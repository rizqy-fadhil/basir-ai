"""SQLAlchemy model for the `meja` table."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    SmallInteger,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.types import JsonbOrJson


class Meja(Base):
    """Represents a table (meja) inside a cafe, with its ROI polygon and capacity."""

    __tablename__ = "meja"
    __table_args__ = (
        UniqueConstraint("cafe_id", "nomor_meja", name="uq_meja_cafe_nomor"),
        CheckConstraint("kapasitas > 0", name="ck_meja_kapasitas_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cafe_id: Mapped[int] = mapped_column(
        ForeignKey("cafe.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nomor_meja: Mapped[int] = mapped_column(nullable=False)
    kapasitas: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    roi: Mapped[dict | None] = mapped_column(JsonbOrJson, nullable=True)
    aktif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # relationships
    cafe: Mapped["Cafe"] = relationship("Cafe", back_populates="mejas")  # noqa: F821
    status_meja: Mapped["StatusMeja | None"] = relationship(  # noqa: F821
        "StatusMeja", back_populates="meja", cascade="all, delete-orphan", uselist=False
    )
