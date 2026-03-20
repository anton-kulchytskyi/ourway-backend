from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import secrets

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User, UserRole
from app.models.space import Space, SpaceMember, SpaceMemberRole, Invitation, InvitationRole, InvitationStatus
from app.schemas.invitation import InvitationCreate, InvitationResponse, InvitationPublicInfo

router = APIRouter(prefix="/invitations", tags=["invitations"])

INVITE_EXPIRES_DAYS = 7


@router.post("", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    body: InvitationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User has no organization")

    # Check user is owner of the space
    m_result = await db.execute(
        select(SpaceMember).where(
            SpaceMember.space_id == body.space_id,
            SpaceMember.user_id == current_user.id,
        )
    )
    membership = m_result.scalar_one_or_none()
    if not membership or membership.role != SpaceMemberRole.owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only space owner can invite")

    token = secrets.token_urlsafe(32)
    invitation = Invitation(
        token=token,
        org_id=current_user.organization_id,
        space_id=body.space_id,
        invited_by=current_user.id,
        role=body.role,
        expires_at=datetime.utcnow() + timedelta(days=INVITE_EXPIRES_DAYS),
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)
    return invitation


@router.get("/{token}", response_model=InvitationPublicInfo)
async def get_invitation(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Invitation).where(Invitation.token == token))
    invitation = result.scalar_one_or_none()
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    if invitation.expires_at < datetime.utcnow():
        invitation.status = InvitationStatus.expired
        await db.commit()

    if invitation.status != InvitationStatus.pending:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=f"Invitation is {invitation.status.value}")

    # Fetch space and inviter name
    space_result = await db.execute(select(Space).where(Space.id == invitation.space_id))
    space = space_result.scalar_one_or_none()

    inviter_result = await db.execute(select(User).where(User.id == invitation.invited_by))
    inviter = inviter_result.scalar_one_or_none()

    return InvitationPublicInfo(
        token=invitation.token,
        space_name=space.name if space else "Unknown",
        space_emoji=space.emoji if space else None,
        invited_by_name=inviter.name if inviter else "Unknown",
        role=invitation.role,
        expires_at=invitation.expires_at,
    )


@router.post("/{token}/accept", status_code=status.HTTP_200_OK)
async def accept_invitation(
    token: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Invitation).where(Invitation.token == token))
    invitation = result.scalar_one_or_none()
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    if invitation.expires_at < datetime.utcnow():
        invitation.status = InvitationStatus.expired
        await db.commit()
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invitation expired")

    if invitation.status != InvitationStatus.pending:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=f"Invitation is {invitation.status.value}")

    # Add user to org if not already
    if current_user.organization_id != invitation.org_id:
        current_user.organization_id = invitation.org_id
        if current_user.role == UserRole.owner:
            # Don't downgrade an owner of another org — edge case, reject
            raise HTTPException(status_code=400, detail="Cannot join another org as owner")
        if current_user.role != UserRole.child:
            current_user.role = UserRole.member

    # Add to space_members (upsert — if already a member, upgrade role if invited as editor)
    existing = await db.execute(
        select(SpaceMember).where(
            SpaceMember.space_id == invitation.space_id,
            SpaceMember.user_id == current_user.id,
        )
    )
    existing_m = existing.scalar_one_or_none()
    if existing_m:
        if invitation.role == InvitationRole.editor and existing_m.role == SpaceMemberRole.viewer:
            existing_m.role = SpaceMemberRole.editor
    else:
        role = SpaceMemberRole.editor if invitation.role == InvitationRole.editor else SpaceMemberRole.viewer
        db.add(SpaceMember(space_id=invitation.space_id, user_id=current_user.id, role=role))

    invitation.status = InvitationStatus.accepted
    await db.commit()
    return {"detail": "Invitation accepted"}
