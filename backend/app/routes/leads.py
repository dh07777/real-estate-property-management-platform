from datetime import datetime, timedelta
from flask import Blueprint, request, g
from ..extensions import db
from ..models import Inquiry, Appointment, Property, User, LEAD_STATUSES
from ..utils import ok, fail, roles_required, optional_user, audit, notify, paginate, parse_dt, parse_date, STAFF, MANAGERS

bp = Blueprint("leads", __name__, url_prefix="/api")


# ---------------- Inquiries / leads ----------------
@bp.post("/inquiries")
def create_inquiry():
    u = optional_user()
    d = request.get_json(silent=True) or {}
    p = db.session.get(Property, d.get("property_id") or 0)
    if not p or p.approval != "approved":
        return fail("Property not found", 404)
    name = (d.get("name") or (u.name if u else "")).strip()
    email = (d.get("email") or (u.email if u else "")).strip()
    msg = (d.get("message") or "").strip()
    if not (name and "@" in email and len(msg) >= 5):
        return fail("Name, valid email and a message are required", 422)
    i = Inquiry(property_id=p.id, user_id=u.id if u else None, agent_id=p.agent_id, name=name[:120],
                email=email[:160], phone=(d.get("phone") or "")[:20], message=msg[:2000])
    db.session.add(i)
    db.session.flush()
    notify(p.agent_id, "New inquiry", f"{name} asked about {p.title}", "/inquiries")
    notify(p.owner_id, "New inquiry on your property", p.title, "/inquiries")
    db.session.commit()
    return ok(i.to_dict(), 201)


@bp.get("/inquiries")
@roles_required()
def list_inquiries():
    u, q = g.user, Inquiry.query
    if u.role in MANAGERS:
        pass
    elif u.role == "agent":
        q = q.filter(Inquiry.agent_id == u.id)
    elif u.role == "owner":
        q = q.join(Property).filter(Property.owner_id == u.id)
    else:
        q = q.filter(Inquiry.user_id == u.id)
    if request.args.get("status"):
        q = q.filter(Inquiry.status == request.args["status"])
    return paginate(q.order_by(Inquiry.created_at.desc()), lambda i: i.to_dict())


@bp.patch("/inquiries/<int:iid>")
@roles_required(*STAFF)
def update_inquiry(iid):
    i = db.get_or_404(Inquiry, iid)
    if g.user.role == "agent" and i.agent_id != g.user.id:
        return fail("Not allowed", 403)
    d = request.get_json(silent=True) or {}
    if "status" in d:
        if d["status"] not in LEAD_STATUSES:
            return fail("Invalid status")
        i.status = d["status"]
    if d.get("priority") in ("low", "medium", "high"):
        i.priority = d["priority"]
    if "follow_up_date" in d:
        i.follow_up_date = parse_date(d["follow_up_date"])
    if d.get("note"):
        stamp = datetime.utcnow().strftime("%d %b %H:%M")
        i.notes = (i.notes or "") + f"[{stamp} {g.user.name}] {d['note'][:500]}\n"
    if d.get("agent_id") and g.user.role in MANAGERS:
        ag = db.session.get(User, d["agent_id"])
        if not ag or ag.role != "agent":
            return fail("Invalid agent")
        i.agent_id = ag.id
        notify(ag.id, "Lead assigned to you", i.property.title, "/inquiries")
    audit("update_inquiry", "inquiry", i.id, i.status)
    db.session.commit()
    return ok(i.to_dict())


# ---------------- Appointments ----------------
def has_conflict(agent_id, when, exclude=None):
    if not agent_id:
        return False
    q = Appointment.query.filter(Appointment.agent_id == agent_id,
                                 Appointment.status.in_(("pending", "approved")),
                                 Appointment.scheduled_at > when - timedelta(minutes=60),
                                 Appointment.scheduled_at < when + timedelta(minutes=60))
    if exclude:
        q = q.filter(Appointment.id != exclude)
    return q.first() is not None


@bp.post("/appointments")
@roles_required()
def book():
    d = request.get_json(silent=True) or {}
    p = db.session.get(Property, d.get("property_id") or 0)
    when = parse_dt(d.get("scheduled_at"))
    if not p or p.approval != "approved":
        return fail("Property not found", 404)
    if not when or when <= datetime.now():
        return fail("Choose a future date and time", 422)
    if has_conflict(p.agent_id, when):
        return fail("The agent already has a visit at that time. Pick another slot.", 409)
    a = Appointment(property_id=p.id, user_id=g.user.id, agent_id=p.agent_id, scheduled_at=when,
                    note=(d.get("note") or "")[:300])
    db.session.add(a)
    db.session.flush()
    notify(p.agent_id, "Visit requested", f"{g.user.name} for {p.title} on {when:%d %b %H:%M}", "/appointments")
    db.session.commit()
    return ok(a.to_dict(), 201)


@bp.get("/appointments")
@roles_required()
def list_appointments():
    u, q = g.user, Appointment.query
    if u.role in MANAGERS:
        pass
    elif u.role == "agent":
        q = q.filter(Appointment.agent_id == u.id)
    elif u.role == "owner":
        q = q.join(Property).filter(Property.owner_id == u.id)
    else:
        q = q.filter(Appointment.user_id == u.id)
    return paginate(q.order_by(Appointment.scheduled_at.desc()), lambda a: a.to_dict())


@bp.patch("/appointments/<int:aid>")
@roles_required()
def update_appointment(aid):
    a = db.get_or_404(Appointment, aid)
    u, d = g.user, request.get_json(silent=True) or {}
    is_staff = u.role in MANAGERS or (u.role == "agent" and a.agent_id == u.id)
    if not (is_staff or a.user_id == u.id):
        return fail("Not allowed", 403)
    action = d.get("action")
    if action in ("approve", "complete") and not is_staff:
        return fail("Only the agent can do that", 403)
    if action == "approve":
        a.status = "approved"
    elif action == "complete":
        a.status = "completed"
    elif action == "cancel":
        a.status = "cancelled"
    elif action == "reschedule":
        when = parse_dt(d.get("scheduled_at"))
        if not when or when <= datetime.now():
            return fail("Choose a future date and time", 422)
        if has_conflict(a.agent_id, when, exclude=a.id):
            return fail("Agent is busy at that time", 409)
        a.scheduled_at, a.status = when, "pending"
    else:
        return fail("Unknown action")
    other = a.user_id if is_staff else a.agent_id
    notify(other, f"Visit {a.status}", f"{a.property.title} - {a.scheduled_at:%d %b %H:%M}", "/appointments")
    audit("appointment_" + action, "appointment", a.id)
    db.session.commit()
    return ok(a.to_dict())
