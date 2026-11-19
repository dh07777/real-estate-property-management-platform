from collections import defaultdict
from datetime import date, timedelta
from flask import Blueprint, request, g
from ..extensions import db
from ..models import RentPayment, Lease, Deal, Commission, Expense, MaintenanceRequest, Property
from ..utils import ok, fail, roles_required, audit, parse_date, num, paginate, MANAGERS

bp = Blueprint("finance", __name__, url_prefix="/api")
EXPENSE_CATEGORIES = ("tax", "utilities", "insurance", "repairs", "marketing", "management_fee", "other")


def scope_ids(u):
    """None = every property (managers). Otherwise the owner's property ids."""
    if u.role in MANAGERS:
        return None
    return [p.id for p in Property.query.filter_by(owner_id=u.id)]


def in_scope(ids, pid):
    return ids is None or pid in ids


def date_range():
    end = parse_date(request.args.get("to")) or date.today()
    start = parse_date(request.args.get("from")) or end - timedelta(days=365)
    return start, end


def ledger_entries(ids, start, end):
    E = []
    add = lambda d, t, c, prop, amt, ref="": E.append(dict(date=d.isoformat(), type=t, category=c, property=prop, amount=round(amt, 2), reference=ref))
    for p in RentPayment.query.filter_by(status="paid"):
        if p.paid_date and start <= p.paid_date <= end and in_scope(ids, p.lease.property_id):
            add(p.paid_date, "income", "rent (recorded)", p.lease.property.title, p.amount, p.reference or "")
    for d in Deal.query.filter_by(status="completed"):
        if d.completed_at and start <= d.completed_at.date() <= end and in_scope(ids, d.property_id):
            add(d.completed_at.date(), "income", "sale (recorded)", d.property.title, d.price, f"deal #{d.id}")
    for l in Lease.query.filter(Lease.status != "terminated"):
        if start <= l.start_date <= end and in_scope(ids, l.property_id):
            add(l.start_date, "deposit", "security deposit (held)", l.property.title, l.security_deposit or 0, f"lease #{l.id}")
    for m in MaintenanceRequest.query.filter_by(cost_approved=True):
        if start <= m.created_at.date() <= end and in_scope(ids, m.property_id):
            add(m.created_at.date(), "expense", "maintenance", m.property.title, m.cost or 0, f"request #{m.id}")
    for e in Expense.query:
        if start <= e.spent_on <= end and (ids is None or e.property_id in ids):
            add(e.spent_on, "expense", e.category, e.property.title if e.property else "General", e.amount, e.description or "")
    for c in Commission.query:
        if start <= c.created_at.date() <= end and in_scope(ids, c.deal.property_id):
            add(c.created_at.date(), "expense", "agent commission", c.deal.property.title, c.amount, f"{c.agent.name} ({c.status})")
    return sorted(E, key=lambda x: x["date"], reverse=True)


@bp.get("/finance/summary")
@roles_required(*MANAGERS, "owner")
def summary():
    ids = scope_ids(g.user)
    start, end = date_range()
    E = ledger_entries(ids, start, end)
    tot = lambda t: round(sum(e["amount"] for e in E if e["type"] == t), 2)
    monthly = defaultdict(lambda: {"income": 0, "expense": 0})
    by_prop, by_cat = defaultdict(float), defaultdict(float)
    for e in E:
        m = e["date"][:7]
        if e["type"] in ("income", "expense"):
            monthly[m][e["type"]] += e["amount"]
        if e["type"] == "income":
            by_prop[e["property"]] += e["amount"]
        if e["type"] == "expense":
            by_cat[e["category"]] += e["amount"]
    pend = RentPayment.query.join(Lease).filter(RentPayment.status == "pending", RentPayment.due_date < date.today())
    if ids is not None:
        pend = pend.filter(Lease.property_id.in_(ids or [0]))
    income, expense = tot("income"), tot("expense")
    return ok(dict(
        range=dict(start=start.isoformat(), end=end.isoformat()), income=income, expense=expense, net=round(income - expense, 2),
        security_deposits_held=tot("deposit"), outstanding_rent=round(sum(p.amount for p in pend), 2),
        monthly=[dict(month=k, **{a: round(b, 2) for a, b in v.items()}) for k, v in sorted(monthly.items())],
        by_property=sorted([{"property": k, "income": round(v, 2)} for k, v in by_prop.items()], key=lambda x: -x["income"])[:10],
        by_category=sorted([{"category": k, "amount": round(v, 2)} for k, v in by_cat.items()], key=lambda x: -x["amount"]),
        note="Figures are manually recorded entries. Security deposits are held for tenants and excluded from income."))


@bp.get("/finance/ledger")
@roles_required(*MANAGERS, "owner")
def ledger():
    start, end = date_range()
    rows = ledger_entries(scope_ids(g.user), start, end)
    page, per = max(request.args.get("page", 1, type=int), 1), 20
    return ok(rows[(page - 1) * per: page * per], page=page, per_page=per, total=len(rows), pages=max(-(-len(rows) // per), 1))


@bp.get("/maintenance/analytics")
@roles_required(*MANAGERS, "owner")
def maintenance_analytics():
    ids = scope_ids(g.user)
    q = MaintenanceRequest.query
    if ids is not None:
        q = q.filter(MaintenanceRequest.property_id.in_(ids or [0]))
    cat, st = defaultdict(lambda: {"count": 0, "cost": 0.0}), defaultdict(int)
    for m in q:
        cat[m.category]["count"] += 1
        cat[m.category]["cost"] += (m.cost or 0) if m.cost_approved else 0
        st[m.status] += 1
    return ok(dict(by_category=[{"category": k, **v} for k, v in cat.items()], by_status=[{"status": k, "count": v} for k, v in st.items()]))


@bp.post("/expenses")
@roles_required(*MANAGERS, "owner")
def add_expense():
    d = request.get_json(silent=True) or {}
    ids = scope_ids(g.user)
    pid = d.get("property_id")
    if pid and (not db.session.get(Property, pid) or not in_scope(ids, pid)):
        return fail("Property not found", 404)
    if ids is not None and not pid:
        return fail("Choose one of your properties", 422)
    try:
        amt = num(d.get("amount"), float, 0.01, 1e9)
    except (ValueError, TypeError):
        return fail("Invalid amount", 422)
    if d.get("category") not in EXPENSE_CATEGORIES:
        return fail("Invalid category", 422)
    e = Expense(property_id=pid, category=d["category"], amount=amt, spent_on=parse_date(d.get("spent_on")) or date.today(),
                description=(d.get("description") or "")[:300], created_by=g.user.id)
    db.session.add(e)
    audit("add_expense", "expense", None, f"{e.category} {amt}")
    db.session.commit()
    return ok(e.to_dict(), 201)


@bp.get("/expenses")
@roles_required(*MANAGERS, "owner")
def list_expenses():
    ids = scope_ids(g.user)
    q = Expense.query
    if ids is not None:
        q = q.filter(Expense.property_id.in_(ids or [0]))
    return paginate(q.order_by(Expense.spent_on.desc()), lambda e: e.to_dict())


@bp.delete("/expenses/<int:eid>")
@roles_required(*MANAGERS, "owner")
def delete_expense(eid):
    e = db.get_or_404(Expense, eid)
    if not (g.user.role in MANAGERS or e.created_by == g.user.id):
        return fail("Not found", 404)
    db.session.delete(e)
    audit("delete_expense", "expense", eid)
    db.session.commit()
    return ok({"message": "Expense deleted"})
