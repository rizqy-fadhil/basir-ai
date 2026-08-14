"""Seed script — inserts one demo cafe and four tables matching roi_config.json.

ROI polygons and capacities are kept in sync with inference/config/roi_config.json
so the inference service can process the same tables that exist in the database.

Usage (from backend/ directory):
    python -m app.seed
    # or with explicit env:
    DATABASE_URL=postgresql+psycopg://... python -m app.seed
"""

from __future__ import annotations

import logging

from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import Cafe, Meja

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seed data — mirrors inference/config/roi_config.json
# ---------------------------------------------------------------------------

CAFE_DATA = {
    "id": 1,
    "nama": "Demo Cafe",
    "slug": "demo-cafe",
    "timezone": "Asia/Jakarta",
    "aktif": True,
}

# Each polygon is stored as a GeoJSON-compatible object with a "coordinates"
# key so it can be consumed directly by Shapely in the inference service.
MEJA_DATA = [
    {
        "nomor_meja": 1,
        "kapasitas": 2,
        "roi": {
            "type": "Polygon",
            "coordinates": [[[1, 2], [15, 2], [15, 9], [1, 9], [1, 2]]],
        },
    },
    {
        "nomor_meja": 2,
        "kapasitas": 2,
        "roi": {
            "type": "Polygon",
            "coordinates": [[[17, 2], [31, 2], [31, 9], [17, 9], [17, 2]]],
        },
    },
    {
        "nomor_meja": 3,
        "kapasitas": 4,
        "roi": {
            "type": "Polygon",
            "coordinates": [[[1, 10], [15, 10], [15, 17], [1, 17], [1, 10]]],
        },
    },
    {
        "nomor_meja": 4,
        "kapasitas": 4,
        "roi": {
            "type": "Polygon",
            "coordinates": [[[17, 10], [31, 10], [31, 17], [17, 17], [17, 10]]],
        },
    },
]


def seed() -> None:
    db = SessionLocal()
    try:
        # ---- cafe ----
        existing_cafe = db.get(Cafe, CAFE_DATA["id"])
        if existing_cafe is not None:
            log.info("Cafe id=%d already exists — skipping cafe insert.", CAFE_DATA["id"])
            cafe = existing_cafe
        else:
            cafe = Cafe(**CAFE_DATA)
            db.add(cafe)
            db.flush()  # get the id without committing
            log.info("Inserted cafe: %s (id=%d)", cafe.nama, cafe.id)

        # ---- mejas ----
        for meja_dict in MEJA_DATA:
            existing = (
                db.query(Meja)
                .filter_by(cafe_id=cafe.id, nomor_meja=meja_dict["nomor_meja"])
                .first()
            )
            if existing is not None:
                log.info(
                    "Meja nomor=%d for cafe_id=%d already exists — skipping.",
                    meja_dict["nomor_meja"],
                    cafe.id,
                )
                continue

            meja = Meja(cafe_id=cafe.id, **meja_dict)
            db.add(meja)
            log.info(
                "Inserted meja nomor=%d kapasitas=%d",
                meja.nomor_meja,
                meja.kapasitas,
            )

        db.commit()
        log.info("Seed completed successfully.")

    except IntegrityError as exc:
        db.rollback()
        log.error("IntegrityError during seed — rolled back: %s", exc)
        raise
    except Exception as exc:
        db.rollback()
        log.error("Unexpected error during seed — rolled back: %s", exc)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
