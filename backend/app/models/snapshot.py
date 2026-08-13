"""SQLAlchemy model for the `snapshot` table."""

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Snapshot(Base):
    """
    Stores the latest camera snapshot for a given camera area inside a cafe.

    Rows are upserted (not accumulated), so the table holds exactly one row
    per (cafe_id, area_kamera) pair.
    """

    __tablename__ = "snapshot"
    __table_args__ = (
        UniqueConstraint("cafe_id", "area_kamera", name="uq_snapshot_cafe_area"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cafe_id: Mapped[int] = mapped_column(
        ForeignKey("cafe.id", ondelete="CASCADE"), nullable=False, index=True
    )
    area_kamera: Mapped[str] = mapped_column(String(120), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    # relationships
    cafe: Mapped["Cafe"] = relationship("Cafe", back_populates="snapshots")  # noqa: F821
