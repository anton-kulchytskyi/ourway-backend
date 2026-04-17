from sqlalchemy import String, Text, Integer, ForeignKey, Enum, DateTime, Date, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date, time
import enum

from app.database import Base


class TaskStatus(str, enum.Enum):
    backlog = "backlog"
    todo = "todo"
    in_progress = "in_progress"
    blocked = "blocked"
    done = "done"


class TaskPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class TaskSource(str, enum.Enum):
    manual = "manual"
    schedule = "schedule"
    family_space = "family_space"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.backlog, nullable=False)
    priority: Mapped[TaskPriority] = mapped_column(Enum(TaskPriority), default=TaskPriority.medium, nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Daily flow fields
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    time_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    source: Mapped[TaskSource] = mapped_column(Enum(TaskSource), default=TaskSource.manual, nullable=False)

    progress_current: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_total: Mapped[int | None] = mapped_column(Integer, nullable=True)

    space_id: Mapped[int] = mapped_column(ForeignKey("spaces.id"), nullable=False)
    creator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    space: Mapped["Space"] = relationship(back_populates="tasks")  # noqa: F821
    creator: Mapped["User"] = relationship(back_populates="tasks_created", foreign_keys=[creator_id])  # noqa: F821
    assignee: Mapped["User | None"] = relationship(back_populates="tasks_assigned", foreign_keys=[assignee_id])  # noqa: F821
