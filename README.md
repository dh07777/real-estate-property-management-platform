# EstateFlow - Real Estate Property Management Platform

Flask + SQLite backend, React (Vite) frontend. All numbers on dashboards and reports come from the database.
All seeded records are **DEMO data** (fictional people, listings and payments). Rent "payments" are
**manually recorded receipts**; no payment gateway is integrated.

## Run on Windows (VS Code + PowerShell)

Prerequisites: Python 3.11+ (tick "Add to PATH"), Node.js 18+ (LTS), VS Code.

### 1. Backend (terminal 1)
```powershell
cd estateflow\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope Process Bypass
pip install -r requirements.txt
copy .env.example .env                # then edit the two secret keys
python seed.py --reset                # (re)creates estateflow.db with DEMO data
python run.py                         # API on http://127.0.0.1:5000
```
API docs: http://127.0.0.1:5000/api/docs

### 2. Frontend (terminal 2)
```powershell
cd estateflow\frontend
npm install
npm run dev                           # http://localhost:5173
```

### 3. Sign in (password for all: `Demo@1234`)
admin@ / agency@ / manager@ / agent@ / owner@ / tenant@ / buyer@ `estateflow.demo`
(The login page has one-click buttons that fill these in.)

### Tests
```powershell
cd backend;  pytest                   # API, RBAC, IDOR, workflows, reports
cd ..\frontend; npm test              # component tests
```

### Useful commands
- `python init_db.py` - create tables without demo data
- `flask --app run.py send-reminders` - generate in-app rent-due/overdue/lease-expiry notifications (run daily with Windows Task Scheduler)
- Migrations: `flask --app run.py db init`, then `db migrate -m "msg"`, `db upgrade`

## Production
```powershell
pip install waitress
waitress-serve --listen=0.0.0.0:8000 run:app
```
Set strong `SECRET_KEY`/`JWT_SECRET_KEY`, `FLASK_DEBUG=0`, `CORS_ORIGINS` to your site, run `npm run build` and serve
`frontend/dist` (e.g. Nginx/Caddy or Render/Railway static site) with `/api` proxied to the backend.

## SQLite limits
SQLite allows one writer at a time, so it suits small/medium traffic. For heavy concurrent writes, switch
`DATABASE_URL` to PostgreSQL (SQLAlchemy models and Flask-Migrate carry over; add `psycopg2`).

## Modules (all 14 now implemented)
1. Role dashboards (admin, agent incl. commissions, owner, tenant, buyer incl. purchase progress)
2. Property management: CRUD, archive, approval workflow, featuring, image gallery upload
3. Discovery: filters, sort, pagination, favorites, share, similar properties, inquiries
4. Leads: pipeline (New to Lost), priority, source, follow-ups, notes, assignment
5. Visits: booking, approval, reschedule, cancel, conflict prevention
6. Rentals: leases, rent schedule, recorded payments, renewal, termination, overdue tracking
7. Sales: offers, counter-offers, deals, booking amount, payment milestones, agreement record, completion, commissions
8. Maintenance: requests, private photo upload, vendors, owner expense approval, analytics
9. Documents: private storage, magic-byte validation, permission checks, expiry reminders, activity history
10. Finance: income/expense ledger, expense categories, property-wise revenue, monthly summary, Excel/PDF export
11. Notifications: in-app centre, read/unread, `flask send-reminders` for rent, lease and document expiry
12. Reviews: property and agent ratings, verified-customer flag, reporting, moderation queue
13. Administration: users, suspension, roles, agencies, system settings, audit log
14. Reports: inventory, rentals, payments, maintenance, leads, deals, commissions, ledger, occupancy, lease expiry, appointments (JSON/Excel/PDF)

Limits to know: sale/rent "payments" are manual records (no gateway); password-reset tokens appear on screen only in
development because no email server is configured; logout is client-side; agency data scoping is not enforced
(all managers see all properties).

## Security notes
Passwords hashed (Werkzeug); JWT in `Authorization` header stored in localStorage (XSS-sensitive: React escapes output,
no raw HTML is rendered); server-side role checks on every endpoint; owner/tenant/agent scoping prevents IDOR;
field whitelists prevent mass assignment; uploads validated by magic bytes, renamed to UUIDs, 5 MB limit; rate limits on auth;
logout is client-side (tokens expire after 8 h; add a token blocklist for hard revocation).
