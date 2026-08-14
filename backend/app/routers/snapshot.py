"""Router: GET /cafes/{cafe_id}/snapshot

Returns the latest camera snapshot(s) for a given cafe.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Cafe, Snapshot
from app.schemas.snapshot import SnapshotOut

router = APIRouter(prefix="/cafes", tags=["snapshot"])


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
