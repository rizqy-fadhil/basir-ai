"""Router: GET /cafes/{cafe_id}/meja

Returns the list of active tables (meja) for a given cafe.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Cafe, Meja
from app.schemas.meja import MejaOut

router = APIRouter(prefix="/cafes", tags=["meja"])


@router.get(
    "/{cafe_id}/meja",
    response_model=list[MejaOut],
    summary="Daftar meja aktif untuk sebuah cafe",
)
def list_meja(cafe_id: int, db: Session = Depends(get_db)) -> list[MejaOut]:
    """Return all active tables (aktif=true) for the given cafe.

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
    return mejas
