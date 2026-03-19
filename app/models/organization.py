from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    default_locale: Mapped[str] = mapped_column(String(10), default="en", nullable=False)

    members: Mapped[list["User"]] = relationship(back_populates="organization")  # noqa: F821
    spaces: Mapped[list["Space"]] = relationship(back_populates="organization")  # noqa: F821
