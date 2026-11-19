from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db

ROLES = ("super_admin", "agency_owner", "property_manager", "agent", "owner", "tenant", "buyer")
SELF_REGISTER_ROLES = ("owner", "tenant", "buyer")
PROPERTY_TYPES = ("apartment", "villa", "house", "commercial", "land", "office")
LEAD_STATUSES = ("New", "Contacted", "Interested", "Visit Scheduled", "Negotiation", "Converted", "Lost")


def now():
    return datetime.utcnow()


class Agency(db.Model):
    __tablename__ = "agencies"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    city = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=now, nullable=False)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, index=True)
    phone = db.Column(db.String(20))
    active = db.Column(db.Boolean, default=True, nullable=False)
    agency_id = db.Column(db.Integer, db.ForeignKey("agencies.id"))
    is_demo = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    def to_dict(self):
        return dict(id=self.id, name=self.name, email=self.email, role=self.role, phone=self.phone,
                    active=self.active, agency_id=self.agency_id, is_demo=self.is_demo,
                    created_at=self.created_at.isoformat())


property_amenities = db.Table(
    "property_amenities",
    db.Column("property_id", db.Integer, db.ForeignKey("properties.id", ondelete="CASCADE"), primary_key=True),
    db.Column("amenity_id", db.Integer, db.ForeignKey("amenities.id"), primary_key=True),
)


class Amenity(db.Model):
    __tablename__ = "amenities"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)


class Property(db.Model):
    __tablename__ = "properties"
    __table_args__ = (db.CheckConstraint("listing_type in ('sale','rent')"),)
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    property_type = db.Column(db.String(20), nullable=False, index=True)
    listing_type = db.Column(db.String(10), nullable=False, index=True)
    price = db.Column(db.Float)          # sale price (INR)
    monthly_rent = db.Column(db.Float)   # INR / month
    address = db.Column(db.String(200))
    city = db.Column(db.String(80), index=True)
    state = db.Column(db.String(80))
    postal_code = db.Column(db.String(10))
    locality = db.Column(db.String(80))
    bedrooms = db.Column(db.Integer, default=0)
    bathrooms = db.Column(db.Integer, default=0)
    balconies = db.Column(db.Integer, default=0)
    area_sqft = db.Column(db.Float)
    furnishing = db.Column(db.String(20), default="unfurnished")
    parking = db.Column(db.Integer, default=0)
    year_built = db.Column(db.Integer)
    status = db.Column(db.String(15), default="available", nullable=False, index=True)  # available/sold/rented/archived
    approval = db.Column(db.String(15), default="pending", nullable=False, index=True)  # pending/approved/rejected
    featured = db.Column(db.Boolean, default=False)
    views = db.Column(db.Integer, default=0)
    cover_url = db.Column(db.String(300))
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    agent_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    is_demo = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    owner = db.relationship("User", foreign_keys=[owner_id])
    agent = db.relationship("User", foreign_keys=[agent_id])
    images = db.relationship("PropertyImage", cascade="all, delete-orphan", backref="property")
    amenities = db.relationship("Amenity", secondary=property_amenities)

    def to_dict(self, detail=False):
        imgs = [f"/api/uploads/{i.filename}" for i in self.images]
        d = dict(id=self.id, title=self.title, property_type=self.property_type, listing_type=self.listing_type,
                 price=self.price, monthly_rent=self.monthly_rent, city=self.city, locality=self.locality,
                 bedrooms=self.bedrooms, bathrooms=self.bathrooms, area_sqft=self.area_sqft,
                 furnishing=self.furnishing, status=self.status, approval=self.approval, featured=self.featured,
                 views=self.views, cover=(imgs[0] if imgs else self.cover_url), is_demo=self.is_demo,
                 created_at=self.created_at.isoformat(), owner_id=self.owner_id, agent_id=self.agent_id)
        if detail:
            d.update(description=self.description, address=self.address, state=self.state,
                     postal_code=self.postal_code, balconies=self.balconies, parking=self.parking,
                     year_built=self.year_built, images=imgs, amenities=[a.name for a in self.amenities],
                     owner_name=self.owner.name if self.owner else None,
                     agent=dict(id=self.agent.id, name=self.agent.name, phone=self.agent.phone)
                     if self.agent else None)
        return d


class PropertyImage(db.Model):
    __tablename__ = "property_images"
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False)
    filename = db.Column(db.String(80), nullable=False)


class Favorite(db.Model):
    __tablename__ = "favorites"
    __table_args__ = (db.UniqueConstraint("user_id", "property_id"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=False)


class Inquiry(db.Model):  # an inquiry is also the lead record
    __tablename__ = "inquiries"
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    agent_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(20))
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="New", nullable=False)
    priority = db.Column(db.String(10), default="medium")
    source = db.Column(db.String(30), default="website")
    follow_up_date = db.Column(db.Date)
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    property = db.relationship("Property")

    def to_dict(self):
        return dict(id=self.id, property_id=self.property_id, property_title=self.property.title,
                    user_id=self.user_id, agent_id=self.agent_id, name=self.name, email=self.email,
                    phone=self.phone, message=self.message, status=self.status, priority=self.priority,
                    source=self.source, follow_up_date=self.follow_up_date.isoformat() if self.follow_up_date else None,
                    notes=self.notes, created_at=self.created_at.isoformat())


class Appointment(db.Model):
    __tablename__ = "appointments"
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    agent_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    scheduled_at = db.Column(db.DateTime, nullable=False, index=True)
    status = db.Column(db.String(15), default="pending", nullable=False)  # pending/approved/cancelled/completed
    note = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    property = db.relationship("Property")
    user = db.relationship("User", foreign_keys=[user_id])

    def to_dict(self):
        return dict(id=self.id, property_id=self.property_id, property_title=self.property.title,
                    user_id=self.user_id, visitor=self.user.name, agent_id=self.agent_id,
                    scheduled_at=self.scheduled_at.isoformat(), status=self.status, note=self.note)


class Lease(db.Model):
    __tablename__ = "leases"
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=False, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    monthly_rent = db.Column(db.Float, nullable=False)
    security_deposit = db.Column(db.Float, default=0)
    due_day = db.Column(db.Integer, default=5)
    status = db.Column(db.String(15), default="active", nullable=False)  # active/terminated/expired
    is_demo = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    property = db.relationship("Property")
    tenant = db.relationship("User", foreign_keys=[tenant_id])
    payments = db.relationship("RentPayment", backref="lease", cascade="all, delete-orphan")

    def to_dict(self):
        return dict(id=self.id, property_id=self.property_id, property_title=self.property.title,
                    tenant_id=self.tenant_id, tenant_name=self.tenant.name, start_date=self.start_date.isoformat(),
                    end_date=self.end_date.isoformat(), monthly_rent=self.monthly_rent,
                    security_deposit=self.security_deposit, due_day=self.due_day, status=self.status,
                    is_demo=self.is_demo)


class RentPayment(db.Model):
    """A *recorded* rent payment. No online gateway is integrated: staff/owner record receipts manually."""
    __tablename__ = "rent_payments"
    id = db.Column(db.Integer, primary_key=True)
    lease_id = db.Column(db.Integer, db.ForeignKey("leases.id", ondelete="CASCADE"), nullable=False, index=True)
    due_date = db.Column(db.Date, nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(15), default="pending", nullable=False)  # pending/paid/cancelled
    paid_date = db.Column(db.Date)
    method = db.Column(db.String(20))      # cash/bank_transfer/upi/cheque
    reference = db.Column(db.String(60))
    recorded_by = db.Column(db.Integer, db.ForeignKey("users.id"))

    @property
    def display_status(self):
        if self.status == "pending" and self.due_date < date.today():
            return "overdue"
        return self.status

    def to_dict(self):
        return dict(id=self.id, lease_id=self.lease_id, property_title=self.lease.property.title,
                    tenant_name=self.lease.tenant.name, due_date=self.due_date.isoformat(), amount=self.amount,
                    status=self.display_status, paid_date=self.paid_date.isoformat() if self.paid_date else None,
                    method=self.method, reference=self.reference, entry="recorded payment (manual)")


class MaintenanceRequest(db.Model):
    __tablename__ = "maintenance_requests"
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=False, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    category = db.Column(db.String(30), nullable=False)
    priority = db.Column(db.String(10), default="medium")
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(15), default="open", nullable=False)  # open/assigned/in_progress/resolved/closed
    assigned_to = db.Column(db.String(120))
    cost = db.Column(db.Float, default=0)
    cost_approved = db.Column(db.Boolean, default=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"))
    image = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    property = db.relationship("Property")
    vendor = db.relationship("Vendor")
    tenant = db.relationship("User", foreign_keys=[tenant_id])

    def to_dict(self):
        return dict(id=self.id, property_id=self.property_id, property_title=self.property.title,
                    tenant_name=self.tenant.name, category=self.category, priority=self.priority,
                    description=self.description, status=self.status, assigned_to=self.assigned_to,
                    cost=self.cost, cost_approved=self.cost_approved, created_at=self.created_at.isoformat(),
                    vendor_id=self.vendor_id, vendor_name=self.vendor.name if self.vendor else None, has_image=bool(self.image))


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.String(400))
    link = db.Column(db.String(120))
    read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)

    def to_dict(self):
        return dict(id=self.id, title=self.title, body=self.body, link=self.link, read=self.read,
                    created_at=self.created_at.isoformat())


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    action = db.Column(db.String(60), nullable=False)
    entity = db.Column(db.String(40))
    entity_id = db.Column(db.Integer)
    detail = db.Column(db.String(500))
    ip = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=now, nullable=False, index=True)
    user = db.relationship("User")

    def to_dict(self):
        return dict(id=self.id, user=self.user.name if self.user else None, action=self.action,
                    entity=self.entity, entity_id=self.entity_id, detail=self.detail,
                    created_at=self.created_at.isoformat())


class Vendor(db.Model):
    __tablename__ = "vendors"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(30), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(160))
    active = db.Column(db.Boolean, default=True, nullable=False)
    is_demo = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return dict(id=self.id, name=self.name, category=self.category, phone=self.phone, email=self.email,
                    active=self.active, is_demo=self.is_demo)


class Offer(db.Model):
    __tablename__ = "offers"
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=False, index=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    message = db.Column(db.String(500))
    status = db.Column(db.String(15), default="pending", nullable=False)  # pending/accepted/rejected/countered/withdrawn
    counter_amount = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    property = db.relationship("Property")
    buyer = db.relationship("User", foreign_keys=[buyer_id])

    def to_dict(self):
        return dict(id=self.id, property_id=self.property_id, property_title=self.property.title,
                    listed_price=self.property.price, buyer_id=self.buyer_id, buyer_name=self.buyer.name,
                    amount=self.amount, message=self.message, status=self.status,
                    counter_amount=self.counter_amount, created_at=self.created_at.isoformat())


class Deal(db.Model):
    __tablename__ = "sales_deals"
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=False, index=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    agent_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    price = db.Column(db.Float, nullable=False)
    booking_amount = db.Column(db.Float, default=0)
    commission_rate = db.Column(db.Float, default=2)
    status = db.Column(db.String(15), default="booked", nullable=False)  # booked/agreement/completed/cancelled
    agreement_date = db.Column(db.Date)
    completed_at = db.Column(db.DateTime)
    is_demo = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    property = db.relationship("Property")
    buyer = db.relationship("User", foreign_keys=[buyer_id])
    milestones = db.relationship("Milestone", backref="deal", cascade="all, delete-orphan", order_by="Milestone.due_date")

    def to_dict(self):
        paid = (self.booking_amount or 0) + sum(m.amount for m in self.milestones if m.status == "paid")
        return dict(id=self.id, property_id=self.property_id, property_title=self.property.title, buyer_id=self.buyer_id,
                    buyer_name=self.buyer.name, agent_id=self.agent_id, price=self.price, booking_amount=self.booking_amount,
                    commission_rate=self.commission_rate, status=self.status, paid_total=paid, balance=self.price - paid,
                    agreement_date=self.agreement_date.isoformat() if self.agreement_date else None,
                    completed_at=self.completed_at.isoformat() if self.completed_at else None, is_demo=self.is_demo,
                    milestones=[m.to_dict() for m in self.milestones])


class Milestone(db.Model):
    __tablename__ = "deal_milestones"
    id = db.Column(db.Integer, primary_key=True)
    deal_id = db.Column(db.Integer, db.ForeignKey("sales_deals.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date)
    paid_date = db.Column(db.Date)
    status = db.Column(db.String(10), default="pending", nullable=False)

    def to_dict(self):
        return dict(id=self.id, title=self.title, amount=self.amount, status=self.status,
                    due_date=self.due_date.isoformat() if self.due_date else None,
                    paid_date=self.paid_date.isoformat() if self.paid_date else None)


class Commission(db.Model):
    __tablename__ = "commissions"
    id = db.Column(db.Integer, primary_key=True)
    deal_id = db.Column(db.Integer, db.ForeignKey("sales_deals.id"), nullable=False, index=True)
    agent_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(10), default="pending", nullable=False)
    paid_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    deal = db.relationship("Deal")
    agent = db.relationship("User", foreign_keys=[agent_id])

    def to_dict(self):
        return dict(id=self.id, deal_id=self.deal_id, property_title=self.deal.property.title, agent_name=self.agent.name,
                    agent_id=self.agent_id, amount=self.amount, rate=self.deal.commission_rate, status=self.status,
                    paid_date=self.paid_date.isoformat() if self.paid_date else None, created_at=self.created_at.isoformat())


class Expense(db.Model):
    __tablename__ = "expenses"
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), index=True)
    category = db.Column(db.String(30), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    spent_on = db.Column(db.Date, nullable=False, index=True)
    description = db.Column(db.String(300))
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    is_demo = db.Column(db.Boolean, default=False)
    property = db.relationship("Property")

    def to_dict(self):
        return dict(id=self.id, property_id=self.property_id, property_title=self.property.title if self.property else None,
                    category=self.category, amount=self.amount, spent_on=self.spent_on.isoformat(), description=self.description)


class Document(db.Model):
    __tablename__ = "documents"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(30), nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), index=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    filename = db.Column(db.String(80), nullable=False)       # stored name (uuid)
    original_name = db.Column(db.String(160), nullable=False)
    size = db.Column(db.Integer)
    visibility = db.Column(db.String(10), default="private", nullable=False)  # private / parties
    expires_on = db.Column(db.Date)
    is_demo = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    property = db.relationship("Property")
    uploader = db.relationship("User", foreign_keys=[uploaded_by])

    def to_dict(self):
        return dict(id=self.id, title=self.title, category=self.category, property_id=self.property_id,
                    property_title=self.property.title if self.property else None, uploaded_by=self.uploader.name,
                    original_name=self.original_name, size=self.size, visibility=self.visibility,
                    expires_on=self.expires_on.isoformat() if self.expires_on else None, is_demo=self.is_demo,
                    created_at=self.created_at.isoformat())


class DocumentActivity(db.Model):
    __tablename__ = "document_activity"
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    user = db.relationship("User")


class Review(db.Model):
    __tablename__ = "reviews"
    __table_args__ = (db.UniqueConstraint("user_id", "property_id"), db.CheckConstraint("rating between 1 and 5"))
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    rating = db.Column(db.Integer, nullable=False)
    agent_rating = db.Column(db.Integer)
    comment = db.Column(db.String(1000))
    verified = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(10), default="published", nullable=False)  # published/reported/hidden
    report_reason = db.Column(db.String(200))
    is_demo = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    user = db.relationship("User", foreign_keys=[user_id])
    property = db.relationship("Property")

    def to_dict(self):
        return dict(id=self.id, property_id=self.property_id, property_title=self.property.title,
                    reviewer=self.user.name.split()[0], rating=self.rating, agent_rating=self.agent_rating,
                    comment=self.comment, verified=self.verified, status=self.status,
                    report_reason=self.report_reason, created_at=self.created_at.isoformat())


class Setting(db.Model):
    __tablename__ = "settings"
    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.String(300))
