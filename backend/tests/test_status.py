"""Tests for GET /cafes/{cafe_id}/status and POST /internal/status."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Cafe, Meja, StatusMeja

VALID_UPDATED_AT = "2026-08-14T06:00:00Z"
API_KEY = "test-secret-key"  # set in conftest via os.environ


# ---------------------------------------------------------------------------
# GET /cafes/{cafe_id}/status
# ---------------------------------------------------------------------------


class TestGetCafeStatus:
    """GET /cafes/{cafe_id}/status"""

    def test_returns_status_for_cafe(
        self, client: TestClient, meja_with_status: tuple[Meja, StatusMeja], cafe: Cafe
    ):
        """Should return the occupancy aggregate including each meja's status."""
        resp = client.get(f"/cafes/{cafe.id}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cafe_id"] == cafe.id
        assert len(data["meja"]) == 1
        item = data["meja"][0]
        assert item["nomor_meja"] == 1
        assert item["kapasitas"] == 2
        assert item["terisi"] == 1
        assert item["status"] == "partial"

    def test_okupansi_persen_calculation(
        self, client: TestClient, cafe: Cafe, db: Session
    ):
        """okupansi_persen = round(terisi_total / kapasitas_total * 100)."""
        # 2 mejas: kapasitas 4 total, terisi 2 total → 50 %
        m1 = Meja(cafe_id=cafe.id, nomor_meja=1, kapasitas=2)
        m2 = Meja(cafe_id=cafe.id, nomor_meja=2, kapasitas=2)
        db.add_all([m1, m2])
        db.commit()  # commit so meja IDs exist in DB before adding status rows

        sm1 = StatusMeja(
            meja_id=m1.id,
            terisi=2,
            status="occupied",
            updated_at=datetime(2026, 8, 14, 6, 0, tzinfo=timezone.utc),
        )
        sm2 = StatusMeja(
            meja_id=m2.id,
            terisi=0,
            status="available",
            updated_at=datetime(2026, 8, 14, 6, 0, tzinfo=timezone.utc),
        )
        db.add_all([sm1, sm2])
        db.commit()

        resp = client.get(f"/cafes/{cafe.id}/status")
        assert resp.status_code == 200
        assert resp.json()["okupansi_persen"] == 50

    def test_meja_without_status_has_null_status(
        self, client: TestClient, meja: Meja, cafe: Cafe
    ):
        """Mejas with no status row must appear with terisi=0, status=null."""
        resp = client.get(f"/cafes/{cafe.id}/status")
        assert resp.status_code == 200
        data = resp.json()
        item = data["meja"][0]
        assert item["terisi"] == 0
        assert item["status"] is None
        assert data["okupansi_persen"] is None
        assert data["updated_at"] is None

    def test_404_for_unknown_cafe(self, client: TestClient):
        resp = client.get("/cafes/9999/status")
        assert resp.status_code == 404

    def test_response_shape(
        self, client: TestClient, meja_with_status: tuple[Meja, StatusMeja], cafe: Cafe
    ):
        """Top-level response must include cafe_id, okupansi_persen, updated_at, meja."""
        resp = client.get(f"/cafes/{cafe.id}/status")
        data = resp.json()
        for field in ("cafe_id", "okupansi_persen", "updated_at", "meja"):
            assert field in data

    def test_updated_at_is_most_recent(
        self, client: TestClient, cafe: Cafe, db: Session
    ):
        """updated_at in the response must be the latest updated_at across all mejas."""
        m1 = Meja(cafe_id=cafe.id, nomor_meja=1, kapasitas=2)
        m2 = Meja(cafe_id=cafe.id, nomor_meja=2, kapasitas=2)
        db.add_all([m1, m2])
        db.commit()  # commit so meja IDs exist in DB before adding status rows

        earlier = datetime(2026, 8, 14, 5, 0, tzinfo=timezone.utc)
        later = datetime(2026, 8, 14, 6, 30, tzinfo=timezone.utc)

        db.add_all(
            [
                StatusMeja(
                    meja_id=m1.id, terisi=0, status="available", updated_at=earlier
                ),
                StatusMeja(meja_id=m2.id, terisi=1, status="partial", updated_at=later),
            ]
        )
        db.commit()

        resp = client.get(f"/cafes/{cafe.id}/status")
        assert resp.status_code == 200
        # updated_at must equal the later timestamp
        assert "06:30" in resp.json()["updated_at"]


# ---------------------------------------------------------------------------
# POST /internal/status
# ---------------------------------------------------------------------------


class TestUpsertStatus:
    """POST /internal/status"""

    def _payload(self, meja_id: int, terisi: int = 1, status: str = "partial") -> dict:
        return {
            "meja_id": meja_id,
            "terisi": terisi,
            "status": status,
            "updated_at": VALID_UPDATED_AT,
        }

    def _post(self, client: TestClient, payload: dict, key: str = API_KEY):
        return client.post(
            "/internal/status",
            json=payload,
            headers={"X-API-Key": key},
        )

    # --- Auth tests ---

    def test_rejects_missing_api_key(self, client: TestClient, meja: Meja):
        """Request without X-API-Key must be rejected with 401."""
        resp = client.post("/internal/status", json=self._payload(meja.id))
        assert resp.status_code == 401

    def test_rejects_wrong_api_key(self, client: TestClient, meja: Meja):
        """Wrong API key must be rejected with 401."""
        resp = client.post(
            "/internal/status",
            json=self._payload(meja.id),
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 401

    def test_accepts_correct_api_key(self, client: TestClient, meja: Meja):
        """Correct API key must allow the request through."""
        resp = self._post(client, self._payload(meja.id))
        assert resp.status_code == 200

    # --- Insert path ---

    def test_inserts_new_status(self, client: TestClient, meja: Meja, db: Session):
        """First POST for a meja should insert a new status row."""
        resp = self._post(client, self._payload(meja.id, terisi=1, status="partial"))
        assert resp.status_code == 200
        assert resp.json()["action"] == "inserted"
        assert resp.json()["meja_id"] == meja.id

        sm = db.get(StatusMeja, meja.id)
        assert sm is not None
        assert sm.terisi == 1
        assert sm.status == "partial"

    # --- Update path ---

    def test_updates_existing_status(
        self, client: TestClient, meja_with_status: tuple[Meja, StatusMeja], db: Session
    ):
        """Second POST for the same meja must update the existing row."""
        meja, _ = meja_with_status
        resp = self._post(client, self._payload(meja.id, terisi=2, status="occupied"))
        assert resp.status_code == 200
        assert resp.json()["action"] == "updated"

        db.expire_all()
        sm = db.get(StatusMeja, meja.id)
        assert sm.terisi == 2
        assert sm.status == "occupied"

    def test_no_duplicate_rows_created(
        self, client: TestClient, meja: Meja, db: Session
    ):
        """Multiple POSTs for the same meja must not create more than one status row."""
        for _ in range(3):
            self._post(client, self._payload(meja.id))

        count = db.query(StatusMeja).filter_by(meja_id=meja.id).count()
        assert count == 1

    # --- Validation errors ---

    def test_rejects_invalid_status_value(self, client: TestClient, meja: Meja):
        """status must be one of available / partial / occupied."""
        payload = self._payload(meja.id)
        payload["status"] = "full"  # invalid
        resp = self._post(client, payload)
        assert resp.status_code == 422

    def test_rejects_negative_terisi(self, client: TestClient, meja: Meja):
        """terisi must not be negative."""
        payload = self._payload(meja.id)
        payload["terisi"] = -1
        resp = self._post(client, payload)
        assert resp.status_code == 422

    def test_rejects_missing_meja_id(self, client: TestClient):
        """Payload without meja_id must fail validation."""
        resp = self._post(
            client, {"terisi": 0, "status": "available", "updated_at": VALID_UPDATED_AT}
        )
        assert resp.status_code == 422

    def test_404_for_unknown_meja(self, client: TestClient, cafe: Cafe):
        """meja_id that doesn't exist must return 404."""
        resp = self._post(client, self._payload(meja_id=9999))
        assert resp.status_code == 404
        assert "9999" in resp.json()["detail"]

    def test_all_valid_status_values_accepted(
        self, client: TestClient, db: Session, cafe: Cafe
    ):
        """Each of the three allowed status values must be accepted."""
        for i, s in enumerate(["available", "partial", "occupied"], start=10):
            m = Meja(cafe_id=cafe.id, nomor_meja=i, kapasitas=2)
            db.add(m)
            db.commit()  # commit so the router's session can see this meja
            resp = self._post(client, self._payload(m.id, status=s))
            assert resp.status_code == 200, f"Status '{s}' was unexpectedly rejected"
        db.commit()

    def test_zero_terisi_is_valid(self, client: TestClient, meja: Meja):
        """terisi=0 must be accepted (boundary value)."""
        resp = self._post(client, self._payload(meja.id, terisi=0, status="available"))
        assert resp.status_code == 200
