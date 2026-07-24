"""Test harness: in-memory SQLite, seeded demo users, auth helpers."""
from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "sqlite://"  # pure in-memory (StaticPool)
os.environ["JWT_SECRET"] = "test-secret-please-change-32-bytes-minimum"

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.core.security import hash_password
from app.main import app
from app.models.user import User
from app.models.vendor import Vendor


@pytest.fixture(scope="function")
def client():
    Base.metadata.create_all(bind=engine)
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        demo = [
            ("admin@finance.local", "Admin", "ADMIN", "Admin#12345"),
            ("clerk@finance.local", "Clerk", "AP_CLERK", "Clerk#12345"),
            ("clerk2@finance.local", "Clerk Two", "AP_CLERK", "Clerk#12345"),
            ("manager@finance.local", "Manager", "AP_MANAGER", "Manager#12345"),
            ("auditor@finance.local", "Auditor", "AUDITOR", "Auditor#12345"),
        ]
        for email, name, role, pw in demo:
            db.add(User(email=email, full_name=name, role=role,
                        hashed_password=hash_password(pw), is_active=True))
        db.add(Vendor(name="Acme Supplies", tax_id="TAX-001",
                      erp_ref="ERP-VENDOR-001", is_active=True))
        db.commit()
    finally:
        db.close()

    with TestClient(app) as c:
        yield c

    Base.metadata.drop_all(bind=engine)


def login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
