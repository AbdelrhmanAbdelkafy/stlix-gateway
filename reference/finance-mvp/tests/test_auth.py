from tests.conftest import auth, login


def test_login_success_and_me(client):
    token = login(client, "clerk@finance.local", "Clerk#12345")
    resp = client.get("/api/v1/auth/me", headers=auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "clerk@finance.local"
    assert body["role"] == "AP_CLERK"
    assert "invoice:create" in body["permissions"]
    assert "invoice:approve" not in body["permissions"]


def test_login_wrong_password(client):
    resp = client.post("/api/v1/auth/login",
                       json={"email": "clerk@finance.local", "password": "wrong"})
    assert resp.status_code == 401


def test_protected_requires_token(client):
    assert client.get("/api/v1/invoices").status_code in (401, 403)


def test_refresh_issues_new_access_token(client):
    r = client.post("/api/v1/auth/login",
                    json={"email": "manager@finance.local", "password": "Manager#12345"})
    refresh = r.json()["refresh_token"]
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 200
    assert r2.json()["access_token"]


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"
