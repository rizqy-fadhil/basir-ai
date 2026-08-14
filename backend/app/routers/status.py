"""Router: GET /cafes/{cafe_id}/status  and  POST /internal/status

GET  — aggregate occupancy status for all tables in a cafe.
POST — internal endpoint for the inference service to upsert table status.
"""

from __future__ import annotations

import os
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Cafe, Meja, StatusMeja
from app.schemas.status import (
    MejaStatusItem,
    OkupansiResponse,
    StatusUpsertRequest,
    StatusUpsertResponse,
)

# ---------------------------------------------------------------------------
# Routers (two separate prefixes, kept in one file as per ARCHITECTURE.md)
# ---------------------------------------------------------------------------

cafe_router = APIRouter(prefix="/cafes", tags=["status"])
internal_router = APIRouter(prefix="/internal", tags=["internal"])


# ---------------------------------------------------------------------------
# GET /cafes/{cafe_id}/status
# ---------------------------------------------------------------------------


@cafe_router.get(
    "/{cafe_id}/status",
    response_model=OkupansiResponse,
    summary="Status okupansi terkini semua meja untuk sebuah cafe",
)
def get_cafe_status(cafe_id: int, db: Session = Depends(get_db)) -> OkupansiResponse:
    """Return the current occupancy status for every active table in the cafe.

    Tables that have no status row yet are included with terisi=0 and status=None.
    Raises 404 if the cafe does not exist.
    """
    cafe = db.get(Cafe, cafe_id)
    if cafe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cafe dengan id={cafe_id} tidak ditemukan.",
        )

    mejas = (
        db.query(Meja)
        .filter(Meja.cafe_id == cafe_id, Meja.aktif.is_(True))
        .order_by(Meja.nomor_meja)
        .all()
    )

    items: list[MejaStatusItem] = []
    latest_updated_at: datetime | None = None
    total_kapasitas = 0
    total_terisi = 0

    for meja in mejas:
        sm: StatusMeja | None = meja.status_meja
        terisi = sm.terisi if sm else 0
        meja_status = sm.status if sm else None

        if sm and (
            latest_updated_at is None or sm.updated_at > latest_updated_at
        ):
            latest_updated_at = sm.updated_at

        total_kapasitas += meja.kapasitas
        total_terisi += terisi

        items.append(
            MejaStatusItem(
                nomor_meja=meja.nomor_meja,
                kapasitas=meja.kapasitas,
                terisi=terisi,
                status=meja_status,
            )
        )

    if total_kapasitas > 0 and latest_updated_at is not None:
        okupansi_persen = round((total_terisi / total_kapasitas) * 100)
    else:
        okupansi_persen = None

    return OkupansiResponse(
        cafe_id=cafe_id,
        okupansi_persen=okupansi_persen,
        updated_at=latest_updated_at,
        meja=items,
    )


# ---------------------------------------------------------------------------
# POST /internal/status
# ---------------------------------------------------------------------------

_BACKEND_API_KEY: str = os.environ.get("BACKEND_API_KEY", "")


def _verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Dependency: validate the X-API-Key header against BACKEND_API_KEY env var."""
    if not _BACKEND_API_KEY:
        # If the server is misconfigured (no key set), deny all requests to
        # prevent accidental open access.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="BACKEND_API_KEY tidak dikonfigurasi di server.",
        )
    if x_api_key != _BACKEND_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key tidak valid atau tidak diberikan.",
        )


@internal_router.post(
    "/status",
    response_model=StatusUpsertResponse,
    status_code=status.HTTP_200_OK,
    summary="Inference service mengirim status terbaru per meja",
)
def upsert_status(
    payload: StatusUpsertRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_verify_api_key),
) -> StatusUpsertResponse:
    """Upsert the latest occupancy status for a single table.

    - If a status_meja row for meja_id already exists, update it in-place.
    - If it does not exist yet, insert a new row.
    - No history rows are created.
    - Returns 404 if the meja_id does not exist.
    - Returns 401 if the X-API-Key header is missing or incorrect.
    """
    meja = db.get(Meja, payload.meja_id)
    if meja is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meja dengan id={payload.meja_id} tidak ditemukan.",
        )

    existing: StatusMeja | None = db.get(StatusMeja, payload.meja_id)

    if existing is not None:
        existing.terisi = payload.terisi
        existing.status = payload.status.value
        existing.updated_at = payload.updated_at
        db.commit()
        return StatusUpsertResponse(action="updated", meja_id=payload.meja_id)

    new_status = StatusMeja(
        meja_id=payload.meja_id,
        terisi=payload.terisi,
        status=payload.status.value,
        updated_at=payload.updated_at,
    )
    db.add(new_status)
    db.commit()
    return StatusUpsertResponse(action="inserted", meja_id=payload.meja_id)
