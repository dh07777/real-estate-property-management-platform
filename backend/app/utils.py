from functools import wraps
from datetime import datetime
from flask import jsonify, g, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from .extensions import db

ADMINS = ("super_admin", "agency_owner")
STAFF = ("super_admin", "agency_owner", "property_manager", "agent")
MANAGERS = ("super_admin", "agency_owner", "property_manager")


def ok(data=None, code=200, **meta):
    return jsonify(success=True, data=data, **meta), code


def fail(message, code=400, errors=None):
    return jsonify(success=False, message=message, errors=errors), code


def _load_user():
    from .models import User
    uid = get_jwt_identity()
    return db.session.get(User, int(uid)) if uid else None


def roles_required(*roles):
    """Require a valid JWT, an active account and (optionally) one of `roles`."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **k):
            verify_jwt_in_request()
            u = _load_user()
            if not u or not u.active:
                return fail("Account not found or deactivated", 401)
            if roles and u.role not in roles:
                return fail("You do not have permission to do this", 403)
            g.user = u
            return fn(*a, **k)
        return wrapper
    return deco


def optional_user():
    verify_jwt_in_request(optional=True)
    u = _load_user()
    return u if u and u.active else None


def audit(action, entity=None, entity_id=None, detail=None, user_id=None):
    from .models import AuditLog
    uid = user_id or (g.user.id if getattr(g, "user", None) else None)
    db.session.add(AuditLog(user_id=uid, action=action, entity=entity, entity_id=entity_id,
                            detail=(detail or "")[:500], ip=request.remote_addr))


def notify(user_id, title, body="", link=None):
    from .models import Notification
    if user_id and get_setting("notifications_enabled", "1") == "1":
        db.session.add(Notification(user_id=user_id, title=title, body=body, link=link))


def parse_dt(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", ""))
    except (ValueError, TypeError):
        return None


def parse_date(s):
    d = parse_dt(s)
    return d.date() if d else None


def num(v, cast=float, lo=None, hi=None):
    """Return a validated number or raise ValueError."""
    x = cast(v)
    if (lo is not None and x < lo) or (hi is not None and x > hi):
        raise ValueError("out of range")
    return x


def paginate(query, serialize):
    page = max(request.args.get("page", 1, type=int), 1)
    per = min(max(request.args.get("per_page", 12, type=int), 1), 100)
    p = query.paginate(page=page, per_page=per, error_out=False)
    return ok([serialize(i) for i in p.items], page=p.page, per_page=per, total=p.total, pages=p.pages)


def get_setting(key, default=None):
    from .models import Setting
    s = db.session.get(Setting, key)
    return s.value if s else default


def sniff_file(f, allow):
    """Detect real file type from magic bytes (never trust extension/MIME)."""
    head = f.read(12)
    f.seek(0)
    ext = None
    if head.startswith(b"\xff\xd8\xff"): ext = "jpg"
    elif head.startswith(b"\x89PNG"): ext = "png"
    elif head.startswith(b"%PDF"): ext = "pdf"
    elif head[:4] == b"RIFF" and head[8:12] == b"WEBP": ext = "webp"
    elif head.startswith(b"PK\x03\x04") and (f.filename or "").lower().endswith(".docx"): ext = "docx"
    return ext if ext in allow else None
