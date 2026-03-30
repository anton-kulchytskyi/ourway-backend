from sqlalchemy import Integer, String, ForeignKey, Date, Time, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ARRAY
from datetime import date, time

from app.database import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date | None] = mapped_column(Date, nullable=True)        # None if flexible date
    time_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    time_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    is_fixed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # False = find a free slot
    duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)       # required if is_fixed=False
    find_before: Mapped[date | None] = mapped_column(Date, nullable=True)          # deadline for scheduling
    participants: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False, default=list)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    organization: Mapped["Organization"] = relationship()  # noqa: F821
    creator: Mapped["User | None"] = relationship()  # noqa: F821
