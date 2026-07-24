"""Seed baseline roles-as-users and a demo vendor (Chapter 36: Local Development).

Idempotent: safe to run multiple times.
Run:  python -m app.seed
"""
from __future__ import annotations

from app.core.database import SessionLocal, create_all
from app.core.logging_config import configure_logging, logger
from app.core.security import hash_password
from app.models.user import User
from app.models.vendor import Vendor

DEMO_USERS = [
    ("admin@finance.local", "Admin", "ADMIN", "Admin#12345"),
    ("clerk@finance.local", "AP Clerk", "AP_CLERK", "Clerk#12345"),
    ("manager@finance.local", "AP Manager", "AP_MANAGER", "Manager#12345"),
    ("auditor@finance.local", "Internal Auditor", "AUDITOR", "Auditor#12345"),
]


def seed() -> None:
    configure_logging()
    create_all()
    db = SessionLocal()
    try:
        for email, name, role, password in DEMO_USERS:
            if not db.query(User).filter(User.email == email).first():
                db.add(User(email=email, full_name=name, role=role,
                            hashed_password=hash_password(password), is_active=True))
                logger.info("seed user %s (%s)", email, role)
        if not db.query(Vendor).filter(Vendor.name == "Acme Supplies").first():
            db.add(Vendor(name="Acme Supplies", tax_id="TAX-001",
                          email="ap@acme.example", erp_ref="ERP-VENDOR-001", is_active=True))
            logger.info("seed vendor Acme Supplies")
        db.commit()
        logger.info("seed complete")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
