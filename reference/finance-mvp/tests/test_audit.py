from tests.conftest import auth, login


def test_audit_trail_records_lifecycle(client):
    clerk = login(client, "clerk@finance.local", "Clerk#12345")
    manager = login(client, "manager@finance.local", "Manager#12345")
    auditor = login(client, "auditor@finance.local", "Auditor#12345")

    inv = client.post("/api/v1/invoices", headers=auth(clerk),
                      json={"invoice_number": "INV-AUD", "vendor_id": 1, "amount": 42}).json()
    client.post(f"/api/v1/invoices/{inv['id']}/submit", headers=auth(clerk))
    client.post(f"/api/v1/invoices/{inv['id']}/approve", headers=auth(manager))
    client.post(f"/api/v1/invoices/{inv['id']}/post", headers=auth(manager))

    logs = client.get(f"/api/v1/audit-logs?entity_type=invoice&entity_id={inv['id']}",
                      headers=auth(auditor)).json()
    actions = {row["action"] for row in logs}
    assert {"invoice.create", "invoice.submit", "invoice.approve", "invoice.post"} <= actions
    # Correlation id present on every audit row.
    assert all(row["correlation_id"] for row in logs)
    # Actor attribution: post done by the manager.
    post_row = next(r for r in logs if r["action"] == "invoice.post")
    assert post_row["actor_email"] == "manager@finance.local"
