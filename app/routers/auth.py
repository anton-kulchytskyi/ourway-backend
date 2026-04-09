import hashlib
import hmac
import os
import time

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError

from app.database import get_db
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.schemas.user import LoginRequest, RefreshRequest, TokenResponse, UserResponse
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token
from app.core.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])



@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError
        user_id = int(payload["sub"])
    except (JWTError, ValueError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


class BotLoginRequest(BaseModel):
    telegram_id: int


class TelegramRegisterRequest(BaseModel):
    telegram_id: int
    name: str
    locale: str = "en"


@router.post("/bot-login", response_model=TokenResponse)
async def bot_login(
    body: BotLoginRequest,
    x_bot_secret: str = Header(..., alias="X-Bot-Secret"),
    db: AsyncSession = Depends(get_db),
):
    """Called by the Telegram bot to get a JWT for a linked user."""
    expected = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not expected or x_bot_secret != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bot secret")

    result = await db.execute(select(User).where(User.telegram_id == body.telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No user linked to this Telegram account")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/telegram-register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def telegram_register(
    body: TelegramRegisterRequest,
    x_bot_secret: str = Header(..., alias="X-Bot-Secret"),
    db: AsyncSession = Depends(get_db),
):
    """Register a new user directly via Telegram. Auto-generates email as tg_{id}@ourway.app."""
    expected = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not expected or x_bot_secret != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bot secret")

    existing = await db.execute(select(User).where(User.telegram_id == body.telegram_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Telegram account already registered")

    org = Organization(name=f"{body.name}'s Family", default_locale=body.locale)
    db.add(org)
    await db.flush()

    user = User(
        email=None,
        hashed_password=None,
        name=body.name,
        locale=body.locale,
        role=UserRole.owner,
        organization_id=org.id,
        telegram_id=body.telegram_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


class TelegramOAuthRequest(BaseModel):
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


def _verify_telegram_hash(data: TelegramOAuthRequest) -> bool:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    fields = {
        "id": str(data.id),
        "first_name": data.first_name,
        "auth_date": str(data.auth_date),
    }
    if data.last_name:
        fields["last_name"] = data.last_name
    if data.username:
        fields["username"] = data.username
    if data.photo_url:
        fields["photo_url"] = data.photo_url
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    expected = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, data.hash)


@router.post("/telegram-oauth", response_model=TokenResponse)
async def telegram_oauth(
    body: TelegramOAuthRequest,
    db: AsyncSession = Depends(get_db),
):
    """Login or register via Telegram Login Widget / Mini App initData."""
    if not _verify_telegram_hash(body):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram hash")

    if time.time() - body.auth_date > 86400:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram auth expired")

    result = await db.execute(select(User).where(User.telegram_id == body.id))
    user = result.scalar_one_or_none()

    if not user:
        name = body.first_name
        if body.last_name:
            name += f" {body.last_name}"

        org = Organization(name=f"{name}'s Family", default_locale="en")
        db.add(org)
        await db.flush()

        user = User(
            email=None,
            hashed_password=None,
            name=name,
            locale="en",
            role=UserRole.owner,
            organization_id=org.id,
            telegram_id=body.id,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role == UserRole.owner and current_user.organization_id:
        # Delete org → cascades to spaces, tasks, all org members
        result = await db.execute(select(Organization).where(Organization.id == current_user.organization_id))
        org = result.scalar_one_or_none()
        if org:
            await db.delete(org)
    else:
        await db.delete(current_user)
    await db.commit()
