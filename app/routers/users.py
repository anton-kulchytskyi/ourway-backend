from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User, UserRole
from app.models.space import SpaceMember, SpaceMemberRole
from app.schemas.user import UserResponse, CreateChildRequest, UpdateChildRequest
from app.core.security import hash_password
from app.core.deps import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


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
