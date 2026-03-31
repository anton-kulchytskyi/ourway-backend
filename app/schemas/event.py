import datetime

from pydantic import BaseModel, model_validator


class EventCreate(BaseModel):
    title: str
    date: datetime.date | None = None
    time_start: datetime.time | None = None
    time_end: datetime.time | None = None
    is_fixed: bool = True
    duration_min: int | None = None
    find_before: datetime.date | None = None
    participants: list[int] = []

    @model_validator(mode="after")
    def check_flexible_fields(self) -> "EventCreate":
        if not self.is_fixed and not self.duration_min:
            raise ValueError("duration_min is required when is_fixed=False")
        return self


class EventUpdate(BaseModel):
    title: str | None = None
    date: datetime.date | None = None
    time_start: datetime.time | None = None
    time_end: datetime.time | None = None
    is_fixed: bool | None = None
    duration_min: int | None = None
    find_before: datetime.date | None = None
    participants: list[int] | None = None


class EventResponse(BaseModel):
    id: int
    title: str
    organization_id: int
    date: datetime.date | None
    time_start: datetime.time | None
    time_end: datetime.time | None
    is_fixed: bool
    duration_min: int | None
    find_before: datetime.date | None
    participants: list[int]
    created_by: int | None

    model_config = {"from_attributes": True}
