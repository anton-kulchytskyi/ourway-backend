from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.space import Space
from app.schemas.space import SpaceCreate, SpaceUpdate, SpaceResponse

router = APIRouter(prefix="/spaces", tags=["spaces"])


def _check_org(user: User) -> int:
    if not user.organization_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User has no organization")
    return user.organization_id


async def _get_space_or_404(space_id: int, org_id: int, db: AsyncSession) -> Space:
    result = await db.execute(
        select(Space).where(Space.id == space_id, Space.organization_id == org_id)
    )
    space = result.scalar_one_or_none()
    if not space:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Space not found")
    return space


@router.get("", response_model=list[SpaceResponse])
async def list_spaces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_id = _check_org(current_user)
    result = await db.execute(select(Space).where(Space.organization_id == org_id))
    return result.scalars().all()


@router.post("", response_model=SpaceResponse, status_code=status.HTTP_201_CREATED)
async def create_space(
    body: SpaceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_id = _check_org(current_user)
    space = Space(name=body.name, emoji=body.emoji, organization_id=org_id)
    db.add(space)
    await db.commit()
    await db.refresh(space)
    return space


@router.get("/{space_id}", response_model=SpaceResponse)
async def get_space(
    space_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_id = _check_org(current_user)
    return await _get_space_or_404(space_id, org_id, db)


@router.patch("/{space_id}", response_model=SpaceResponse)
async def update_space(
    space_id: int,
    body: SpaceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_id = _check_org(current_user)
    space = await _get_space_or_404(space_id, org_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(space, field, value)
    await db.commit()
    await db.refresh(space)
    return space


@router.delete("/{space_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_space(
    space_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_id = _check_org(current_user)
    space = await _get_space_or_404(space_id, org_id, db)
    await db.delete(space)
    await db.commit()
