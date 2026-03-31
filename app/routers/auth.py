import os

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError

from app.database import get_db
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.schemas.user import RegisterRequest, LoginRequest, RefreshRequest, TokenResponse, UserResponse
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.core.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    org = Organization(name=f"{body.name}'s Family", default_locale=body.locale)
    db.add(org)
    await db.flush()  # get org.id before user insert

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        name=body.name,
        locale=body.locale,
        role=UserRole.owner,
        organization_id=org.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


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
    """Register a new user directly via Telegram (no email/password required)."""
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
