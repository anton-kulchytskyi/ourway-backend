from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import secrets

from app.database import get_db
from app.core.deps import get_current_user, get_current_org_user
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.models.space import Space, SpaceMember, SpaceMemberRole, Invitation, InvitationRole, InvitationStatus
from app.schemas.invitation import InvitationCreate, InvitationResponse, InvitationPublicInfo

router = APIRouter(prefix="/invitations", tags=["invitations"])

INVITE_EXPIRES_DAYS = 7


@router.post("", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    body: InvitationCreate,
    current_user: User = Depends(get_current_org_user),
    db: AsyncSession = Depends(get_db),
):
    if body.space_id is not None:
        # Space-level invite: requester must be owner of that space
        m_result = await db.execute(
            select(SpaceMember).where(
                SpaceMember.space_id == body.space_id,
                SpaceMember.user_id == current_user.id,
            )
        )
        membership = m_result.scalar_one_or_none()
        if not membership or membership.role != SpaceMemberRole.owner:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only space owner can invite")
    else:
        # Org-level invite: requester must be org owner
        if current_user.role != UserRole.owner:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only org owner can invite to organization")

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

    org_result = await db.execute(select(Organization).where(Organization.id == invitation.org_id))
    org = org_result.scalar_one_or_none()

    inviter_result = await db.execute(select(User).where(User.id == invitation.invited_by))
    inviter = inviter_result.scalar_one_or_none()

    space_name = None
    space_emoji = None
    if invitation.space_id:
        space_result = await db.execute(select(Space).where(Space.id == invitation.space_id))
        space = space_result.scalar_one_or_none()
        if space:
            space_name = space.name
            space_emoji = space.emoji

    return InvitationPublicInfo(
        token=invitation.token,
        org_name=org.name if org else "Family",
        space_name=space_name,
        space_emoji=space_emoji,
        invited_by_name=inviter.name if inviter else "Unknown",
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
        if current_user.role == UserRole.owner and current_user.organization_id:
            # Check if their org is empty (only themselves)
            other_members = await db.execute(
                select(User).where(
                    User.organization_id == current_user.organization_id,
                    User.id != current_user.id,
                )
            )
            if other_members.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Cannot leave your org while it has other members")
            org_result = await db.execute(
                select(Organization).where(Organization.id == current_user.organization_id)
            )
            org = org_result.scalar_one_or_none()
            if org:
                await db.delete(org)
                await db.flush()

        current_user.organization_id = invitation.org_id
        if current_user.role != UserRole.child:
            current_user.role = UserRole.member

    # Add to space if this is a space-level invite
    if invitation.space_id:
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
