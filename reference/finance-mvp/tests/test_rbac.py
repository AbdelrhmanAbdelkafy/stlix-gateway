from tests.conftest import auth, login


def _create_and_submit(client, clerk_token):
    inv = client.post("/api/v1/invoices", headers=auth(clerk_token),
                      json={"invoice_number": "INV-RBAC", "vendor_id": 1, "amount": 100}).json()
    client.post(f"/api/v1/invoices/{inv['id']}/submit", headers=auth(clerk_token))
    return inv["id"]


def test_clerk_cannot_approve(client):
    clerk = login(client, "clerk@finance.local", "Clerk#12345")
    inv_id = _create_and_submit(client, clerk)
    resp = client.post(f"/api/v1/invoices/{inv_id}/approve", headers=auth(clerk))
    assert resp.status_code == 403


def test_manager_cannot_create_invoice(client):
    manager = login(client, "manager@finance.local", "Manager#12345")
    resp = client.post("/api/v1/invoices", headers=auth(manager),
                       json={"invoice_number": "INV-X", "vendor_id": 1, "amount": 100})
    assert resp.status_code == 403


def test_auditor_can_read_audit_clerk_cannot(client):
    auditor = login(client, "auditor@finance.local", "Auditor#12345")
    assert client.get("/api/v1/audit-logs", headers=auth(auditor)).status_code == 200
    clerk = login(client, "clerk@finance.local", "Clerk#12345")
    assert client.get("/api/v1/audit-logs", headers=auth(clerk)).status_code == 403


def test_clerk_cannot_create_vendor(client):
    clerk = login(client, "clerk@finance.local", "Clerk#12345")
    resp = client.post("/api/v1/vendors", headers=auth(clerk), json={"name": "New Co"})
    assert resp.status_code == 403
