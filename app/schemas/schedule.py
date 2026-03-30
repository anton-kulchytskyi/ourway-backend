from pydantic import BaseModel, field_validator
from datetime import date, time


class ScheduleCreate(BaseModel):
    title: str
    weekdays: list[int]  # [1..7], Mon=1, Sun=7
    time_start: time
    time_end: time
    valid_from: date | None = None
    valid_until: date | None = None
    user_id: int | None = None  # defaults to current user; owner can set a child's id

    @field_validator("weekdays")
    @classmethod
    def weekdays_valid(cls, v: list[int]) -> list[int]:
        if not v:
            raise ValueError("weekdays must not be empty")
        if any(d < 1 or d > 7 for d in v):
            raise ValueError("weekdays values must be 1–7")
        return sorted(set(v))


class ScheduleUpdate(BaseModel):
    title: str | None = None
    weekdays: list[int] | None = None
    time_start: time | None = None
    time_end: time | None = None
    valid_from: date | None = None
    valid_until: date | None = None

    @field_validator("weekdays")
    @classmethod
    def weekdays_valid(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return v
        if not v:
            raise ValueError("weekdays must not be empty")
        if any(d < 1 or d > 7 for d in v):
            raise ValueError("weekdays values must be 1–7")
        return sorted(set(v))


class ScheduleResponse(BaseModel):
    id: int
    title: str
    weekdays: list[int]
    time_start: time
    time_end: time
    valid_from: date | None
    valid_until: date | None
    user_id: int
    created_by: int | None

    model_config = {"from_attributes": True}
