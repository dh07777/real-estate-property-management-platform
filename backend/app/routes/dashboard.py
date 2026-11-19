import io
from datetime import date, datetime, timedelta
from collections import defaultdict
from flask import Blueprint, request, g, send_file
from sqlalchemy import func
from ..extensions import db
from ..models import (Deal, Commission, User, Property, Lease, RentPayment, MaintenanceRequest, Inquiry, Appointment,
                      Favorite, Notification, AuditLog)
from ..utils import ok, fail, roles_required, MANAGERS, STAFF

bp = Blueprint("dashboard", __name__, url_prefix="/api")


def monthly_revenue(payments):
    """Last 6 months of recorded rent, computed from real payment rows."""
    today = date.today()
    keys = []
    y, m = today.year, today.month
    for _ in range(6):
        keys.append(f"{y}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    totals = defaultdict(float)
    for p in payments:
        if p.status == "paid" and p.paid_date:
            totals[p.paid_date.strftime("%Y-%m")] += p.amount
    return [{"month": k, "revenue": totals.get(k, 0)} for k in reversed(keys)]


def paid_sum(q):
    return q.with_entities(func.coalesce(func.sum(RentPayment.amount), 0)).scalar()


@bp.get("/dashboard")
@roles_required()
def dashboard():
    u, today = g.user, date.today()
    role = u.role
    if role in MANAGERS:
        pays = RentPayment.query
        data = dict(
            kind="admin",
            total_users=User.query.count(), total_properties=Property.query.count(),
            active_listings=Property.query.filter_by(approval="approved", status="available").count(),
            sold=Property.query.filter_by(status="sold").count(), rented=Property.query.filter_by(status="rented").count(),
            rental_revenue=paid_sum(pays.filter(RentPayment.status == "paid")),
            overdue_rent=paid_sum(pays.filter(RentPayment.status == "pending", RentPayment.due_date < today)),
            pending_approvals=Property.query.filter_by(approval="pending").count(),
            open_maintenance=MaintenanceRequest.query.filter(MaintenanceRequest.status.in_(("open", "assigned", "in_progress"))).count(),
            monthly=monthly_revenue(pays.all()),
            by_type=[{"name": t, "count": c} for t, c in db.session.query(Property.property_type, func.count()).group_by(Property.property_type)],
            recent_activity=[a.to_dict() for a in AuditLog.query.order_by(AuditLog.created_at.desc()).limit(8)])
    elif role == "agent":
        inq = Inquiry.query.filter_by(agent_id=u.id)
        data = dict(
            kind="agent",
            assigned_properties=Property.query.filter_by(agent_id=u.id).count(),
            active_listings=Property.query.filter_by(agent_id=u.id, approval="approved", status="available").count(),
            inquiries=inq.count(), new_inquiries=inq.filter_by(status="New").count(),
            converted=inq.filter_by(status="Converted").count(),
            upcoming_visits=Appointment.query.filter(Appointment.agent_id == u.id, Appointment.scheduled_at >= datetime.now(),
                                                     Appointment.status.in_(("pending", "approved"))).count(),
            follow_ups=[i.to_dict() for i in inq.filter(Inquiry.follow_up_date.isnot(None), Inquiry.follow_up_date <= today + timedelta(days=7),
                                                        Inquiry.status.notin_(("Converted", "Lost"))).limit(10)],
            pipeline=[{"name": s, "count": c} for s, c in db.session.query(Inquiry.status, func.count()).filter(Inquiry.agent_id == u.id).group_by(Inquiry.status)],
            commission_total=sum(c.amount for c in Commission.query.filter_by(agent_id=u.id)),
            commission_pending=sum(c.amount for c in Commission.query.filter_by(agent_id=u.id, status="pending")),
            deals_closed=Deal.query.filter_by(agent_id=u.id, status="completed").count(),
            sales_value=sum(d.price for d in Deal.query.filter_by(agent_id=u.id, status="completed")))
    elif role == "owner":
        props = Property.query.filter_by(owner_id=u.id)
        ids = [p.id for p in props]
        leases = Lease.query.filter(Lease.property_id.in_(ids or [0]))
        pays = RentPayment.query.join(Lease).filter(Lease.property_id.in_(ids or [0]))
        data = dict(
            kind="owner", owned_properties=len(ids), occupied=props.filter_by(status="rented").count(),
            rental_income=paid_sum(pays.filter(RentPayment.status == "paid")),
            pending_rent=paid_sum(pays.filter(RentPayment.status == "pending", RentPayment.due_date < today)),
            open_maintenance=MaintenanceRequest.query.filter(MaintenanceRequest.property_id.in_(ids or [0]),
                                                             MaintenanceRequest.status.in_(("open", "assigned", "in_progress"))).count(),
            leases=[l.to_dict() for l in leases.filter_by(status="active")], monthly=monthly_revenue(pays.all()))
    elif role == "tenant":
        lease = Lease.query.filter_by(tenant_id=u.id, status="active").first()
        pays = RentPayment.query.join(Lease).filter(Lease.tenant_id == u.id)
        nxt = pays.filter(RentPayment.status == "pending").order_by(RentPayment.due_date).first()
        data = dict(kind="tenant", lease=lease.to_dict() if lease else None,
                    next_due=nxt.to_dict() if nxt else None,
                    payments=[p.to_dict() for p in pays.order_by(RentPayment.due_date.desc()).limit(12)],
                    open_maintenance=MaintenanceRequest.query.filter(MaintenanceRequest.tenant_id == u.id,
                                                                     MaintenanceRequest.status.in_(("open", "assigned", "in_progress"))).count())
    else:  # buyer
        data = dict(kind="buyer", saved=Favorite.query.filter_by(user_id=u.id).count(),
                    inquiries=Inquiry.query.filter_by(user_id=u.id).count(),
                    visits=Appointment.query.filter(Appointment.user_id == u.id, Appointment.status.in_(("pending", "approved"))).count(),
                    deals=[d.to_dict() for d in Deal.query.filter_by(buyer_id=u.id).order_by(Deal.created_at.desc())])
    data["unread_notifications"] = Notification.query.filter_by(user_id=u.id, read=False).count()
    return ok(data)


# ---------------- Reports (JSON / Excel / PDF) ----------------
def report_rows(name):
    if name == "inventory":
        cols = ["ID", "Title", "Type", "Listing", "City", "Price / Rent (INR)", "Status", "Approval"]
        rows = [[p.id, p.title, p.property_type, p.listing_type, p.city,
                 p.price if p.listing_type == "sale" else p.monthly_rent, p.status, p.approval] for p in Property.query]
    elif name == "rentals":
        cols = ["Lease", "Property", "Tenant", "Start", "End", "Rent (INR)", "Deposit (INR)", "Status"]
        rows = [[l.id, l.property.title, l.tenant.name, l.start_date, l.end_date, l.monthly_rent, l.security_deposit, l.status] for l in Lease.query]
    elif name == "payments":
        cols = ["ID", "Property", "Tenant", "Due", "Amount (INR)", "Status", "Paid on", "Method"]
        rows = [[p.id, p.lease.property.title, p.lease.tenant.name, p.due_date, p.amount, p.display_status, p.paid_date, p.method] for p in RentPayment.query]
    elif name == "maintenance":
        cols = ["ID", "Property", "Category", "Priority", "Status", "Cost (INR)", "Approved"]
        rows = [[m.id, m.property.title, m.category, m.priority, m.status, m.cost, m.cost_approved] for m in MaintenanceRequest.query]
    elif name == "leads":
        cols = ["ID", "Property", "Name", "Status", "Priority", "Source", "Created"]
        rows = [[i.id, i.property.title, i.name, i.status, i.priority, i.source, i.created_at.date()] for i in Inquiry.query]
    elif name == "deals":
        cols = ["Deal", "Property", "Buyer", "Price (INR)", "Booking (INR)", "Status", "Commission %"]
        rows = [[d.id, d.property.title, d.buyer.name, d.price, d.booking_amount, d.status, d.commission_rate] for d in Deal.query]
    elif name == "commissions":
        cols = ["ID", "Property", "Agent", "Amount (INR)", "Status", "Paid on"]
        rows = [[c.id, c.deal.property.title, c.agent.name, c.amount, c.status, c.paid_date] for c in Commission.query]
    elif name == "ledger":
        from .finance import ledger_entries
        end = date.today()
        cols = ["Date", "Type", "Category", "Property", "Amount (INR)", "Reference"]
        rows = [[e["date"], e["type"], e["category"], e["property"], e["amount"], e["reference"]] for e in ledger_entries(None, end - timedelta(days=365), end)]
    elif name == "occupancy":
        cols = ["Property", "City", "Status", "Tenant", "Lease ends"]
        rows = []
        for p in Property.query.filter_by(listing_type="rent"):
            l = Lease.query.filter_by(property_id=p.id, status="active").first()
            rows.append([p.title, p.city, "occupied" if l else "vacant", l.tenant.name if l else "", l.end_date if l else ""])
    elif name == "lease_expiry":
        cols = ["Lease", "Property", "Tenant", "Ends", "Days left"]
        rows = [[l.id, l.property.title, l.tenant.name, l.end_date, (l.end_date - date.today()).days]
                for l in Lease.query.filter_by(status="active").order_by(Lease.end_date) if (l.end_date - date.today()).days <= 90]
    elif name == "appointments":
        cols = ["ID", "Property", "Visitor", "When", "Status"]
        rows = [[a.id, a.property.title, a.user.name, a.scheduled_at, a.status] for a in Appointment.query]
    else:
        return None, None
    return cols, rows


@bp.get("/reports/<name>")
@roles_required(*MANAGERS)
def report(name):
    cols, rows = report_rows(name)
    if cols is None:
        return fail("Unknown report", 404)
    fmt = request.args.get("format", "json")
    s = lambda v: "" if v is None else (v if isinstance(v, (int, float)) else str(v))
    rows = [[s(c) for c in r] for r in rows]
    if fmt == "xlsx":
        from openpyxl import Workbook
        wb = Workbook(); ws = wb.active; ws.title = name[:30]
        ws.append(cols)
        for r in rows:
            ws.append(r)
        buf = io.BytesIO(); wb.save(buf); buf.seek(0)
        return send_file(buf, as_attachment=True, download_name=f"{name}.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if fmt == "pdf":
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=landscape(A4))
        t = Table([cols] + [[str(c)[:28] for c in r] for r in rows], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#14213D")),
                               ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 7),
                               ("GRID", (0, 0), (-1, -1), 0.25, colors.grey)]))
        st = getSampleStyleSheet()
        doc.build([Paragraph(f"EstateFlow - {name.title()} report ({date.today():%d %b %Y})", st["Title"]), Spacer(1, 8), t])
        buf.seek(0)
        return send_file(buf, as_attachment=True, download_name=f"{name}.pdf", mimetype="application/pdf")
    return ok({"columns": cols, "rows": rows})
