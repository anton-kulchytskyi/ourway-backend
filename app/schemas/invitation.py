from pydantic import BaseModel
from datetime import datetime
from app.models.space import InvitationRole, InvitationStatus


class InvitationCreate(BaseModel):
    space_id: int | None = None
    role: InvitationRole = InvitationRole.editor


class InvitationResponse(BaseModel):
    id: int
    token: str
    space_id: int | None
    org_id: int
    role: InvitationRole
    status: InvitationStatus
    expires_at: datetime

    model_config = {"from_attributes": True}


class InvitationPublicInfo(BaseModel):
    token: str
    org_name: str
    space_name: str | None
    space_emoji: str | None
    invited_by_name: str
    expires_at: datetime
