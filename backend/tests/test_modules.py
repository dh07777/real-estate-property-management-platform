import io


def _sale_prop(client):
    return next(p for p in client.get("/api/properties?listing_type=sale&per_page=50").get_json()["data"] if p["status"] == "available")


def test_offer_counter_accept_deal_complete_commission(client, login):
    p = _sale_prop(client)
    buyer, mgr = login("buyer"), login("manager")
    o = client.post("/api/offers", headers=buyer, json={"property_id": p["id"], "amount": 4000000}).get_json()["data"]
    assert client.post("/api/offers", headers=login("tenant"), json={"property_id": p["id"], "amount": 1}).status_code == 403
    assert client.patch(f"/api/offers/{o['id']}", headers=buyer, json={"action": "accept"}).status_code == 403  # buyer cannot accept own offer
    r = client.patch(f"/api/offers/{o['id']}", headers=mgr, json={"action": "counter", "counter_amount": 4200000})
    assert r.get_json()["data"]["status"] == "countered"
    assert client.patch(f"/api/offers/{o['id']}", headers=buyer, json={"action": "accept_counter"}).status_code == 200
    deal = client.get("/api/deals", headers=buyer).get_json()["data"]
    deal = next(d for d in deal if d["property_id"] == p["id"])
    assert deal["price"] == 4200000 and deal["status"] == "booked"
    ms = client.post(f"/api/deals/{deal['id']}/milestones", headers=mgr, json={"title": "Balance", "amount": 4000000}).get_json()["data"]["milestones"]
    assert client.post(f"/api/milestones/{ms[0]['id']}/pay", headers=buyer).status_code == 403
    assert client.patch(f"/api/deals/{deal['id']}", headers=mgr, json={"action": "complete"}).status_code == 409  # milestone unpaid
    assert client.post(f"/api/milestones/{ms[0]['id']}/pay", headers=mgr).status_code == 200
    done = client.patch(f"/api/deals/{deal['id']}", headers=mgr, json={"action": "complete"}).get_json()["data"]
    assert done["status"] == "completed"
    assert client.get(f"/api/properties/{p['id']}").get_json()["data"]["status"] == "sold"
    comms = client.get("/api/commissions", headers=mgr).get_json()["data"]
    assert any(c["amount"] == round(4200000 * 0.02, 2) for c in comms)


def test_duplicate_active_deal_blocked(client, login):
    p = _sale_prop(client)
    mgr = login("manager")
    for _ in range(2):
        client.post("/api/offers", headers=login("buyer"), json={"property_id": p["id"], "amount": 100})
    ids = [o["id"] for o in client.get("/api/offers", headers=mgr).get_json()["data"] if o["property_id"] == p["id"]]
    codes = [client.patch(f"/api/offers/{i}", headers=mgr, json={"action": "accept"}).status_code for i in ids]
    assert 200 in codes and 409 in codes


def test_document_access_control_and_validation(client, login):
    pdf = (io.BytesIO(b"%PDF-1.4 test"), "a.pdf")
    owner = login("owner")
    prop = client.get("/api/properties?mine=1&approval=pending", headers=owner).get_json()["data"][0]["id"]
    r = client.post("/api/documents", headers=owner, content_type="multipart/form-data",
                    data={"file": pdf, "title": "Deed", "category": "ownership", "property_id": prop})
    assert r.status_code == 201
    did = r.get_json()["data"]["id"]
    assert client.get(f"/api/documents/{did}/download", headers=owner).status_code == 200
    assert client.get(f"/api/documents/{did}/download", headers=login("buyer")).status_code == 404  # IDOR guard
    assert client.get(f"/api/documents/{did}/download", headers=login("manager")).status_code == 200
    bad = client.post("/api/documents", headers=owner, content_type="multipart/form-data",
                      data={"file": (io.BytesIO(b"MZ\x90 exe"), "evil.pdf"), "title": "x", "category": "other"})
    assert bad.status_code == 415
    assert client.post("/api/documents", headers=login("buyer"), content_type="multipart/form-data",
                       data={"file": (io.BytesIO(b"%PDF-1"), "a.pdf"), "title": "x", "category": "other", "property_id": prop}).status_code == 403


def test_reviews_verification_and_moderation(client, login):
    pid = _sale_prop(client)["id"]
    t = login("tenant")
    r = client.post(f"/api/properties/{pid}/reviews", headers=t, json={"rating": 4, "agent_rating": 5, "comment": "Nice"})
    assert r.status_code == 201 and r.get_json()["data"]["verified"] is False  # no lease/visit there
    assert client.post(f"/api/properties/{pid}/reviews", headers=t, json={"rating": 4}).status_code == 409
    assert client.post(f"/api/properties/{pid}/reviews", headers=login("buyer"), json={"rating": 9}).status_code == 422
    rid = r.get_json()["data"]["id"]
    assert client.post(f"/api/reviews/{rid}/report", headers=login("buyer"), json={"reason": "spam"}).status_code == 200
    q = client.get("/api/admin/reviews", headers=login("manager")).get_json()["data"]
    assert any(x["id"] == rid for x in q)
    assert client.patch(f"/api/admin/reviews/{rid}", headers=login("buyer"), json={"status": "hidden"}).status_code == 403
    assert client.patch(f"/api/admin/reviews/{rid}", headers=login("manager"), json={"status": "hidden"}).status_code == 200
    pub = client.get(f"/api/properties/{pid}/reviews").get_json()
    assert all(x["id"] != rid for x in pub["data"])


def test_finance_scoping_and_expenses(client, login):
    mgr, owner = login("manager"), login("owner")
    s = client.get("/api/finance/summary", headers=mgr).get_json()["data"]
    assert s["income"] > 0 and s["expense"] > 0 and s["net"] == round(s["income"] - s["expense"], 2)
    assert client.get("/api/finance/summary", headers=login("tenant")).status_code == 403
    assert client.get("/api/finance/ledger", headers=owner).status_code == 200
    assert client.post("/api/expenses", headers=owner, json={"category": "tax", "amount": 500}).status_code == 422  # must pick property
    pid = client.get("/api/properties?mine=1", headers=owner).get_json()["data"][0]["id"]
    assert client.post("/api/expenses", headers=owner, json={"property_id": pid, "category": "tax", "amount": 500}).status_code == 201
    assert client.post("/api/expenses", headers=mgr, json={"category": "bogus", "amount": 5}).status_code == 422
    assert client.get("/api/reports/ledger?format=xlsx", headers=mgr).status_code == 200


def test_vendor_settings_agency_permissions(client, login):
    assert client.post("/api/vendors", headers=login("agent"), json={"name": "x", "category": "plumbing"}).status_code == 403
    assert client.post("/api/vendors", headers=login("manager"), json={"name": "Pipe Pros", "category": "plumbing"}).status_code == 201
    assert client.put("/api/settings", headers=login("manager"), json={"platform_name": "X"}).status_code == 403
    r = client.put("/api/settings", headers=login("admin"), json={"default_commission_rate": 3, "hack": "x"})
    assert r.get_json()["data"]["default_commission_rate"] == "3"
    assert client.put("/api/settings", headers=login("admin"), json={"default_commission_rate": 99}).status_code == 422
    assert client.post("/api/agencies", headers=login("admin"), json={"name": "Metro Homes", "city": "Pune"}).status_code == 201
    client.put("/api/settings", headers=login("admin"), json={"allow_registration": 0})
    assert client.post("/api/auth/register", json={"name": "A", "email": "a@b.co", "password": "Passw0rd1"}).status_code == 403


def test_maintenance_image_private(client, login):
    m = client.post("/api/maintenance", headers=login("tenant"), json={"category": "plumbing", "description": "Leak under sink"}).get_json()["data"]
    png = (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 20), "leak.png")
    assert client.post(f"/api/maintenance/{m['id']}/image", headers=login("tenant"), content_type="multipart/form-data", data={"image": png}).status_code == 200
    assert client.get(f"/api/maintenance/{m['id']}/image", headers=login("tenant")).status_code == 200
    assert client.get(f"/api/maintenance/{m['id']}/image", headers=login("tenant2")).status_code == 404
    assert client.get(f"/api/maintenance/{m['id']}/image").status_code == 401
