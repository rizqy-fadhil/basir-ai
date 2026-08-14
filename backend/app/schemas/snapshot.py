"""Pydantic schemas for the `snapshot` endpoint."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SnapshotOut(BaseModel):
    """Response schema for a single snapshot row (GET /cafes/{cafe_id}/snapshot)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    area_kamera: str
    url: str
    captured_at: datetime
    updated_at: datetime
