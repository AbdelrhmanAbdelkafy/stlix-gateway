"""Database engine & session (Chapter 41: Database Architecture).

Portable across MySQL (production) and SQLite (local/tests). ERP remains the
System of Record; this database only stores platform-side workflow state,
audit trail, and derived data.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        # Pure in-memory ("sqlite://") needs a single shared connection.
        if url in ("sqlite://", "sqlite:///:memory:"):
            return create_engine(url, connect_args=connect_args, poolclass=StaticPool)
        return create_engine(url, connect_args=connect_args)
    # MySQL / others
    return create_engine(url, pool_pre_ping=True)


engine = _make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db():
    """FastAPI dependency: yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all() -> None:
    # Import models so they register on Base.metadata before create_all.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
