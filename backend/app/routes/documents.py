import os, uuid
from datetime import date, timedelta
from flask import Blueprint, request, g, current_app, send_from_directory
from ..extensions import db
from ..models import Document, DocumentActivity, Property, Lease, Deal
from ..utils import ok, fail, roles_required, audit, parse_date, sniff_file, MANAGERS

bp = Blueprint("documents", __name__, url_prefix="/api/documents")
CATEGORIES = ("property", "ownership", "rental_agreement", "sale_agreement", "tenant", "invoice", "other")


def related(u, p):
    """Is the user a party to this property (owner, agent, tenant on a lease, buyer in a deal)?"""
    if not p:
        return False
    return (p.owner_id == u.id or p.agent_id == u.id
            or Lease.query.filter_by(property_id=p.id, tenant_id=u.id).first() is not None
            or Deal.query.filter_by(property_id=p.id, buyer_id=u.id).first() is not None)


def can_view(u, d):
    return u.role in MANAGERS or d.uploaded_by == u.id or (d.visibility == "parties" and related(u, d.property))


def log(d, action):
    db.session.add(DocumentActivity(document_id=d.id, user_id=g.user.id, action=action))


@bp.post("")
@roles_required()
def upload():
    f = request.files.get("file")
    form = request.form
    if not f:
        return fail("No file uploaded")
    ext = sniff_file(f, ("pdf", "png", "jpg", "docx"))
    if not ext:
        return fail("Only PDF, PNG, JPG or DOCX files are allowed", 415)
    title, cat = (form.get("title") or "").strip(), form.get("category")
    if not title or cat not in CATEGORIES:
        return fail("Title and a valid category are required", 422)
    pid = form.get("property_id", type=int)
    p = db.session.get(Property, pid) if pid else None
    if pid and (not p or not (g.user.role in MANAGERS or related(g.user, p))):
        return fail("You cannot attach documents to that property", 403)
    name = f"{uuid.uuid4().hex}.{ext}"
    f.save(os.path.join(current_app.config["DOC_FOLDER"], name))
    d = Document(title=title[:160], category=cat, property_id=p.id if p else None, uploaded_by=g.user.id, filename=name,
                 original_name=os.path.basename(f.filename or f"document.{ext}")[:160], size=request.content_length,
                 visibility="parties" if form.get("visibility") == "parties" and p else "private",
                 expires_on=parse_date(form.get("expires_on")) if form.get("expires_on") else None)
    db.session.add(d)
    db.session.flush()
    log(d, "uploaded")
    audit("upload_document", "document", d.id, d.category)
    db.session.commit()
    return ok(d.to_dict(), 201)


@bp.get("")
@roles_required()
def list_docs():
    q = Document.query
    if request.args.get("category"):
        q = q.filter_by(category=request.args["category"])
    if request.args.get("expiring") == "1":
        q = q.filter(Document.expires_on.isnot(None), Document.expires_on <= date.today() + timedelta(days=30))
    docs = [d for d in q.order_by(Document.created_at.desc()).limit(500) if can_view(g.user, d)]
    return ok([dict(d.to_dict(), expired=bool(d.expires_on and d.expires_on < date.today())) for d in docs])


@bp.get("/<int:did>/download")
@roles_required()
def download(did):
    d = db.get_or_404(Document, did)
    if not can_view(g.user, d):
        return fail("Not found", 404)  # same answer as missing: no existence leak
    log(d, "downloaded")
    db.session.commit()
    return send_from_directory(current_app.config["DOC_FOLDER"], d.filename, as_attachment=True, download_name=d.original_name)


@bp.get("/<int:did>/activity")
@roles_required()
def activity(did):
    d = db.get_or_404(Document, did)
    if not (g.user.role in MANAGERS or d.uploaded_by == g.user.id):
        return fail("Not found", 404)
    rows = DocumentActivity.query.filter_by(document_id=did).order_by(DocumentActivity.created_at.desc())
    return ok([{"action": r.action, "user": r.user.name if r.user else None, "at": r.created_at.isoformat()} for r in rows])


@bp.delete("/<int:did>")
@roles_required()
def delete(did):
    d = db.get_or_404(Document, did)
    if not (g.user.role in MANAGERS or d.uploaded_by == g.user.id):
        return fail("Not found", 404)
    path = os.path.join(current_app.config["DOC_FOLDER"], d.filename)
    DocumentActivity.query.filter_by(document_id=d.id).delete()
    db.session.delete(d)
    audit("delete_document", "document", did)
    db.session.commit()
    if os.path.exists(path):
        os.remove(path)
    return ok({"message": "Document deleted"})
