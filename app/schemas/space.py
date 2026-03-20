from pydantic import BaseModel


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

    model_config = {"from_attributes": True}
