"""Router: GET /cafes/{cafe_id}/snapshot  and  POST /internal/snapshot

GET  — returns the latest camera snapshot(s) for a given cafe.
POST — internal endpoint for the inference service to upsert snapshot metadata.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Cafe, Snapshot
from app.routers.status import _verify_api_key
from app.schemas.snapshot import (
    SnapshotOut,
    SnapshotUpsertRequest,
    SnapshotUpsertResponse,
)

router = APIRouter(prefix="/cafes", tags=["snapshot"])
internal_snapshot_router = APIRouter(prefix="/internal", tags=["internal"])


@router.get(
    "/{cafe_id}/snapshot",
    response_model=list[SnapshotOut],
    summary="Snapshot kamera terbaru untuk sebuah cafe",
)
def list_snapshots(cafe_id: int, db: Session = Depends(get_db)) -> list[SnapshotOut]:
    """Return the latest snapshot for every camera area belonging to the given cafe.

    Each (cafe_id, area_kamera) pair has exactly one row (upsert semantics), so
    this endpoint returns one entry per camera area.

    Raises 404 if the cafe does not exist.
    """
    cafe = db.get(Cafe, cafe_id)
    if cafe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cafe dengan id={cafe_id} tidak ditemukan.",
        )

    snapshots = (
        db.query(Snapshot)
        .filter(Snapshot.cafe_id == cafe_id)
        .order_by(Snapshot.area_kamera)
        .all()
    )
    return snapshots


# ---------------------------------------------------------------------------
# POST /internal/snapshot
# ---------------------------------------------------------------------------


@internal_snapshot_router.post(
    "/snapshot",
    response_model=SnapshotUpsertResponse,
    status_code=status.HTTP_200_OK,
    summary="Inference service mengirim metadata snapshot terbaru",
)
def upsert_snapshot(
    payload: SnapshotUpsertRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_verify_api_key),
) -> SnapshotUpsertResponse:
    """Upsert the latest snapshot for a (cafe_id, area_kamera) pair.

    - If a snapshot row already exists, update url, captured_at, and updated_at.
    - If it does not exist yet, insert a new row.
    - Returns 404 if the cafe_id does not exist.
    - Returns 401 if the X-API-Key header is missing or incorrect.
    """
    cafe = db.get(Cafe, payload.cafe_id)
    if cafe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cafe dengan id={payload.cafe_id} tidak ditemukan.",
        )

    existing: Snapshot | None = (
        db.query(Snapshot)
        .filter(
            Snapshot.cafe_id == payload.cafe_id,
            Snapshot.area_kamera == payload.area_kamera,
        )
        .first()
    )

    if existing is not None:
        existing.url = payload.url
        existing.captured_at = payload.captured_at
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        return SnapshotUpsertResponse(action="updated", snapshot_id=existing.id)

    new_snapshot = Snapshot(
        cafe_id=payload.cafe_id,
        area_kamera=payload.area_kamera,
        url=payload.url,
        captured_at=payload.captured_at,
    )
    db.add(new_snapshot)
    db.commit()
    db.refresh(new_snapshot)
    return SnapshotUpsertResponse(action="inserted", snapshot_id=new_snapshot.id)
