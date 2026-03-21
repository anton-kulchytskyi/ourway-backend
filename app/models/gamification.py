from sqlalchemy import String, Integer, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class GamificationProfile(Base):
    __tablename__ = "gamification_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    points_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    streak_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_activity: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    user: Mapped["User"] = relationship(back_populates="gamification_profile")  # noqa: F821
    rewards: Mapped[list["Reward"]] = relationship(back_populates="profile")


class Reward(Base):
    __tablename__ = "rewards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    points_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    is_claimed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    profile_id: Mapped[int] = mapped_column(ForeignKey("gamification_profiles.id"), nullable=False)

    profile: Mapped["GamificationProfile"] = relationship(back_populates="rewards")
