from datetime import date
import os, uuid
from flask import Blueprint, request, g, current_app, send_from_directory
from ..extensions import db
from ..models import Lease, RentPayment, MaintenanceRequest, Property, User, Vendor
from ..utils import sniff_file, ok, fail, roles_required, audit, notify, paginate, parse_date, num, STAFF, MANAGERS

bp = Blueprint("rentals", __name__, url_prefix="/api")
CATEGORIES = ("plumbing", "electrical", "appliance", "structural", "cleaning", "other")


def scope_leases(q, u):
    if u.role in MANAGERS:
        return q
    if u.role == "agent":
        return q.join(Property).filter(Property.agent_id == u.id)
    if u.role == "owner":
        return q.join(Property).filter(Property.owner_id == u.id)
    return q.filter(Lease.tenant_id == u.id)


def can_manage_lease(u, lease):
    return u.role in MANAGERS or (u.role == "owner" and lease.property.owner_id == u.id)


def month_add(d, n, day):
    y, m = divmod(d.year * 12 + d.month - 1 + n, 12)
    return date(y, m + 1, min(day, 28))


@bp.post("/leases")
@roles_required(*MANAGERS, "owner")
def create_lease():
    d = request.get_json(silent=True) or {}
    p = db.session.get(Property, d.get("property_id") or 0)
    t = db.session.get(User, d.get("tenant_id") or 0)
    start, end = parse_date(d.get("start_date")), parse_date(d.get("end_date"))
    if not p or not t or t.role != "tenant":
        return fail("Valid property and tenant are required", 422)
    if g.user.role == "owner" and p.owner_id != g.user.id:
        return fail("Not your property", 403)
    if p.listing_type != "rent" or p.status != "available":
        return fail("Property must be an available rental listing", 409)
    if not start or not end or end <= start:
        return fail("End date must be after start date", 422)
    try:
        rent = num(d.get("monthly_rent", p.monthly_rent), float, 1, 1e8)
        dep = num(d.get("security_deposit", 0), float, 0, 1e9)
        due_day = num(d.get("due_day", 5), int, 1, 28)
    except (ValueError, TypeError):
        return fail("Invalid amounts", 422)
    try:  # one transaction: lease + schedule + property status
        lease = Lease(property_id=p.id, tenant_id=t.id, start_date=start, end_date=end, monthly_rent=rent,
                      security_deposit=dep, due_day=due_day)
        db.session.add(lease)
        db.session.flush()
        i = 0
        while (due := month_add(start, i, due_day)) <= end:
            if due >= start:
                db.session.add(RentPayment(lease_id=lease.id, due_date=due, amount=rent))
            i += 1
        p.status = "rented"
        notify(t.id, "Lease created", f"{p.title}: rent Rs {rent:,.0f}/month", "/rentals")
        audit("create_lease", "lease", lease.id)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return ok(lease.to_dict(), 201)


@bp.get("/leases")
@roles_required()
def list_leases():
    return paginate(scope_leases(Lease.query, g.user).order_by(Lease.start_date.desc()), lambda l: l.to_dict())


@bp.post("/leases/<int:lid>/terminate")
@roles_required(*MANAGERS, "owner")
def terminate(lid):
    lease = db.get_or_404(Lease, lid)
    if not can_manage_lease(g.user, lease):
        return fail("Not allowed", 403)
    if lease.status != "active":
        return fail("Lease is not active", 409)
    lease.status = "terminated"
    lease.property.status = "available"
    for pay in lease.payments:
        if pay.status == "pending" and pay.due_date > date.today():
            pay.status = "cancelled"
    notify(lease.tenant_id, "Lease terminated", lease.property.title, "/rentals")
    audit("terminate_lease", "lease", lease.id)
    db.session.commit()
    return ok(lease.to_dict())


@bp.post("/leases/<int:lid>/renew")
@roles_required(*MANAGERS, "owner")
def renew(lid):
    lease = db.get_or_404(Lease, lid)
    if not can_manage_lease(g.user, lease):
        return fail("Not allowed", 403)
    months = (request.get_json(silent=True) or {}).get("months", 11)
    if not isinstance(months, int) or not 1 <= months <= 60:
        return fail("months must be 1-60", 422)
    last = lease.end_date
    for i in range(1, months + 1):
        db.session.add(RentPayment(lease_id=lease.id, due_date=month_add(last, i, lease.due_day), amount=lease.monthly_rent))
    lease.end_date = month_add(last, months, last.day)
    lease.status = "active"
    audit("renew_lease", "lease", lease.id, f"{months} months")
    db.session.commit()
    return ok(lease.to_dict())


@bp.get("/payments")
@roles_required()
def list_payments():
    q = scope_leases(RentPayment.query.join(Lease, RentPayment.lease_id == Lease.id), g.user)
    st = request.args.get("status")
    if st == "overdue":
        q = q.filter(RentPayment.status == "pending", RentPayment.due_date < date.today())
    elif st:
        q = q.filter(RentPayment.status == st)
    return paginate(q.order_by(RentPayment.due_date.desc()), lambda p: p.to_dict())


@bp.post("/payments/<int:pid>/record")
@roles_required(*MANAGERS, "owner")
def record_payment(pid):
    pay = db.get_or_404(RentPayment, pid)
    if not can_manage_lease(g.user, pay.lease):
        return fail("Not allowed", 403)
    if pay.status != "pending":
        return fail("Payment is already settled or cancelled", 409)
    d = request.get_json(silent=True) or {}
    if d.get("method") not in ("cash", "bank_transfer", "upi", "cheque"):
        return fail("method must be cash, bank_transfer, upi or cheque", 422)
    pay.status, pay.method = "paid", d["method"]
    pay.paid_date = parse_date(d.get("paid_date")) or date.today()
    pay.reference, pay.recorded_by = (d.get("reference") or "")[:60], g.user.id
    notify(pay.lease.tenant_id, "Rent receipt recorded", f"Rs {pay.amount:,.0f} for {pay.due_date:%b %Y}", "/rentals")
    audit("record_payment", "rent_payment", pay.id)
    db.session.commit()
    return ok(pay.to_dict())


# ---------------- Maintenance ----------------
@bp.post("/maintenance")
@roles_required("tenant")
def create_maintenance():
    d = request.get_json(silent=True) or {}
    lease = Lease.query.filter_by(tenant_id=g.user.id, status="active").first()
    if not lease:
        return fail("You need an active lease to raise a request", 403)
    if d.get("category") not in CATEGORIES or len((d.get("description") or "").strip()) < 5:
        return fail("Choose a category and describe the issue", 422)
    m = MaintenanceRequest(property_id=lease.property_id, tenant_id=g.user.id, category=d["category"],
                           priority=d.get("priority") if d.get("priority") in ("low", "medium", "high") else "medium",
                           description=d["description"].strip()[:2000])
    db.session.add(m)
    db.session.flush()
    notify(lease.property.owner_id, "New maintenance request", d["category"], "/maintenance")
    notify(lease.property.agent_id, "New maintenance request", d["category"], "/maintenance")
    db.session.commit()
    return ok(m.to_dict(), 201)


@bp.get("/maintenance")
@roles_required()
def list_maintenance():
    u, q = g.user, MaintenanceRequest.query
    if u.role in MANAGERS:
        pass
    elif u.role == "agent":
        q = q.join(Property).filter(Property.agent_id == u.id)
    elif u.role == "owner":
        q = q.join(Property).filter(Property.owner_id == u.id)
    else:
        q = q.filter(MaintenanceRequest.tenant_id == u.id)
    return paginate(q.order_by(MaintenanceRequest.created_at.desc()), lambda m: m.to_dict())


@bp.patch("/maintenance/<int:mid>")
@roles_required(*MANAGERS, "owner")
def update_maintenance(mid):
    m = db.get_or_404(MaintenanceRequest, mid)
    u, d = g.user, request.get_json(silent=True) or {}
    if u.role == "owner":
        if m.property.owner_id != u.id:
            return fail("Not allowed", 403)
        if "cost_approved" in d:  # owners only approve expenses
            m.cost_approved = bool(d["cost_approved"])
    else:
        if d.get("status") in ("open", "assigned", "in_progress", "resolved", "closed"):
            m.status = d["status"]
        if d.get("vendor_id"):
            v = db.session.get(Vendor, d["vendor_id"])
            if not v or not v.active:
                return fail("Invalid vendor", 422)
            m.vendor_id, m.assigned_to = v.id, v.name
        if "assigned_to" in d:
            m.assigned_to = (d["assigned_to"] or "")[:120]
        if "cost" in d:
            try:
                m.cost, m.cost_approved = num(d["cost"], float, 0, 1e8), False
            except (ValueError, TypeError):
                return fail("Invalid cost", 422)
    notify(m.tenant_id, "Maintenance update", f"{m.category}: {m.status}", "/maintenance")
    audit("update_maintenance", "maintenance", m.id, m.status)
    db.session.commit()
    return ok(m.to_dict())


def _maint_visible(u, m):
    return (u.role in MANAGERS or m.tenant_id == u.id or (u.role == "owner" and m.property.owner_id == u.id)
            or (u.role == "agent" and m.property.agent_id == u.id))


@bp.post("/maintenance/<int:mid>/image")
@roles_required()
def maint_image(mid):
    m = db.get_or_404(MaintenanceRequest, mid)
    if not _maint_visible(g.user, m) or g.user.role in ("owner", "agent"):
        return fail("Not allowed", 403)
    f = request.files.get("image")
    ext = sniff_file(f, ("jpg", "png", "webp")) if f else None
    if not ext:
        return fail("Upload a JPG, PNG or WEBP image", 415)
    name = f"{uuid.uuid4().hex}.{ext}"
    f.save(os.path.join(current_app.config["DOC_FOLDER"], name))  # private folder
    m.image = name
    audit("maintenance_image", "maintenance", m.id)
    db.session.commit()
    return ok(m.to_dict())


@bp.get("/maintenance/<int:mid>/image")
@roles_required()
def maint_image_get(mid):
    m = db.get_or_404(MaintenanceRequest, mid)
    if not _maint_visible(g.user, m) or not m.image:
        return fail("Not found", 404)
    return send_from_directory(current_app.config["DOC_FOLDER"], m.image)
