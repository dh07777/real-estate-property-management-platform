import os
from datetime import timedelta
from flask import Flask, jsonify
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.exceptions import HTTPException
from .extensions import db, migrate, jwt, cors, limiter
from .utils import fail


@event.listens_for(Engine, "connect")
def _sqlite_fk(dbapi_conn, _):
    # enforce foreign keys in SQLite
    try:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()
    except Exception:
        pass


def create_app(config=None):
    app = Flask(__name__)
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-only-change-me"),
        JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY", "dev-only-jwt-change-me"),
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///" + os.path.join(base, "estateflow.db")),
        UPLOAD_FOLDER=os.path.join(base, "uploads"),
        DOC_FOLDER=os.path.join(base, "private_docs"),  # never served statically
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(hours=8),
        RATELIMIT_ENABLED=True,
        EXPOSE_RESET_TOKEN=os.getenv("FLASK_DEBUG") == "1",  # no email server: token shown only in dev
    )
    if config:
        app.config.update(config)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["DOC_FOLDER"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)
    origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    cors.init_app(app, resources={r"/api/*": {"origins": origins}})

    from .routes import auth, properties, leads, rentals, dashboard, admin, notifications, docs, sales, documents, reviews, finance, extras
    for m in (auth, properties, leads, rentals, dashboard, admin, notifications, docs, sales, documents, reviews, finance, extras):
        app.register_blueprint(m.bp)

    @app.errorhandler(HTTPException)
    def http_err(e):
        return fail(e.description, e.code)

    @app.errorhandler(Exception)
    def any_err(e):
        app.logger.exception(e)
        db.session.rollback()
        return fail("Internal server error", 500)

    @jwt.unauthorized_loader
    def _u(msg):
        return fail("Authentication required", 401)

    @jwt.invalid_token_loader
    def _i(msg):
        return fail("Invalid token", 401)

    @jwt.expired_token_loader
    def _e(h, p):
        return fail("Session expired, please sign in again", 401)

    @app.after_request
    def headers(r):
        r.headers["X-Content-Type-Options"] = "nosniff"
        r.headers["X-Frame-Options"] = "DENY"
        return r

    @app.cli.command("send-reminders")
    def send_reminders():
        """Create in-app rent due/overdue and lease expiry reminders (run daily via Task Scheduler/cron)."""
        from datetime import date, timedelta
        from .models import RentPayment, Lease
        from .utils import notify
        t, n = date.today(), 0
        for p in RentPayment.query.filter_by(status="pending"):
            if p.due_date == t + timedelta(days=3) or p.due_date < t:
                kind = "overdue" if p.due_date < t else "due soon"
                notify(p.lease.tenant_id, f"Rent {kind}", f"Rs {p.amount:,.0f} due {p.due_date:%d %b}", "/rentals")
                n += 1
        for l in Lease.query.filter_by(status="active"):
            if (l.end_date - t).days in (30, 7):
                notify(l.tenant_id, "Lease expiring soon", l.property.title, "/rentals")
                notify(l.property.owner_id, "Lease expiring soon", l.property.title, "/rentals")
                n += 1
        from .models import Document
        for d in Document.query.filter(Document.expires_on.isnot(None)):
            if (d.expires_on - t).days in (30, 7, 0):
                notify(d.uploaded_by, "Document expiring", f"{d.title} expires {d.expires_on:%d %b %Y}", "/documents")
                n += 1
        db.session.commit()
        print(f"Created {n} reminders")

    @app.get("/api/health")
    def health():
        return jsonify(success=True, data={"status": "ok"})

    return app
