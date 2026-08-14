"""Pydantic schemas for status endpoints.

Covers:
  - POST /internal/status  (request + response)
  - GET  /cafes/{cafe_id}/status (response)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StatusEnum(str, Enum):
    """Allowed occupancy status values — must stay lowercase to match DB and API contract."""

    available = "available"
    partial = "partial"
    occupied = "occupied"


# ---------------------------------------------------------------------------
# POST /internal/status — inference service → backend
# ---------------------------------------------------------------------------


class StatusUpsertRequest(BaseModel):
    """Payload sent by the inference service when occupancy is updated."""

    meja_id: int = Field(..., gt=0, description="Primary key of the meja being updated.")
    terisi: int = Field(
        ...,
        ge=0,
        description="Number of seats currently occupied. Must be ≥ 0.",
    )
    status: StatusEnum = Field(
        ...,
        description="Occupancy status: available | partial | occupied.",
    )
    updated_at: datetime = Field(
        ...,
        description="Timestamp when the inference result was generated (inference clock).",
    )


class StatusUpsertResponse(BaseModel):
    """Response for POST /internal/status."""

    action: Literal["inserted", "updated"]
    meja_id: int


# ---------------------------------------------------------------------------
# GET /cafes/{cafe_id}/status — per-meja item in the aggregate response
# ---------------------------------------------------------------------------


class MejaStatusItem(BaseModel):
    """One row in the occupancy status list."""

    model_config = ConfigDict(from_attributes=True)

    nomor_meja: int
    kapasitas: int
    terisi: int
    status: str | None  # None when no status row exists yet


class OkupansiResponse(BaseModel):
    """Aggregate occupancy response for GET /cafes/{cafe_id}/status."""

    cafe_id: int
    okupansi_persen: int | None  # None when no status data exists yet
    updated_at: datetime | None  # Most recent status updated_at across all mejas
    meja: list[MejaStatusItem]
