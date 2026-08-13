"""SQLAlchemy model for the `status_meja` table."""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

_VALID_STATUS = ("available", "partial", "occupied")


class StatusMeja(Base):
    """
    Stores the latest occupancy status for a single table.

    Exactly one row exists per meja. meja_id is simultaneously the primary key
    and the foreign key to meja.id (1-to-1 relationship).
    """

    __tablename__ = "status_meja"
    __table_args__ = (
        CheckConstraint(
            "status IN ('available', 'partial', 'occupied')",
            name="ck_status_meja_status_valid",
        ),
        CheckConstraint("terisi >= 0", name="ck_status_meja_terisi_non_negative"),
    )

    meja_id: Mapped[int] = mapped_column(
        ForeignKey("meja.id", ondelete="CASCADE"), primary_key=True
    )
    terisi: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default="0"
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    # relationships
    meja: Mapped["Meja"] = relationship("Meja", back_populates="status_meja")  # noqa: F821
