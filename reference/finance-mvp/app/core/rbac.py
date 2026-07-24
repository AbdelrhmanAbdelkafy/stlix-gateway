"""Authorization / RBAC (Chapters 26-27).

Roles map to a fixed permission matrix. Endpoints declare the permission they
require; Segregation-of-Duties is additionally enforced in the workflow layer.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import JWTError, decode_token
from app.models.user import User

# --- Permission catalogue ---
P_VENDOR_READ = "vendor:read"
P_VENDOR_WRITE = "vendor:write"
P_INVOICE_READ = "invoice:read"
P_INVOICE_CREATE = "invoice:create"
P_INVOICE_SUBMIT = "invoice:submit"
P_INVOICE_APPROVE = "invoice:approve"
P_INVOICE_POST = "invoice:post"
P_AUDIT_READ = "audit:read"
P_USER_MANAGE = "user:manage"

# --- Roles ---
ROLE_ADMIN = "ADMIN"
ROLE_AP_CLERK = "AP_CLERK"
ROLE_AP_MANAGER = "AP_MANAGER"
ROLE_AUDITOR = "AUDITOR"

ALL_PERMISSIONS = {
    P_VENDOR_READ, P_VENDOR_WRITE, P_INVOICE_READ, P_INVOICE_CREATE,
    P_INVOICE_SUBMIT, P_INVOICE_APPROVE, P_INVOICE_POST, P_AUDIT_READ, P_USER_MANAGE,
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    ROLE_ADMIN: set(ALL_PERMISSIONS),
    ROLE_AP_CLERK: {P_VENDOR_READ, P_INVOICE_READ, P_INVOICE_CREATE, P_INVOICE_SUBMIT},
    ROLE_AP_MANAGER: {P_VENDOR_READ, P_VENDOR_WRITE, P_INVOICE_READ, P_INVOICE_APPROVE, P_INVOICE_POST},
    ROLE_AUDITOR: {P_VENDOR_READ, P_INVOICE_READ, P_AUDIT_READ},
}


def permissions_for(role: str) -> set[str]:
    return ROLE_PERMISSIONS.get(role, set())


def has_permission(role: str, permission: str) -> bool:
    return permission in permissions_for(role)


_bearer = HTTPBearer(auto_error=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    creds_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise creds_exc
    if payload.get("type") != "access":
        raise creds_exc
    email = payload.get("sub")
    if not email:
        raise creds_exc
    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active:
        raise creds_exc
    return user


def require_permission(permission: str):
    """Dependency factory: 403 unless the current user's role grants `permission`."""

    def _checker(user: User = Depends(get_current_user)) -> User:
        if not has_permission(user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission}",
            )
        return user

    return _checker
