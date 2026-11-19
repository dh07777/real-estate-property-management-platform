from datetime import date, datetime
from flask import Blueprint, request, g
from ..extensions import db
from ..models import Offer, Deal, Milestone, Commission, Property
from ..utils import (ok, fail, roles_required, audit, notify, paginate, parse_date, num, get_setting,
                     MANAGERS)

bp = Blueprint("sales", __name__, url_prefix="/api")


def seller_side(u, p):
    return u.role in MANAGERS or (u.role == "agent" and p.agent_id == u.id) or (u.role == "owner" and p.owner_id == u.id)


def scoped(q, model, u):
    if u.role in MANAGERS:
        return q
    if u.role in ("agent", "owner"):
        col = Property.agent_id if u.role == "agent" else Property.owner_id
        return q.join(Property, model.property_id == Property.id).filter(col == u.id)
    return q.filter(model.buyer_id == u.id)


def make_deal(p, buyer_id, price):
    """Create a deal (caller commits). One active deal per property."""
    if Deal.query.filter(Deal.property_id == p.id, Deal.status.in_(("booked", "agreement"))).first() or p.status != "available":
        return None
    try:
        rate = float(get_setting("default_commission_rate", "2"))
    except ValueError:
        rate = 2.0
    d = Deal(property_id=p.id, buyer_id=buyer_id, agent_id=p.agent_id, price=price, commission_rate=rate)
    p.status = "booked"
    db.session.add(d)
    db.session.flush()
    return d


# ---------------- Offers ----------------
@bp.post("/offers")
@roles_required("buyer")
def submit_offer():
    d = request.get_json(silent=True) or {}
    p = db.session.get(Property, d.get("property_id") or 0)
    if not p or p.approval != "approved" or p.listing_type != "sale" or p.status != "available":
        return fail("This property is not open for offers", 409)
    try:
        amount = num(d.get("amount"), float, 1, 1e11)
    except (ValueError, TypeError):
        return fail("Enter a valid offer amount", 422)
    o = Offer(property_id=p.id, buyer_id=g.user.id, amount=amount, message=(d.get("message") or "")[:500])
    db.session.add(o)
    db.session.flush()
    for uid in (p.agent_id, p.owner_id):
        notify(uid, "New offer received", f"{g.user.name} offered Rs {amount:,.0f} on {p.title}", "/offers")
    audit("submit_offer", "offer", o.id)
    db.session.commit()
    return ok(o.to_dict(), 201)


@bp.get("/offers")
@roles_required()
def list_offers():
    return paginate(scoped(Offer.query, Offer, g.user).order_by(Offer.created_at.desc()), lambda o: o.to_dict())


@bp.patch("/offers/<int:oid>")
@roles_required()
def respond_offer(oid):
    o = db.get_or_404(Offer, oid)
    u, d = g.user, request.get_json(silent=True) or {}
    act, p = d.get("action"), o.property
    is_seller = seller_side(u, p)
    if not (is_seller or o.buyer_id == u.id):
        return fail("Not allowed", 403)
    if act in ("accept", "reject", "counter"):
        if not is_seller or o.status != "pending":
            return fail("Only the seller side can respond to a pending offer", 403 if not is_seller else 409)
        if act == "reject":
            o.status = "rejected"
        elif act == "counter":
            try:
                o.counter_amount = num(d.get("counter_amount"), float, 1, 1e11)
            except (ValueError, TypeError):
                return fail("Enter a valid counter amount", 422)
            o.status = "countered"
        else:
            deal = make_deal(p, o.buyer_id, o.amount)
            if not deal:
                return fail("Property already has an active deal", 409)
            o.status = "accepted"
        notify(o.buyer_id, f"Offer {o.status}", p.title, "/offers")
    elif act == "accept_counter":
        if o.buyer_id != u.id or o.status != "countered":
            return fail("No counter-offer to accept", 409)
        if not make_deal(p, o.buyer_id, o.counter_amount):
            return fail("Property already has an active deal", 409)
        o.status = "accepted"
        notify(p.agent_id, "Counter-offer accepted", p.title, "/deals")
    elif act == "withdraw":
        if o.buyer_id != u.id or o.status not in ("pending", "countered"):
            return fail("Cannot withdraw this offer", 409)
        o.status = "withdrawn"
    else:
        return fail("Unknown action")
    audit("offer_" + act, "offer", o.id)
    db.session.commit()
    return ok(o.to_dict())


# ---------------- Deals ----------------
@bp.get("/deals")
@roles_required()
def list_deals():
    return paginate(scoped(Deal.query, Deal, g.user).order_by(Deal.created_at.desc()), lambda d: d.to_dict())


def _deal(did, u, write=False):
    d = db.get_or_404(Deal, did)
    if write and not seller_side(u, d.property):
        return None
    if not write and not (seller_side(u, d.property) or d.buyer_id == u.id):
        return None
    return d


@bp.post("/deals/<int:did>/milestones")
@roles_required()
def add_milestone(did):
    d = _deal(did, g.user, write=True)
    if not d or d.status in ("completed", "cancelled"):
        return fail("Not allowed or deal closed", 403)
    b = request.get_json(silent=True) or {}
    try:
        amt = num(b.get("amount"), float, 1, 1e11)
    except (ValueError, TypeError):
        return fail("Invalid amount", 422)
    if not (b.get("title") or "").strip():
        return fail("Title required", 422)
    d.milestones.append(Milestone(title=b["title"].strip()[:120], amount=amt, due_date=parse_date(b.get("due_date"))))
    notify(d.buyer_id, "Payment milestone added", f"{b['title']}: Rs {amt:,.0f}", "/deals")
    db.session.commit()
    return ok(d.to_dict(), 201)


@bp.post("/milestones/<int:mid>/pay")
@roles_required()
def pay_milestone(mid):
    m = db.get_or_404(Milestone, mid)
    if not seller_side(g.user, m.deal.property):
        return fail("Not allowed", 403)
    if m.status == "paid" or m.deal.status in ("completed", "cancelled"):
        return fail("Already paid or deal closed", 409)
    m.status, m.paid_date = "paid", date.today()
    notify(m.deal.buyer_id, "Milestone payment recorded", m.title, "/deals")
    audit("pay_milestone", "deal", m.deal_id, f"{m.title} {m.amount}")
    db.session.commit()
    return ok(m.deal.to_dict())


@bp.patch("/deals/<int:did>")
@roles_required()
def update_deal(did):
    d = _deal(did, g.user, write=True)
    if not d:
        return fail("Not allowed", 403)
    b = request.get_json(silent=True) or {}
    act = b.get("action")
    if d.status in ("completed", "cancelled"):
        return fail("Deal is closed", 409)
    if act == "record_booking":
        try:
            d.booking_amount = num(b.get("amount"), float, 0, d.price)
        except (ValueError, TypeError):
            return fail("Booking amount must be between 0 and the deal price", 422)
    elif act == "agreement":
        d.status, d.agreement_date = "agreement", parse_date(b.get("date")) or date.today()
    elif act == "complete":
        if any(m.status != "paid" for m in d.milestones):
            return fail("Record all milestone payments before completing", 409)
        d.status, d.completed_at = "completed", datetime.utcnow()
        d.property.status = "sold"
        if d.agent_id:
            db.session.add(Commission(deal_id=d.id, agent_id=d.agent_id, amount=round(d.price * d.commission_rate / 100, 2)))
            notify(d.agent_id, "Deal completed: commission recorded", d.property.title, "/deals")
    elif act == "cancel":
        d.status, d.property.status = "cancelled", "available"
    else:
        return fail("Unknown action")
    notify(d.buyer_id, f"Deal {d.status}", d.property.title, "/deals")
    audit("deal_" + act, "deal", d.id)
    db.session.commit()
    return ok(d.to_dict())


# ---------------- Commissions ----------------
@bp.get("/commissions")
@roles_required(*MANAGERS, "agent")
def list_commissions():
    q = Commission.query
    if g.user.role == "agent":
        q = q.filter_by(agent_id=g.user.id)
    return paginate(q.order_by(Commission.created_at.desc()), lambda c: c.to_dict())


@bp.post("/commissions/<int:cid>/pay")
@roles_required(*MANAGERS)
def pay_commission(cid):
    c = db.get_or_404(Commission, cid)
    if c.status == "paid":
        return fail("Already paid", 409)
    c.status, c.paid_date = "paid", date.today()
    notify(c.agent_id, "Commission paid", f"Rs {c.amount:,.0f}", "/deals")
    audit("pay_commission", "commission", c.id)
    db.session.commit()
    return ok(c.to_dict())
