from tests.conftest import auth, login


def test_full_lifecycle_to_erp(client):
    clerk = login(client, "clerk@finance.local", "Clerk#12345")
    manager = login(client, "manager@finance.local", "Manager#12345")

    inv = client.post("/api/v1/invoices", headers=auth(clerk),
                      json={"invoice_number": "INV-2001", "vendor_id": 1,
                            "amount": 2500.50, "currency": "USD"}).json()
    assert inv["status"] == "DRAFT"

    r = client.post(f"/api/v1/invoices/{inv['id']}/submit", headers=auth(clerk))
    assert r.json()["status"] == "SUBMITTED"

    r = client.post(f"/api/v1/invoices/{inv['id']}/approve", headers=auth(manager))
    assert r.json()["status"] == "APPROVED"

    r = client.post(f"/api/v1/invoices/{inv['id']}/post", headers=auth(manager))
    body = r.json()
    assert body["status"] == "POSTED"
    assert body["erp_document_id"] and body["erp_document_id"].startswith("ERP-")


def test_cannot_approve_own_invoice_sod(client):
    # An AP_MANAGER-created invoice cannot be approved by the same manager (SoD).
    admin = login(client, "admin@finance.local", "Admin#12345")  # admin has all perms incl create
    inv = client.post("/api/v1/invoices", headers=auth(admin),
                      json={"invoice_number": "INV-SOD", "vendor_id": 1, "amount": 10}).json()
    client.post(f"/api/v1/invoices/{inv['id']}/submit", headers=auth(admin))
    resp = client.post(f"/api/v1/invoices/{inv['id']}/approve", headers=auth(admin))
    assert resp.status_code == 409
    assert "Segregation of Duties" in resp.json()["detail"]


def test_cannot_post_before_approval(client):
    clerk = login(client, "clerk@finance.local", "Clerk#12345")
    manager = login(client, "manager@finance.local", "Manager#12345")
    inv = client.post("/api/v1/invoices", headers=auth(clerk),
                      json={"invoice_number": "INV-EARLY", "vendor_id": 1, "amount": 10}).json()
    client.post(f"/api/v1/invoices/{inv['id']}/submit", headers=auth(clerk))
    # SUBMITTED -> post should fail (must be APPROVED)
    resp = client.post(f"/api/v1/invoices/{inv['id']}/post", headers=auth(manager))
    assert resp.status_code == 409


def test_reject_path(client):
    clerk = login(client, "clerk@finance.local", "Clerk#12345")
    manager = login(client, "manager@finance.local", "Manager#12345")
    inv = client.post("/api/v1/invoices", headers=auth(clerk),
                      json={"invoice_number": "INV-REJ", "vendor_id": 1, "amount": 10}).json()
    client.post(f"/api/v1/invoices/{inv['id']}/submit", headers=auth(clerk))
    r = client.post(f"/api/v1/invoices/{inv['id']}/reject", headers=auth(manager),
                    json={"reason": "missing PO"})
    assert r.json()["status"] == "REJECTED"
