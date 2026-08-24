"""Pydantic schemas for the `snapshot` endpoint."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SnapshotOut(BaseModel):
    """Response schema for a single snapshot row (GET /cafes/{cafe_id}/snapshot)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    area_kamera: str
    url: str
    captured_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# POST /internal/snapshot — inference service → backend
# ---------------------------------------------------------------------------


class SnapshotUpsertRequest(BaseModel):
    """Payload sent by the inference service when a new snapshot is captured."""

    cafe_id: int = Field(..., gt=0, description="Cafe yang memiliki snapshot.")
    area_kamera: str = Field(
        ..., max_length=120, description="Area kamera, misal 'workspace'."
    )
    url: str = Field(
        ..., description="URL relatif snapshot yang bisa di-serve via HTTP."
    )
    captured_at: datetime = Field(
        ..., description="Waktu frame di-capture oleh inference."
    )


class SnapshotUpsertResponse(BaseModel):
    """Response for POST /internal/snapshot."""

    action: Literal["inserted", "updated"]
    snapshot_id: int
