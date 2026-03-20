from sqlalchemy import String, Boolean, Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


class UserRole(str, enum.Enum):
    owner = "owner"
    member = "member"
    child = "child"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.member, nullable=False)
    locale: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    telegram_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Child-specific fields
    autonomy_level: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1, 2, or 3
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)

    organization: Mapped["Organization"] = relationship(back_populates="members")  # noqa: F821
    tasks_assigned: Mapped[list["Task"]] = relationship(back_populates="assignee", foreign_keys="Task.assignee_id")  # noqa: F821
    tasks_created: Mapped[list["Task"]] = relationship(back_populates="creator", foreign_keys="Task.creator_id")  # noqa: F821
    gamification_profile: Mapped["GamificationProfile"] = relationship(back_populates="user")  # noqa: F821
    space_memberships: Mapped[list["SpaceMember"]] = relationship(back_populates="user")  # noqa: F821
