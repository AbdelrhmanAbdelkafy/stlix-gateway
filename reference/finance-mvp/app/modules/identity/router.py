"""Identity module: authentication & user management (Chapters 25-27)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core import rbac
from app.core.audit import record_action
from app.core.database import get_db
from app.core.rbac import get_current_user, permissions_for, require_permission
from app.core.security import (
    JWTError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    MeOut,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserOut,
)

router = APIRouter(tags=["identity"])


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(
        access_token=create_access_token(user.email, user.role),
        refresh_token=create_refresh_token(user.email),
    )


@router.post("/auth/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    creds_exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    try:
        data = decode_token(payload.refresh_token)
    except JWTError:
        raise creds_exc
    if data.get("type") != "refresh":
        raise creds_exc
    user = db.query(User).filter(User.email == data.get("sub")).first()
    if user is None or not user.is_active:
        raise creds_exc
    return TokenResponse(
        access_token=create_access_token(user.email, user.role),
        refresh_token=create_refresh_token(user.email),
    )


@router.get("/auth/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    out = MeOut.model_validate(user)
    out.permissions = sorted(permissions_for(user.role))
    return out


@router.get("/users", response_model=list[UserOut])
def list_users(
    _: User = Depends(require_permission(rbac.P_USER_MANAGE)),
    db: Session = Depends(get_db),
):
    return db.query(User).order_by(User.id).all()


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    actor: User = Depends(require_permission(rbac.P_USER_MANAGE)),
    db: Session = Depends(get_db),
):
    if payload.role not in rbac.ROLE_PERMISSIONS:
        raise HTTPException(status_code=400, detail=f"Unknown role: {payload.role}")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email already exists")
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        is_active=True,
        created_by=actor.id,
    )
    db.add(user)
    db.flush()
    record_action(
        db, actor=actor, action="user.create", entity_type="user", entity_id=user.id,
        after={"email": user.email, "role": user.role},
    )
    db.commit()
    db.refresh(user)
    return user
