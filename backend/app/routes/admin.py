from flask import Blueprint, request, g
from ..extensions import db
from ..models import User, AuditLog, Agency, ROLES
from ..utils import ok, fail, roles_required, audit, paginate, ADMINS, STAFF, MANAGERS

bp = Blueprint("admin", __name__, url_prefix="/api")


@bp.get("/admin/users")
@roles_required(*ADMINS)
def users():
    q = User.query
    if request.args.get("role"):
        q = q.filter(User.role == request.args["role"])
    if request.args.get("q"):
        like = f"%{request.args['q']}%"
        q = q.filter(User.name.ilike(like) | User.email.ilike(like))
    return paginate(q.order_by(User.created_at.desc()), lambda u: u.to_dict())


@bp.patch("/admin/users/<int:uid>")
@roles_required(*ADMINS)
def update_user(uid):
    u = db.get_or_404(User, uid)
    d = request.get_json(silent=True) or {}
    if u.id == g.user.id:
        return fail("You cannot change your own role or status", 409)
    if u.role == "super_admin" and g.user.role != "super_admin":
        return fail("Only a super admin can modify a super admin", 403)
    if "active" in d:
        u.active = bool(d["active"])
    if "role" in d:
        if g.user.role != "super_admin":
            return fail("Only a super admin can change roles", 403)
        if d["role"] not in ROLES:
            return fail("Invalid role")
        u.role = d["role"]
    audit("admin_update_user", "user", u.id, f"active={u.active} role={u.role}")
    db.session.commit()
    return ok(u.to_dict())


@bp.get("/admin/audit-logs")
@roles_required(*ADMINS)
def logs():
    q = AuditLog.query
    if request.args.get("action"):
        q = q.filter(AuditLog.action == request.args["action"])
    return paginate(q.order_by(AuditLog.created_at.desc()), lambda a: a.to_dict())


@bp.get("/users/lookup")
@roles_required(*MANAGERS, "owner")
def lookup():
    """Minimal id/name list used by dropdowns (tenants, agents, owners)."""
    role = request.args.get("role")
    if role not in ("tenant", "agent", "owner"):
        return fail("role must be tenant, agent or owner")
    rows = User.query.filter_by(role=role, active=True).order_by(User.name).limit(200)
    return ok([{"id": u.id, "name": u.name} for u in rows])
