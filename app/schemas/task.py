from pydantic import BaseModel
from datetime import datetime, date, time
from app.models.task import TaskStatus, TaskPriority


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    status: TaskStatus = TaskStatus.backlog
    priority: TaskPriority = TaskPriority.medium
    points: int = 0
    due_date: datetime | None = None
    scheduled_date: date | None = None
    space_id: int
    assignee_id: int | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    points: int | None = None
    due_date: datetime | None = None
    scheduled_date: date | None = None
    assignee_id: int | None = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    points: int
    due_date: datetime | None
    scheduled_date: date | None
    time_start: time | None
    created_at: datetime
    updated_at: datetime
    space_id: int
    creator_id: int
    assignee_id: int | None

    model_config = {"from_attributes": True}
