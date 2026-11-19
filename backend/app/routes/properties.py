import os, uuid
from flask import Blueprint, request, g, current_app, send_from_directory
from sqlalchemy import or_
from ..extensions import db
from ..models import Property, PropertyImage, Amenity, Favorite, User, PROPERTY_TYPES
from ..utils import ok, fail, roles_required, optional_user, audit, notify, paginate, num, STAFF, ADMINS, MANAGERS

bp = Blueprint("properties", __name__, url_prefix="/api")

EDITABLE = ("title", "description", "property_type", "listing_type", "price", "monthly_rent", "address", "city",
            "state", "postal_code", "locality", "bedrooms", "bathrooms", "balconies", "area_sqft", "furnishing",
            "parking", "year_built", "cover_url")  # whitelist -> no mass assignment
NUMERIC = {"price": (float, 0, 1e11), "monthly_rent": (float, 0, 1e8), "bedrooms": (int, 0, 50),
           "bathrooms": (int, 0, 50), "balconies": (int, 0, 20), "area_sqft": (float, 1, 1e7),
           "parking": (int, 0, 50), "year_built": (int, 1800, 2100)}
IMG_MAGIC = {b"\xff\xd8\xff": "jpg", b"\x89PNG": "png", b"RIFF": "webp"}


def clean(d, partial=False):
    out, errs = {}, {}
    for k in EDITABLE:
        if k not in d:
            continue
        v = d[k]
        if k in NUMERIC and v not in (None, ""):
            try:
                v = num(v, *NUMERIC[k])
            except (ValueError, TypeError):
                errs[k] = "Invalid number"
                continue
        elif k in NUMERIC:
            v = None
        elif isinstance(v, str):
            v = v.strip()[:2000]
        out[k] = v
    if not partial:
        for k in ("title", "property_type", "listing_type", "city"):
            if not out.get(k):
                errs[k] = "Required"
    if out.get("property_type") and out["property_type"] not in PROPERTY_TYPES:
        errs["property_type"] = "Invalid type"
    if out.get("listing_type") and out["listing_type"] not in ("sale", "rent"):
        errs["listing_type"] = "Must be sale or rent"
    if out.get("furnishing") and out["furnishing"] not in ("unfurnished", "semi-furnished", "furnished"):
        errs["furnishing"] = "Invalid furnishing"
    return out, errs


def can_edit(u, p):
    return u.role in MANAGERS or (u.role == "agent" and p.agent_id == u.id) or (u.role == "owner" and p.owner_id == u.id)


def set_amenities(p, names):
    p.amenities = []
    for n in {str(n).strip()[:60] for n in (names or []) if str(n).strip()}:
        a = Amenity.query.filter_by(name=n).first() or Amenity(name=n)
        p.amenities.append(a)


def listing_query(u, a):
    q = Property.query
    if u and u.role in STAFF and a.get("all") == "1":
        if u.role == "agent":
            q = q.filter(Property.agent_id == u.id)
    elif u and u.role == "owner" and a.get("mine") == "1":
        q = q.filter(Property.owner_id == u.id)
    else:
        q = q.filter(Property.approval == "approved", Property.status != "archived")
    if a.get("q"):
        like = f"%{a['q'].strip()}%"
        q = q.filter(or_(Property.title.ilike(like), Property.city.ilike(like),
                         Property.locality.ilike(like), Property.address.ilike(like)))
    for f in ("city", "property_type", "listing_type", "furnishing", "status", "approval"):
        if a.get(f):
            q = q.filter(getattr(Property, f) == a[f])
    price_col = Property.monthly_rent if a.get("listing_type") == "rent" else Property.price
    for key, col, op in (("min_price", price_col, ">="), ("max_price", price_col, "<="),
                         ("min_area", Property.area_sqft, ">="), ("max_area", Property.area_sqft, "<="),
                         ("bedrooms", Property.bedrooms, ">="), ("bathrooms", Property.bathrooms, ">=")):
        v = a.get(key, type=float)
        if v is not None:
            q = q.filter(col >= v if op == ">=" else col <= v)
    if a.get("featured") == "1":
        q = q.filter(Property.featured.is_(True))
    for name in filter(None, (a.get("amenities") or "").split(",")):
        q = q.filter(Property.amenities.any(Amenity.name == name.strip()))
    sort = a.get("sort", "latest")
    order = {"price_asc": Property.price.asc(), "price_desc": Property.price.desc(),
             "popular": Property.views.desc()}.get(sort, Property.created_at.desc())
    return q.order_by(order)


@bp.get("/properties")
def list_properties():
    u = optional_user()
    favs = {f.property_id for f in Favorite.query.filter_by(user_id=u.id)} if u else set()

    def ser(p):
        d = p.to_dict()
        d["is_favorite"] = p.id in favs
        return d
    return paginate(listing_query(u, request.args), ser)


@bp.get("/properties/<int:pid>")
def get_property(pid):
    u = optional_user()
    p = db.get_or_404(Property, pid)
    if p.approval != "approved" or p.status == "archived":
        if not (u and (u.role in MANAGERS or can_edit(u, p))):
            return fail("Property not found", 404)
    p.views = (p.views or 0) + 1
    db.session.commit()
    d = p.to_dict(detail=True)
    d["is_favorite"] = bool(u and Favorite.query.filter_by(user_id=u.id, property_id=pid).first())
    sim = Property.query.filter(Property.id != pid, Property.city == p.city, Property.approval == "approved",
                                Property.status != "archived", Property.listing_type == p.listing_type).limit(4)
    d["similar"] = [s.to_dict() for s in sim]
    return ok(d)


@bp.post("/properties")
@roles_required(*STAFF, "owner")
def create_property():
    d = request.get_json(silent=True) or {}
    data, errs = clean(d)
    if errs:
        return fail("Validation failed", 422, errs)
    p = Property(**data)
    u = g.user
    if u.role == "owner":
        p.owner_id, p.approval = u.id, "pending"
    else:
        p.approval = "approved" if u.role in MANAGERS else "pending"
        oid = d.get("owner_id")
        if oid and (own := db.session.get(User, oid)) and own.role == "owner":
            p.owner_id = own.id
        ag = db.session.get(User, d.get("agent_id") or 0)
        p.agent_id = u.id if u.role == "agent" else (ag.id if ag and ag.role == "agent" else None)
    set_amenities(p, d.get("amenities"))
    db.session.add(p)
    db.session.flush()
    audit("create_property", "property", p.id, p.title)
    if p.approval == "pending":
        for m in User.query.filter(User.role.in_(MANAGERS), User.active.is_(True)):
            notify(m.id, "Property awaiting approval", p.title, "/manage")
    db.session.commit()
    return ok(p.to_dict(detail=True), 201)


@bp.put("/properties/<int:pid>")
@roles_required(*STAFF, "owner")
def update_property(pid):
    p = db.get_or_404(Property, pid)
    if not can_edit(g.user, p):
        return fail("Not allowed", 403)
    d = request.get_json(silent=True) or {}
    data, errs = clean(d, partial=True)
    if errs:
        return fail("Validation failed", 422, errs)
    for k, v in data.items():
        setattr(p, k, v)
    if "amenities" in d:
        set_amenities(p, d["amenities"])
    if g.user.role in MANAGERS and d.get("agent_id") is not None:
        ag = db.session.get(User, d["agent_id"])
        if ag and ag.role == "agent":
            p.agent_id = ag.id
    if g.user.role not in MANAGERS and p.approval == "approved":
        p.approval = "pending"  # edits by non-managers need re-approval
    audit("update_property", "property", p.id)
    db.session.commit()
    return ok(p.to_dict(detail=True))


@bp.delete("/properties/<int:pid>")
@roles_required(*STAFF, "owner")
def archive_property(pid):
    p = db.get_or_404(Property, pid)
    if not can_edit(g.user, p):
        return fail("Not allowed", 403)
    p.status = "archived"
    audit("archive_property", "property", p.id)
    db.session.commit()
    return ok({"message": "Property archived"})


@bp.post("/properties/<int:pid>/review")
@roles_required(*MANAGERS)
def review_property(pid):
    p = db.get_or_404(Property, pid)
    decision = (request.get_json(silent=True) or {}).get("decision")
    if decision not in ("approved", "rejected"):
        return fail("decision must be approved or rejected")
    p.approval = decision
    audit("review_property", "property", p.id, decision)
    notify(p.owner_id, f"Listing {decision}", p.title, f"/properties/{p.id}")
    db.session.commit()
    return ok(p.to_dict())


@bp.post("/properties/<int:pid>/feature")
@roles_required(*MANAGERS)
def feature(pid):
    p = db.get_or_404(Property, pid)
    p.featured = not p.featured
    audit("feature_property", "property", p.id, str(p.featured))
    db.session.commit()
    return ok(p.to_dict())


@bp.post("/properties/<int:pid>/images")
@roles_required(*STAFF, "owner")
def upload_image(pid):
    p = db.get_or_404(Property, pid)
    if not can_edit(g.user, p):
        return fail("Not allowed", 403)
    f = request.files.get("image")
    if not f:
        return fail("No image uploaded")
    head = f.read(12)
    f.seek(0)
    ext = next((e for m, e in IMG_MAGIC.items() if head.startswith(m)), None)
    if ext == "webp" and head[8:12] != b"WEBP":
        ext = None
    if not ext:
        return fail("Only JPG, PNG or WEBP images are allowed", 415)
    name = f"{uuid.uuid4().hex}.{ext}"  # never trust the client filename
    f.save(os.path.join(current_app.config["UPLOAD_FOLDER"], name))
    db.session.add(PropertyImage(property_id=pid, filename=name))
    audit("upload_image", "property", pid)
    db.session.commit()
    return ok({"url": f"/api/uploads/{name}"}, 201)


@bp.get("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)  # safe_join prevents traversal


@bp.post("/properties/<int:pid>/favorite")
@roles_required()
def toggle_favorite(pid):
    db.get_or_404(Property, pid)
    f = Favorite.query.filter_by(user_id=g.user.id, property_id=pid).first()
    if f:
        db.session.delete(f)
    else:
        db.session.add(Favorite(user_id=g.user.id, property_id=pid))
    db.session.commit()
    return ok({"favorite": not f})


@bp.get("/favorites")
@roles_required()
def my_favorites():
    q = Property.query.join(Favorite, Favorite.property_id == Property.id).filter(Favorite.user_id == g.user.id)
    return paginate(q, lambda p: {**p.to_dict(), "is_favorite": True})


@bp.get("/meta")
def meta():
    return ok({"amenities": [a.name for a in Amenity.query.order_by(Amenity.name)],
               "cities": [c for (c,) in db.session.query(Property.city).filter(Property.approval == "approved").distinct()],
               "property_types": list(PROPERTY_TYPES)})
