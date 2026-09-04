from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Cookie, Depends, File, HTTPException, Response, UploadFile, status
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
    ProfileUpdateRequest,
    RegisterRequest,
    UserResponse,
)


router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
SESSION_COOKIE_NAME = "shopy_session"
AVATAR_CONTENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_AVATAR_BYTES = 2 * 1024 * 1024


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clear_missing_avatar_reference(user: User, db: Session) -> None:
    """Remove a database URL when its locally managed avatar no longer exists.

    The image bytes and URL are intentionally stored separately. A file can be
    lost after an earlier temporary-storage deployment, so returning its stale
    URL would make every client render a 404 indefinitely.
    """
    avatar_url = user.avatar_url
    prefix = "/uploads/avatars/"
    if not avatar_url or not avatar_url.startswith(prefix):
        return
    filename = Path(avatar_url).name
    avatar_path = settings.upload_directory / "avatars" / filename
    if avatar_path.is_file():
        return
    user.avatar_url = None
    db.commit()
    db.refresh(user)


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

    clear_missing_avatar_reference(session.user, db)
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


@router.patch("/me", response_model=UserResponse)
def update_profile(payload: ProfileUpdateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserResponse:
    user.full_name = payload.full_name
    user.phone = payload.phone
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.post("/avatar", response_model=UserResponse)
async def upload_avatar(
    avatar: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Persist a small, browser-safe avatar for the authenticated account."""
    extension = AVATAR_CONTENT_TYPES.get(avatar.content_type or "")
    if extension is None:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Use a JPEG, PNG, or WebP image for your avatar.")
    image_data = await avatar.read(MAX_AVATAR_BYTES + 1)
    if not image_data or len(image_data) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Avatar images must be 2 MB or smaller.")
    avatar_directory = settings.upload_directory / "avatars"
    avatar_directory.mkdir(parents=True, exist_ok=True)
    filename = f"{user.id}-{uuid4().hex}{extension}"
    destination = avatar_directory / filename
    destination.write_bytes(image_data)
    previous_path = user.avatar_url
    user.avatar_url = f"/uploads/avatars/{filename}"
    db.commit()
    db.refresh(user)
    if previous_path and previous_path.startswith("/uploads/avatars/"):
        previous_file = settings.upload_directory / Path(previous_path).relative_to("/uploads")
        if previous_file != destination:
            previous_file.unlink(missing_ok=True)
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
