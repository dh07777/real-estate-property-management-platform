from flask import Blueprint, g
from ..extensions import db
from ..models import Notification
from ..utils import ok, fail, roles_required, paginate

bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@bp.get("")
@roles_required()
def mine():
    q = Notification.query.filter_by(user_id=g.user.id)
    unread = q.filter_by(read=False).count()
    resp, code = paginate(q.order_by(Notification.created_at.desc()), lambda n: n.to_dict())
    j = resp.get_json()
    j["unread"] = unread
    return ok(j["data"], page=j["page"], total=j["total"], pages=j["pages"], per_page=j["per_page"], unread=unread)


@bp.post("/<int:nid>/read")
@roles_required()
def read_one(nid):
    n = db.get_or_404(Notification, nid)
    if n.user_id != g.user.id:  # IDOR guard
        return fail("Not found", 404)
    n.read = True
    db.session.commit()
    return ok(n.to_dict())


@bp.post("/read-all")
@roles_required()
def read_all():
    Notification.query.filter_by(user_id=g.user.id, read=False).update({"read": True})
    db.session.commit()
    return ok({"message": "All notifications marked as read"})
