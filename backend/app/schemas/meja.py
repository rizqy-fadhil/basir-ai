"""Pydantic schemas for the `meja` (table) endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class MejaOut(BaseModel):
    """Response schema for a single meja row (GET /cafes/{cafe_id}/meja)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nomor_meja: int
    kapasitas: int
    roi: Any | None
    aktif: bool
