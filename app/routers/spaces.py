from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.database import get_db
from app.core.deps import get_current_user
from app.core.i18n import t
from app.models.user import User
from app.models.space import Space, SpaceMember, SpaceMemberRole
from app.schemas.space import SpaceCreate, SpaceUpdate, SpaceResponse, SpaceMemberResponse, SpaceMemberRoleUpdate, SpaceMemberAdd

router = APIRouter(prefix="/spaces", tags=["spaces"])


def _check_org(user: User) -> int:
    if not user.organization_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User has no organization")
    return user.organization_id


async def _get_membership_or_403(space_id: int, user_id: int, db: AsyncSession) -> SpaceMember:
    result = await db.execute(
        select(SpaceMember).where(SpaceMember.space_id == space_id, SpaceMember.user_id == user_id)
    )
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this space")
    return m


async def _get_space_or_404(space_id: int, user_id: int, db: AsyncSession) -> Space:
    result = await db.execute(
        select(Space)
        .join(SpaceMember, SpaceMember.space_id == Space.id)
        .where(Space.id == space_id, SpaceMember.user_id == user_id)
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
    _check_org(current_user)
    OwnerMember = aliased(SpaceMember)
    OwnerUser = aliased(User)
    result = await db.execute(
        select(Space, SpaceMember.role, OwnerUser.name)
        .join(SpaceMember, SpaceMember.space_id == Space.id)
        .outerjoin(OwnerMember, (OwnerMember.space_id == Space.id) & (OwnerMember.role == SpaceMemberRole.owner))
        .outerjoin(OwnerUser, OwnerUser.id == OwnerMember.user_id)
        .where(SpaceMember.user_id == current_user.id)
    )
    rows = result.all()
    spaces = []
    for space, role, owner_name in rows:
        d = {c.key: getattr(space, c.key) for c in space.__table__.columns}
        d["my_role"] = role
        d["owner_name"] = owner_name
        spaces.append(d)
    return spaces


@router.post("", response_model=SpaceResponse, status_code=status.HTTP_201_CREATED)
async def create_space(
    body: SpaceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role.value == "child" and current_user.autonomy_level == 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=t("supervised_cannot_create_spaces", current_user.locale))
    org_id = _check_org(current_user)
    space = Space(name=body.name, emoji=body.emoji, organization_id=org_id)
    db.add(space)
    await db.flush()  # get space.id before commit

    # Add creator as owner
    db.add(SpaceMember(space_id=space.id, user_id=current_user.id, role=SpaceMemberRole.owner))

    # Level 1 (Supervised) and 2 (Semi): auto-add parent as viewer
    if current_user.role.value == "child" and current_user.autonomy_level in (1, 2) and current_user.created_by_id:
        db.add(SpaceMember(space_id=space.id, user_id=current_user.created_by_id, role=SpaceMemberRole.viewer))

    await db.commit()
    await db.refresh(space)
    d = {c.key: getattr(space, c.key) for c in space.__table__.columns}
    d["my_role"] = SpaceMemberRole.owner
    d["owner_name"] = current_user.name
    return d


@router.get("/{space_id}", response_model=SpaceResponse)
async def get_space(
    space_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_org(current_user)
    return await _get_space_or_404(space_id, current_user.id, db)


@router.patch("/{space_id}", response_model=SpaceResponse)
async def update_space(
    space_id: int,
    body: SpaceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_org(current_user)
    m = await _get_membership_or_403(space_id, current_user.id, db)
    if m.role != SpaceMemberRole.owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only space owner can edit")
    space = await _get_space_or_404(space_id, current_user.id, db)
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
    _check_org(current_user)
    m = await _get_membership_or_403(space_id, current_user.id, db)
    if m.role != SpaceMemberRole.owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only space owner can delete")
    space = await _get_space_or_404(space_id, current_user.id, db)
    await db.delete(space)
    await db.commit()


# --- Space members ---

@router.post("/{space_id}/members", response_model=SpaceMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_member(
    space_id: int,
    body: SpaceMemberAdd,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_org(current_user)
    m = await _get_membership_or_403(space_id, current_user.id, db)
    if m.role != SpaceMemberRole.owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only space owner can add members")

    # Verify target user is in the same org
    result = await db.execute(select(User).where(User.id == body.user_id, User.organization_id == current_user.organization_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in your organization")

    # Check not already a member
    existing = await db.execute(select(SpaceMember).where(SpaceMember.space_id == space_id, SpaceMember.user_id == body.user_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a member")

    new_member = SpaceMember(space_id=space_id, user_id=body.user_id, role=body.role)
    db.add(new_member)
    await db.commit()
    await db.refresh(new_member)
    return new_member


@router.get("/{space_id}/members", response_model=list[SpaceMemberResponse])
async def list_members(
    space_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_org(current_user)
    await _get_membership_or_403(space_id, current_user.id, db)
    result = await db.execute(select(SpaceMember).where(SpaceMember.space_id == space_id))
    return result.scalars().all()


@router.patch("/{space_id}/members/{user_id}", response_model=SpaceMemberResponse)
async def update_member_role(
    space_id: int,
    user_id: int,
    body: SpaceMemberRoleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_org(current_user)
    m = await _get_membership_or_403(space_id, current_user.id, db)
    if m.role != SpaceMemberRole.owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only space owner can change roles")

    result = await db.execute(
        select(SpaceMember).where(SpaceMember.space_id == space_id, SpaceMember.user_id == user_id)
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if target.role == SpaceMemberRole.owner:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change owner role")

    target.role = body.role
    await db.commit()
    await db.refresh(target)
    return target


@router.delete("/{space_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    space_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_org(current_user)
    m = await _get_membership_or_403(space_id, current_user.id, db)
    if m.role != SpaceMemberRole.owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only space owner can remove members")

    result = await db.execute(
        select(SpaceMember).where(SpaceMember.space_id == space_id, SpaceMember.user_id == user_id)
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if target.role == SpaceMemberRole.owner:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove space owner")

    await db.delete(target)
    await db.commit()
