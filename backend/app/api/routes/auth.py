from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.agentic.memory import MemoryUnavailableError, build_memory_scope, get_shopping_memory_store
from app.models import AuthSession, Cart, User, UserStatus, Wallet
from app.security import (
    create_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)

from ..schemas import (
    AuthResponse,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    UserResponse,
)


router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
SESSION_COOKIE_NAME = "shopy_session"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def set_session_cookie(response: Response, token: str) -> None:
    max_age = settings.auth_session_days * 24 * 60 * 60
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


def create_auth_session(db: Session, user: User) -> str:
    token = create_session_token()
    now = utc_now()
    db.add(
        AuthSession(
            user=user,
            token_hash=hash_session_token(token),
            expires_at=now + timedelta(days=settings.auth_session_days),
            last_seen_at=now,
        )
    )
    return token


def get_current_user(
    session_token: Annotated[
        str | None, Cookie(alias=SESSION_COOKIE_NAME)
    ] = None,
    db: Session = Depends(get_db),
) -> User:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    session = db.scalar(
        select(AuthSession)
        .options(joinedload(AuthSession.user))
        .where(AuthSession.token_hash == hash_session_token(session_token))
    )
    now = utc_now()
    if session is None or session.expires_at.replace(tzinfo=session.expires_at.tzinfo or timezone.utc) <= now:
        if session is not None:
            db.delete(session)
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or invalid.")
    if session.user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is not active.")

    session.last_seen_at = now
    db.commit()
    return session.user


def get_optional_current_user(
    session_token: Annotated[
        str | None, Cookie(alias=SESSION_COOKIE_NAME)
    ] = None,
    db: Session = Depends(get_db),
) -> User | None:
    if not session_token:
        return None
    try:
        return get_current_user(session_token=session_token, db=db)
    except HTTPException as error:
        if error.status_code == status.HTTP_401_UNAUTHORIZED:
            return None
        raise


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    existing_user = db.scalar(select(User.id).where(User.email == payload.email))
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        wallet=Wallet(),
        carts=[Cart()],
    )
    db.add(user)
    token = create_auth_session(db, user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from error

    db.refresh(user)
    set_session_cookie(response, token)
    return AuthResponse(user=UserResponse.model_validate(user))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is not active.")

    user.last_login_at = utc_now()
    token = create_auth_session(db, user)
    db.commit()
    db.refresh(user)
    set_session_cookie(response, token)
    return AuthResponse(user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(user)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    session_token: Annotated[
        str | None, Cookie(alias=SESSION_COOKIE_NAME)
    ] = None,
    db: Session = Depends(get_db),
) -> MessageResponse:
    if session_token:
        auth_session = db.scalar(
            select(AuthSession).options(joinedload(AuthSession.user)).where(
                AuthSession.token_hash == hash_session_token(session_token)
            )
        )
        if auth_session is not None:
            memory_scope = build_memory_scope(
                user_id=auth_session.user_id,
                auth_session_token=session_token,
                conversation_token="unused-for-authenticated-session",
            )
            try:
                await get_shopping_memory_store().clear(memory_scope)
            except MemoryUnavailableError:
                # Logout must still revoke authentication if Redis is unavailable.
                pass
        db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_session_token(session_token)))
        db.commit()
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    return MessageResponse(message="Signed out successfully.")
