from flask import Blueprint, request, g
from sqlalchemy import func
from ..extensions import db
from ..models import Review, Property, Lease, Appointment, Deal, User
from ..utils import ok, fail, roles_required, audit, notify, paginate, MANAGERS

bp = Blueprint("reviews", __name__, url_prefix="/api")


def avg(q):
    a, c = q.with_entities(func.avg(Review.rating), func.count()).one()
    return {"average": round(float(a), 2) if a else None, "count": c}


def is_verified(u, p):
    return bool(Lease.query.filter_by(property_id=p.id, tenant_id=u.id).first()
                or Deal.query.filter_by(property_id=p.id, buyer_id=u.id, status="completed").first()
                or Appointment.query.filter_by(property_id=p.id, user_id=u.id, status="completed").first())


@bp.get("/properties/<int:pid>/reviews")
def list_reviews(pid):
    q = Review.query.filter(Review.property_id == pid, Review.status != "hidden")
    p = db.get_or_404(Property, pid)
    agent = None
    if p.agent_id:
        a, c = (db.session.query(func.avg(Review.agent_rating), func.count(Review.agent_rating))
                .filter(Review.agent_id == p.agent_id, Review.status != "hidden").one())
        agent = {"name": p.agent.name, "average": round(float(a), 2) if a else None, "count": c}
    return ok([r.to_dict() for r in q.order_by(Review.created_at.desc()).limit(50)], summary=avg(q), agent=agent)


@bp.post("/properties/<int:pid>/reviews")
@roles_required("buyer", "tenant", "owner")
def add_review(pid):
    p = db.get_or_404(Property, pid)
    d = request.get_json(silent=True) or {}
    rating = d.get("rating")
    ar = d.get("agent_rating")
    if not isinstance(rating, int) or not 1 <= rating <= 5 or (ar is not None and (not isinstance(ar, int) or not 1 <= ar <= 5)):
        return fail("Ratings must be whole numbers from 1 to 5", 422)
    if p.owner_id == g.user.id:
        return fail("You cannot review your own property", 403)
    if Review.query.filter_by(user_id=g.user.id, property_id=pid).first():
        return fail("You already reviewed this property", 409)
    r = Review(property_id=pid, user_id=g.user.id, agent_id=p.agent_id, rating=rating, agent_rating=ar,
               comment=(d.get("comment") or "").strip()[:1000], verified=is_verified(g.user, p))
    db.session.add(r)
    notify(p.agent_id, "New review", f"{rating}/5 on {p.title}", f"/properties/{pid}")
    db.session.commit()
    return ok(r.to_dict(), 201)


@bp.post("/reviews/<int:rid>/report")
@roles_required()
def report(rid):
    r = db.get_or_404(Review, rid)
    r.status = "reported" if r.status == "published" else r.status
    r.report_reason = ((request.get_json(silent=True) or {}).get("reason") or "Inappropriate")[:200]
    for m in User.query.filter(User.role.in_(MANAGERS)):
        notify(m.id, "Review reported", r.property.title, "/moderation")
    db.session.commit()
    return ok({"message": "Thanks, a moderator will review this."})


@bp.get("/admin/reviews")
@roles_required(*MANAGERS)
def moderation_queue():
    q = Review.query.filter(Review.status == request.args.get("status", "reported"))
    return paginate(q.order_by(Review.created_at.desc()), lambda r: r.to_dict())


@bp.patch("/admin/reviews/<int:rid>")
@roles_required(*MANAGERS)
def moderate(rid):
    r = db.get_or_404(Review, rid)
    st = (request.get_json(silent=True) or {}).get("status")
    if st not in ("published", "hidden"):
        return fail("status must be published or hidden")
    r.status = st
    audit("moderate_review", "review", r.id, st)
    db.session.commit()
    return ok(r.to_dict())
