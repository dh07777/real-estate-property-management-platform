from flask import Blueprint, request, g
from ..extensions import db
from ..models import Vendor, Agency, Setting, User
from ..utils import ok, fail, roles_required, audit, get_setting, MANAGERS, ADMINS

bp = Blueprint("extras", __name__, url_prefix="/api")
SETTING_KEYS = {"platform_name": 80, "support_email": 120, "default_commission_rate": 6, "allow_registration": 1,
                "notifications_enabled": 1}


# ---------------- Vendors ----------------
@bp.get("/vendors")
@roles_required(*MANAGERS, "owner")
def vendors():
    return ok([v.to_dict() for v in Vendor.query.order_by(Vendor.name)])


@bp.post("/vendors")
@roles_required(*MANAGERS)
def add_vendor():
    d = request.get_json(silent=True) or {}
    if not (d.get("name") or "").strip() or not d.get("category"):
        return fail("Name and category are required", 422)
    v = Vendor(name=d["name"].strip()[:120], category=d["category"][:30], phone=(d.get("phone") or "")[:20], email=(d.get("email") or "")[:160])
    db.session.add(v)
    audit("add_vendor", "vendor", None, v.name)
    db.session.commit()
    return ok(v.to_dict(), 201)


@bp.patch("/vendors/<int:vid>")
@roles_required(*MANAGERS)
def update_vendor(vid):
    v = db.get_or_404(Vendor, vid)
    d = request.get_json(silent=True) or {}
    for k in ("name", "category", "phone", "email"):
        if k in d:
            setattr(v, k, str(d[k])[:160])
    if "active" in d:
        v.active = bool(d["active"])
    audit("update_vendor", "vendor", v.id)
    db.session.commit()
    return ok(v.to_dict())


# ---------------- Agencies ----------------
@bp.get("/agencies")
@roles_required(*MANAGERS)
def agencies():
    return ok([dict(id=a.id, name=a.name, city=a.city, members=User.query.filter_by(agency_id=a.id).count()) for a in Agency.query])


@bp.post("/agencies")
@roles_required(*ADMINS)
def add_agency():
    d = request.get_json(silent=True) or {}
    name = (d.get("name") or "").strip()
    if not name or Agency.query.filter_by(name=name).first():
        return fail("A unique agency name is required", 422)
    a = Agency(name=name[:120], city=(d.get("city") or "")[:80])
    db.session.add(a)
    audit("add_agency", "agency", None, name)
    db.session.commit()
    return ok(dict(id=a.id, name=a.name, city=a.city, members=0), 201)


@bp.put("/agencies/<int:aid>/members")
@roles_required(*ADMINS)
def assign_member(aid):
    a = db.get_or_404(Agency, aid)
    u = db.session.get(User, (request.get_json(silent=True) or {}).get("user_id") or 0)
    if not u or u.role not in ("agency_owner", "property_manager", "agent"):
        return fail("Pick a staff user", 422)
    u.agency_id = a.id
    audit("assign_agency", "user", u.id, a.name)
    db.session.commit()
    return ok({"message": f"{u.name} added to {a.name}"})


# ---------------- Settings ----------------
@bp.get("/public-settings")
def public_settings():
    return ok({"platform_name": get_setting("platform_name", "EstateFlow"), "allow_registration": get_setting("allow_registration", "1") == "1"})


@bp.get("/settings")
@roles_required(*ADMINS)
def settings():
    return ok({k: get_setting(k, {"platform_name": "EstateFlow", "default_commission_rate": "2", "allow_registration": "1",
                                  "notifications_enabled": "1", "support_email": ""}[k]) for k in SETTING_KEYS})


@bp.put("/settings")
@roles_required(*ADMINS)
def update_settings():
    d = request.get_json(silent=True) or {}
    for k, v in d.items():
        if k not in SETTING_KEYS:
            continue  # unknown keys ignored
        v = str(v)[:SETTING_KEYS[k] if SETTING_KEYS[k] > 1 else 1]
        if k == "default_commission_rate":
            try:
                if not 0 <= float(v) <= 20:
                    raise ValueError
            except ValueError:
                return fail("Commission rate must be 0-20", 422)
        s = db.session.get(Setting, k) or Setting(key=k)
        s.value = v
        db.session.add(s)
    audit("update_settings", "settings", None, ",".join(d.keys()))
    db.session.commit()
    return settings()
