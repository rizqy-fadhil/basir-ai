"""SQLAlchemy model for the `cafe` table."""

from datetime import datetime

from sqlalchemy import Boolean, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Cafe(Base):
    """Represents a cafe that owns one or more tables and camera snapshots."""

    __tablename__ = "cafe"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nama: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="Asia/Jakarta"
    )
    aktif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # relationships
    mejas: Mapped[list["Meja"]] = relationship(  # noqa: F821
        "Meja", back_populates="cafe", cascade="all, delete-orphan"
    )
    snapshots: Mapped[list["Snapshot"]] = relationship(  # noqa: F821
        "Snapshot", back_populates="cafe", cascade="all, delete-orphan"
    )
