from sqlalchemy import Integer, ForeignKey, Date, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import date, datetime
import enum

from app.database import Base


class DailyPlanStatus(str, enum.Enum):
    draft = "draft"
    confirmed = "confirmed"
    completed = "completed"


class DailyPlan(Base):
    __tablename__ = "daily_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[DailyPlanStatus] = mapped_column(
        Enum(DailyPlanStatus, name="dailyplanstatus"),
        default=DailyPlanStatus.draft,
        nullable=False,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    user: Mapped["User"] = relationship(foreign_keys=[user_id])  # noqa: F821
    confirmer: Mapped["User | None"] = relationship(foreign_keys=[confirmed_by])  # noqa: F821
