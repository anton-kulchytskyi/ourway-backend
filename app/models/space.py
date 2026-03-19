from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Space(Base):
    __tablename__ = "spaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    emoji: Mapped[str | None] = mapped_column(String(10), nullable=True)

    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)

    organization: Mapped["Organization"] = relationship(back_populates="spaces")  # noqa: F821
    tasks: Mapped[list["Task"]] = relationship(back_populates="space")  # noqa: F821
