"""Create tables and load clearly-labelled DEMO data. Usage: python seed.py [--reset]"""
import sys, random
from datetime import date, datetime, timedelta
from dotenv import load_dotenv
load_dotenv()
from app import create_app
from app.extensions import db
from app.models import *
from app.routes.rentals import month_add
from flask import current_app
import os

DEMO_PASSWORD = "Demo@1234"
IMG = {"apartment": "photo-1545324418-cc1a3fa10c00", "villa": "photo-1512917774080-9991f1c4c750",
       "house": "photo-1564013799919-ab600027ffc6", "office": "photo-1486406146926-c627a92ad1ab",
       "commercial": "photo-1497366216548-37526070297c", "land": "photo-1500382017468-9049fed747ef"}
AMEN = ["Lift", "Gym", "Swimming Pool", "Power Backup", "Security", "Garden", "Clubhouse", "Covered Parking"]
SPOTS = [("Mumbai", "Maharashtra", "Bandra West", "400050"), ("Bengaluru", "Karnataka", "Indiranagar", "560038"),
         ("Pune", "Maharashtra", "Baner", "411045"), ("Hyderabad", "Telangana", "Gachibowli", "500032"),
         ("Delhi", "Delhi", "Dwarka", "110075"), ("Chennai", "Tamil Nadu", "Adyar", "600020"),
         ("Jaipur", "Rajasthan", "Malviya Nagar", "302017"), ("Ahmedabad", "Gujarat", "Satellite", "380015")]


def user(name, email, role, agency=None, phone="9800000000"):
    u = User(name=name, email=email, role=role, phone=phone, agency_id=agency, is_demo=True)
    u.set_password(DEMO_PASSWORD)
    db.session.add(u)
    return u


def run(reset=False):
    random.seed(7)
    if reset:
        db.drop_all()
    db.create_all()
    if User.query.first():
        print("Database already has data. Use --reset to rebuild.")
        return
    ag = Agency(name="Skyline Realty (DEMO)", city="Mumbai")
    db.session.add(ag); db.session.flush()
    admin = user("Aarav Admin", "admin@estateflow.demo", "super_admin")
    agency = user("Meera Kapoor", "agency@estateflow.demo", "agency_owner", ag.id)
    manager = user("Rohan Mehta", "manager@estateflow.demo", "property_manager", ag.id)
    agent = user("Priya Sharma", "agent@estateflow.demo", "agent", ag.id, "9811111111")
    agent2 = user("Vikram Rao", "agent2@estateflow.demo", "agent", ag.id, "9822222222")
    owner = user("Suresh Iyer", "owner@estateflow.demo", "owner")
    tenant = user("Ananya Nair", "tenant@estateflow.demo", "tenant")
    tenant2 = user("Karan Verma", "tenant2@estateflow.demo", "tenant")
    buyer = user("Neha Gupta", "buyer@estateflow.demo", "buyer")
    amen = [Amenity(name=a) for a in AMEN]
    db.session.add_all(amen); db.session.flush()

    props = []
    kinds = ["apartment", "villa", "house", "office", "commercial", "land"]
    for i in range(16):
        city, state, loc, pin = SPOTS[i % len(SPOTS)]
        kind, rent = kinds[i % 6], i % 3 != 0
        beds = 0 if kind in ("land", "office", "commercial") else random.choice([1, 2, 3, 4])
        area = random.choice([650, 900, 1200, 1800, 2400, 3500])
        p = Property(title=f"{beds or ''} {'BHK ' if beds else ''}{kind.title()} in {loc}".strip(),
                     description=f"DEMO LISTING. Well-maintained {kind} in {loc}, {city}. Close to schools, metro and markets.",
                     property_type=kind, listing_type="rent" if rent else "sale",
                     price=None if rent else area * random.choice([6500, 9000, 14000]),
                     monthly_rent=area * random.choice([25, 40, 60]) if rent else None,
                     address=f"{random.randint(1, 120)}, {loc} Main Road", city=city, state=state, postal_code=pin, locality=loc,
                     bedrooms=beds, bathrooms=max(beds - 1, 1) if beds else 1, balconies=random.randint(0, 3), area_sqft=area,
                     furnishing=random.choice(["unfurnished", "semi-furnished", "furnished"]), parking=random.randint(0, 2),
                     year_built=random.randint(2005, 2024), approval="approved" if i < 13 else "pending",
                     featured=i in (0, 1, 4), views=random.randint(5, 400),
                     cover_url=f"https://images.unsplash.com/{IMG[kind]}?w=900&q=70", owner_id=owner.id,
                     agent_id=(agent if i % 2 == 0 else agent2).id, is_demo=True,
                     created_at=datetime.utcnow() - timedelta(days=random.randint(0, 60)))
        p.amenities = random.sample(amen, 4)
        props.append(p); db.session.add(p)
    db.session.flush()

    def lease_for(prop, ten, months_ago):
        start = month_add(date.today(), -months_ago, 1).replace(day=1)
        end = month_add(start, 11, 1)
        l = Lease(property_id=prop.id, tenant_id=ten.id, start_date=start, end_date=end, monthly_rent=prop.monthly_rent,
                  security_deposit=prop.monthly_rent * 2, due_day=5, is_demo=True)
        db.session.add(l); db.session.flush()
        i = 0
        while (due := month_add(start, i, 5)) <= end:
            paid = due < date.today() - timedelta(days=20) or (due < date.today() and random.random() > .4)
            db.session.add(RentPayment(lease_id=l.id, due_date=due, amount=l.monthly_rent,
                                       status="paid" if paid else "pending", paid_date=due + timedelta(days=1) if paid else None,
                                       method="upi" if paid else None, reference=f"DEMO-{l.id}-{i}" if paid else None))
            i += 1
        prop.status = "rented"
        return l
    rentals = [p for p in props[:13] if p.listing_type == "rent"]
    lease_for(rentals[0], tenant, 5); lease_for(rentals[1], tenant2, 3)
    db.session.add(MaintenanceRequest(property_id=rentals[0].id, tenant_id=tenant.id, category="plumbing", priority="high",
                                      description="Kitchen tap leaking since two days (demo request).", status="in_progress", assigned_to="QuickFix Plumbers", cost=1800))
    db.session.add(MaintenanceRequest(property_id=rentals[1].id, tenant_id=tenant2.id, category="electrical", priority="medium",
                                      description="Bedroom fan makes noise (demo request).", status="open"))
    for i, st in enumerate(LEAD_STATUSES):
        p = props[i]
        db.session.add(Inquiry(property_id=p.id, user_id=buyer.id if i < 3 else None, agent_id=p.agent_id, name=buyer.name if i < 3 else f"Demo Lead {i}",
                               email=buyer.email if i < 3 else f"lead{i}@example.com", message="Is this still available? (demo)", status=st,
                               priority=random.choice(["low", "medium", "high"]), source=random.choice(["website", "referral", "walk-in"]),
                               follow_up_date=date.today() + timedelta(days=i)))
    for i in range(3):
        p = props[i + 1]
        db.session.add(Appointment(property_id=p.id, user_id=buyer.id, agent_id=p.agent_id,
                                   scheduled_at=datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=i + 1, hours=3),
                                   status="approved" if i == 0 else "pending"))

    # ---- Vendors, expenses, settings
    vendors = [Vendor(name="QuickFix Plumbers (DEMO)", category="plumbing", phone="9830000001", is_demo=True),
               Vendor(name="BrightSpark Electricals (DEMO)", category="electrical", phone="9830000002", is_demo=True),
               Vendor(name="CleanNest Services (DEMO)", category="cleaning", phone="9830000003", is_demo=True)]
    db.session.add_all(vendors)
    for k, v in {"platform_name": "EstateFlow", "default_commission_rate": "2", "allow_registration": "1",
                 "notifications_enabled": "1", "support_email": "support@estateflow.demo"}.items():
        db.session.add(Setting(key=k, value=v))
    for i, (cat, amt) in enumerate([("tax", 18000), ("insurance", 9500), ("marketing", 6000), ("utilities", 4200)]):
        db.session.add(Expense(property_id=props[i].id, category=cat, amount=amt, spent_on=date.today() - timedelta(days=20 * i + 5),
                               description="Demo expense", created_by=admin.id, is_demo=True))
    m1 = MaintenanceRequest.query.filter_by(category="plumbing").first()
    m1.cost_approved, m1.vendor_id = True, vendors[0].id

    # ---- Sales: offers, one active deal with milestones, one completed deal with commission
    sale = [p for p in props[:13] if p.listing_type == "sale" and p.status == "available"]
    d1 = Deal(property_id=sale[0].id, buyer_id=buyer.id, agent_id=sale[0].agent_id, price=sale[0].price, booking_amount=sale[0].price * .05,
              commission_rate=2, status="agreement", agreement_date=date.today() - timedelta(days=3), is_demo=True)
    d1.milestones = [Milestone(title="Second instalment", amount=sale[0].price * .25, due_date=date.today() + timedelta(days=15)),
                     Milestone(title="Final payment", amount=sale[0].price * .70, due_date=date.today() + timedelta(days=45))]
    sale[0].status = "booked"
    d2 = Deal(property_id=sale[1].id, buyer_id=buyer.id, agent_id=sale[1].agent_id, price=sale[1].price, booking_amount=sale[1].price * .1,
              commission_rate=2, status="completed", completed_at=datetime.utcnow() - timedelta(days=12), is_demo=True)
    d2.milestones = [Milestone(title="Balance payment", amount=sale[1].price * .9, status="paid", paid_date=date.today() - timedelta(days=12))]
    sale[1].status = "sold"
    db.session.add_all([d1, d2])
    db.session.flush()
    db.session.add(Commission(deal_id=d2.id, agent_id=d2.agent_id, amount=round(d2.price * .02, 2)))
    if len(sale) > 2:
        db.session.add(Offer(property_id=sale[2].id, buyer_id=buyer.id, amount=sale[2].price * .93, message="Demo offer, flexible on possession.", status="pending"))

    # ---- Reviews
    db.session.add(Review(property_id=rentals[0].id, user_id=tenant.id, agent_id=rentals[0].agent_id, rating=5, agent_rating=5,
                          comment="Great locality and a responsive agent. (demo review)", verified=True, is_demo=True))
    db.session.add(Review(property_id=sale[1].id, user_id=buyer.id, agent_id=sale[1].agent_id, rating=4, agent_rating=4,
                          comment="Smooth purchase process. (demo review)", verified=True, is_demo=True))

    # ---- Demo documents (tiny placeholder PDFs, stored privately)
    for title, cat, prop, vis, exp in [("Rental agreement (DEMO)", "rental_agreement", rentals[0], "parties", date.today() + timedelta(days=25)),
                                       ("Ownership deed (DEMO)", "ownership", rentals[0], "private", None)]:
        fname = f"demo-{cat}.pdf"
        with open(os.path.join(current_app.config["DOC_FOLDER"], fname), "wb") as fh:
            fh.write(b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\nDEMO DOCUMENT - not a real legal document\n")
        db.session.add(Document(title=title, category=cat, property_id=prop.id, uploaded_by=owner.id, filename=fname,
                                original_name=f"{cat}.pdf", size=100, visibility=vis, expires_on=exp, is_demo=True))
    db.session.add(Favorite(user_id=buyer.id, property_id=props[0].id))
    for u in (tenant, buyer, agent):
        db.session.add(Notification(user_id=u.id, title="Welcome to EstateFlow", body="All data here is DEMO data."))
    db.session.commit()
    print("Seeded DEMO data. Password for every demo user:", DEMO_PASSWORD)


if __name__ == "__main__":
    with create_app().app_context():
        run("--reset" in sys.argv)
