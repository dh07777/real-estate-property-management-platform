from datetime import datetime, timedelta


def test_login_and_bad_password(client):
    assert client.post("/api/auth/login", json={"email": "admin@estateflow.demo", "password": "x"}).status_code == 401


def test_register_cannot_pick_admin_role(client):
    r = client.post("/api/auth/register", json={"name": "Eve", "email": "eve@x.com", "password": "Passw0rdX", "role": "super_admin"})
    assert r.status_code == 403


def test_protected_route_needs_token(client):
    assert client.get("/api/dashboard").status_code == 401


def test_rbac_tenant_cannot_list_users_or_create_property(client, login):
    h = login("tenant")
    assert client.get("/api/admin/users", headers=h).status_code == 403
    assert client.post("/api/properties", headers=h, json={"title": "x"}).status_code == 403


def test_public_listing_hides_pending_and_filters(client):
    r = client.get("/api/properties?per_page=50").get_json()
    assert r["success"] and all(p["approval"] == "approved" for p in r["data"])
    r2 = client.get("/api/properties?listing_type=rent&sort=price_desc").get_json()
    assert all(p["listing_type"] == "rent" for p in r2["data"])


def test_owner_property_needs_approval_then_manager_approves(client, login):
    h = login("owner")
    r = client.post("/api/properties", headers=h, json={"title": "Test Flat", "property_type": "apartment", "listing_type": "sale",
                                                         "city": "Pune", "price": 5000000, "approval": "approved"})
    assert r.status_code == 201 and r.get_json()["data"]["approval"] == "pending"  # mass assignment blocked
    pid = r.get_json()["data"]["id"]
    assert client.post(f"/api/properties/{pid}/review", headers=h, json={"decision": "approved"}).status_code == 403
    assert client.post(f"/api/properties/{pid}/review", headers=login("manager"), json={"decision": "approved"}).status_code == 200


def test_invalid_property_rejected(client, login):
    r = client.post("/api/properties", headers=login("manager"), json={"title": "x", "property_type": "castle", "listing_type": "sale", "city": "A"})
    assert r.status_code == 422


def test_appointment_conflict(client, login):
    prop = next(p for p in client.get("/api/properties?per_page=50").get_json()["data"] if p["agent_id"])
    when = (datetime.now() + timedelta(days=30)).replace(minute=0, second=0, microsecond=0).isoformat()
    body = {"property_id": prop["id"], "scheduled_at": when}
    assert client.post("/api/appointments", headers=login("buyer"), json=body).status_code == 201
    assert client.post("/api/appointments", headers=login("tenant"), json=body).status_code == 409


def test_tenant_only_sees_own_lease_and_payments(client, login):
    mine = client.get("/api/leases", headers=login("tenant")).get_json()["data"]
    other = client.get("/api/leases", headers=login("tenant2")).get_json()["data"]
    assert len(mine) == 1 and len(other) == 1 and mine[0]["id"] != other[0]["id"]
    pays = client.get("/api/payments?per_page=100", headers=login("tenant")).get_json()["data"]
    assert pays and all(p["tenant_name"] == "Ananya Nair" for p in pays)


def test_tenant_cannot_record_payment_but_manager_can(client, login):
    pay = next(p for p in client.get("/api/payments?status=pending&per_page=100", headers=login("manager")).get_json()["data"])
    assert client.post(f"/api/payments/{pay['id']}/record", headers=login("tenant"), json={"method": "upi"}).status_code == 403
    r = client.post(f"/api/payments/{pay['id']}/record", headers=login("manager"), json={"method": "upi", "reference": "T1"})
    assert r.status_code == 200 and r.get_json()["data"]["status"] == "paid"


def test_notification_idor(client, login):
    n = client.get("/api/notifications", headers=login("tenant")).get_json()["data"][0]
    assert client.post(f"/api/notifications/{n['id']}/read", headers=login("buyer")).status_code == 404


def test_maintenance_flow(client, login):
    r = client.post("/api/maintenance", headers=login("tenant"), json={"category": "plumbing", "description": "Leaking sink"})
    assert r.status_code == 201
    assert client.post("/api/maintenance", headers=login("buyer"), json={"category": "plumbing", "description": "Leaking sink"}).status_code == 403


def test_dashboards_and_reports(client, login):
    for role, kind in [("admin", "admin"), ("agent", "agent"), ("owner", "owner"), ("tenant", "tenant"), ("buyer", "buyer")]:
        assert client.get("/api/dashboard", headers=login(role)).get_json()["data"]["kind"] == kind
    h = login("manager")
    assert client.get("/api/reports/inventory", headers=h).status_code == 200
    assert client.get("/api/reports/payments?format=xlsx", headers=h).status_code == 200
    assert client.get("/api/reports/payments?format=pdf", headers=h).status_code == 200
    assert client.get("/api/reports/inventory", headers=login("tenant")).status_code == 403


def test_deactivated_user_blocked(client, login):
    admin = login("admin")
    uid = client.get("/api/admin/users?q=buyer", headers=admin).get_json()["data"][0]["id"]
    buyer = login("buyer")
    assert client.patch(f"/api/admin/users/{uid}", headers=admin, json={"active": False}).status_code == 200
    assert client.get("/api/auth/me", headers=buyer).status_code == 401


def test_upload_rejects_non_image(client, login):
    import io
    pid = client.get("/api/properties").get_json()["data"][0]["id"]
    r = client.post(f"/api/properties/{pid}/images", headers=login("manager"),
                    data={"image": (io.BytesIO(b"<script>alert(1)</script>"), "x.png")}, content_type="multipart/form-data")
    assert r.status_code == 415
