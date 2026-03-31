from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import os

from app.database import get_db
from app.models.user import User, UserRole
from app.models.space import SpaceMember, SpaceMemberRole
from app.schemas.user import UserResponse, CreateChildRequest, UpdateChildRequest
from app.core.security import hash_password, create_telegram_link_token, decode_token
from app.models.organization import Organization
from app.core.deps import get_current_user
from jose import JWTError

router = APIRouter(prefix="/users", tags=["users"])


class TelegramLinkResponse(BaseModel):
    token: str
    deep_link: str


class TelegramLinkRequest(BaseModel):
    token: str
    telegram_id: int


@router.get("/me/telegram/link-token", response_model=TelegramLinkResponse)
async def get_telegram_link_token(
    current_user: User = Depends(get_current_user),
):
    """Generate a 24h deep link for connecting Telegram account."""
    token = create_telegram_link_token(current_user.id)
    bot_username = os.getenv("TG_BOT_USERNAME", "ourway_bot")
    deep_link = f"https://t.me/{bot_username}?start={token}"
    return TelegramLinkResponse(token=token, deep_link=deep_link)


@router.post("/telegram/link", response_model=UserResponse)
async def link_telegram(
    body: TelegramLinkRequest,
    db: AsyncSession = Depends(get_db),
):
    """Called by the bot after user clicks the deep link. Links telegram_id to the user."""
    try:
        payload = decode_token(body.token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired link token")

    if payload.get("type") != "tg_link":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token type")

    user_id = int(payload["sub"])

    # Check telegram_id not already taken by another user
    existing = await db.execute(select(User).where(User.telegram_id == body.telegram_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Telegram account already linked to another user")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.telegram_id = body.telegram_id
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/me/telegram", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_telegram(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unlink Telegram account from current user."""
    current_user.telegram_id = None
    await db.commit()


@router.post("/children", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_child(
    body: CreateChildRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != UserRole.owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners can create child accounts")

    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    if body.autonomy_level not in (1, 2, 3):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="autonomy_level must be 1, 2, or 3")

    child = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        name=body.name,
        role=UserRole.child,
        locale=current_user.locale,
        organization_id=current_user.organization_id,
        autonomy_level=body.autonomy_level,
        created_by_id=current_user.id,
    )
    db.add(child)
    await db.commit()
    await db.refresh(child)
    return child


@router.get("/family", response_model=list[UserResponse])
async def get_family(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.organization_id == current_user.organization_id)
    )
    return result.scalars().all()


@router.patch("/children/{child_id}", response_model=UserResponse)
async def update_child(
    child_id: int,
    body: UpdateChildRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != UserRole.owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners can update child accounts")

    if body.autonomy_level not in (1, 2, 3):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="autonomy_level must be 1, 2, or 3")

    result = await db.execute(
        select(User).where(User.id == child_id, User.organization_id == current_user.organization_id, User.role == UserRole.child)
    )
    child = result.scalar_one_or_none()
    if not child:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child not found")

    child.autonomy_level = body.autonomy_level
    await db.commit()
    await db.refresh(child)
    return child


@router.delete("/children/{child_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_child(
    child_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != UserRole.owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners can delete child accounts")

    result = await db.execute(
        select(User).where(User.id == child_id, User.organization_id == current_user.organization_id, User.role == UserRole.child)
    )
    child = result.scalar_one_or_none()
    if not child:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child not found")

    await db.delete(child)
    await db.commit()


class BotCreateChildRequest(BaseModel):
    name: str
    autonomy_level: int = 1
    is_managed: bool = False  # True = no TG account (parent manages everything)


class BotCreateChildResponse(BaseModel):
    child: UserResponse
    invite_link: str | None = None  # Only set when is_managed=False


@router.post("/children/bot-create", response_model=BotCreateChildResponse, status_code=status.HTTP_201_CREATED)
async def bot_create_child(
    body: BotCreateChildRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a child profile via Telegram bot. Owner only."""
    if current_user.role != UserRole.owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners can create child accounts")

    if body.autonomy_level not in (1, 2, 3):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="autonomy_level must be 1, 2, or 3")

    # Auto-generate a unique placeholder email
    import time
    placeholder_email = f"child_{int(time.time())}_{current_user.id}@ourway.app"

    child = User(
        email=placeholder_email,
        hashed_password=None,
        name=body.name,
        role=UserRole.child,
        locale=current_user.locale,
        organization_id=current_user.organization_id,
        autonomy_level=body.autonomy_level,
        created_by_id=current_user.id,
        is_managed=body.is_managed,
        managed_by=current_user.id if body.is_managed else None,
    )
    db.add(child)
    await db.commit()
    await db.refresh(child)

    invite_link = None
    if not body.is_managed:
        bot_username = os.getenv("TG_BOT_USERNAME", "ourway_bot")
        token = create_telegram_link_token(child.id)
        invite_link = f"https://t.me/{bot_username}?start={token}"

    return BotCreateChildResponse(child=child, invite_link=invite_link)
