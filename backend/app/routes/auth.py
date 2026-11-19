import re
from flask import Blueprint, request, g, current_app
from flask_jwt_extended import create_access_token
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from ..extensions import db, limiter
from ..models import User, SELF_REGISTER_ROLES
from ..utils import ok, fail, roles_required, audit, get_setting

bp = Blueprint("auth", __name__, url_prefix="/api/auth")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def strong(pw):
    return isinstance(pw, str) and len(pw) >= 8 and any(c.isdigit() for c in pw) and any(c.isalpha() for c in pw)


def _ser():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="pw-reset")


@bp.post("/register")
@limiter.limit("20/hour")
def register():
    if get_setting("allow_registration", "1") != "1":
        return fail("Registration is currently closed", 403)
    d = request.get_json(silent=True) or {}
    name, email, pw = (d.get("name") or "").strip(), (d.get("email") or "").strip().lower(), d.get("password")
    role = d.get("role", "buyer")
    if not name or not EMAIL_RE.match(email):
        return fail("Enter a valid name and email")
    if role not in SELF_REGISTER_ROLES:  # prevents self-assigning admin/staff roles
        return fail("Role not allowed for self-registration", 403)
    if not strong(pw):
        return fail("Password needs 8+ characters with letters and numbers")
    if User.query.filter_by(email=email).first():
        return fail("Email already registered", 409)
    u = User(name=name, email=email, role=role, phone=(d.get("phone") or "")[:20])
    u.set_password(pw)
    db.session.add(u)
    db.session.commit()
    audit("register", "user", u.id, user_id=u.id)
    db.session.commit()
    return ok(u.to_dict(), 201)


@bp.post("/login")
@limiter.limit("10/minute")
def login():
    d = request.get_json(silent=True) or {}
    u = User.query.filter_by(email=(d.get("email") or "").strip().lower()).first()
    if not u or not u.check_password(d.get("password") or ""):
        return fail("Incorrect email or password", 401)
    if not u.active:
        return fail("This account is deactivated", 403)
    audit("login", "user", u.id, user_id=u.id)
    db.session.commit()
    return ok({"token": create_access_token(identity=str(u.id)), "user": u.to_dict()})


@bp.post("/logout")
@roles_required()
def logout():
    audit("logout", "user", g.user.id)
    db.session.commit()
    return ok({"message": "Signed out"})


@bp.get("/me")
@roles_required()
def me():
    return ok(g.user.to_dict())


@bp.put("/profile")
@roles_required()
def profile():
    d = request.get_json(silent=True) or {}
    if d.get("name", "").strip():
        g.user.name = d["name"].strip()[:120]
    g.user.phone = (d.get("phone") or g.user.phone or "")[:20]
    db.session.commit()
    return ok(g.user.to_dict())


@bp.post("/change-password")
@roles_required()
def change_password():
    d = request.get_json(silent=True) or {}
    if not g.user.check_password(d.get("current_password") or ""):
        return fail("Current password is incorrect", 403)
    if not strong(d.get("new_password")):
        return fail("Password needs 8+ characters with letters and numbers")
    g.user.set_password(d["new_password"])
    audit("change_password", "user", g.user.id)
    db.session.commit()
    return ok({"message": "Password updated"})


@bp.post("/forgot-password")
@limiter.limit("5/hour")
def forgot():
    email = ((request.get_json(silent=True) or {}).get("email") or "").strip().lower()
    u = User.query.filter_by(email=email).first()
    data = {"message": "If that email exists, a reset link has been generated."}
    if u and current_app.config["EXPOSE_RESET_TOKEN"]:  # dev only: no email service is configured
        data["dev_reset_token"] = _ser().dumps(u.id)
    return ok(data)


@bp.post("/reset-password")
def reset():
    d = request.get_json(silent=True) or {}
    try:
        uid = _ser().loads(d.get("token", ""), max_age=3600)
    except (BadSignature, SignatureExpired):
        return fail("Reset link is invalid or expired", 400)
    if not strong(d.get("new_password")):
        return fail("Password needs 8+ characters with letters and numbers")
    u = db.session.get(User, uid)
    u.set_password(d["new_password"])
    audit("reset_password", "user", u.id, user_id=u.id)
    db.session.commit()
    return ok({"message": "Password reset. You can sign in now."})
