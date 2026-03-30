from pydantic import BaseModel
from datetime import date, datetime, time
from app.models.daily_plan import DailyPlanStatus


class DailyPlanCreate(BaseModel):
    user_id: int | None = None  # defaults to current user; owner can set a child's id
    date: date


class DailyPlanResponse(BaseModel):
    id: int
    user_id: int
    date: date
    status: DailyPlanStatus
    confirmed_at: datetime | None
    confirmed_by: int | None

    model_config = {"from_attributes": True}


# --- Assembled day view ---

class ScheduleItemOut(BaseModel):
    title: str
    time_start: time
    time_end: time


class EventItemOut(BaseModel):
    id: int
    title: str
    time_start: time | None
    time_end: time | None


class TaskItemOut(BaseModel):
    id: int
    title: str
    time_start: time | None
    status: str
    points: int


class DayView(BaseModel):
    plan: DailyPlanResponse
    schedule_items: list[ScheduleItemOut]
    events: list[EventItemOut]
    tasks: list[TaskItemOut]


class FamilyMemberDay(BaseModel):
    user_id: int
    user_name: str
    role: str
    day: DayView
