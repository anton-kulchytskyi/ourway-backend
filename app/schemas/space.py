from pydantic import BaseModel
from app.models.space import SpaceMemberRole


class SpaceCreate(BaseModel):
    name: str
    emoji: str | None = None


class SpaceUpdate(BaseModel):
    name: str | None = None
    emoji: str | None = None


class SpaceResponse(BaseModel):
    id: int
    name: str
    emoji: str | None
    organization_id: int
    my_role: SpaceMemberRole | None = None

    model_config = {"from_attributes": True}


class SpaceMemberResponse(BaseModel):
    id: int
    space_id: int
    user_id: int
    role: SpaceMemberRole

    model_config = {"from_attributes": True}


class SpaceMemberRoleUpdate(BaseModel):
    role: SpaceMemberRole


class SpaceMemberAdd(BaseModel):
    user_id: int
    role: SpaceMemberRole = SpaceMemberRole.viewer
