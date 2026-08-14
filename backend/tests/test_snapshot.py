"""Tests for GET /cafes/{cafe_id}/snapshot."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Cafe, Snapshot


class TestListSnapshot:
    """GET /cafes/{cafe_id}/snapshot"""

    def _make_snapshot(
        self, db: Session, cafe_id: int, area: str = "workspace-1"
    ) -> Snapshot:
        s = Snapshot(
            cafe_id=cafe_id,
            area_kamera=area,
            url="http://example.com/snap.jpg",
            captured_at=datetime(2026, 8, 14, 6, 0, 0, tzinfo=timezone.utc),
        )
        db.add(s)
        db.commit()
        db.refresh(s)
        return s

    def test_returns_snapshots(self, client: TestClient, cafe: Cafe, db: Session):
        """Should return all snapshots for a valid cafe."""
        self._make_snapshot(db, cafe.id, "workspace-1")
        self._make_snapshot(db, cafe.id, "workspace-2")

        resp = client.get(f"/cafes/{cafe.id}/snapshot")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_response_shape(self, client: TestClient, cafe: Cafe, db: Session):
        """Response items must include the documented fields."""
        self._make_snapshot(db, cafe.id)

        resp = client.get(f"/cafes/{cafe.id}/snapshot")
        assert resp.status_code == 200
        item = resp.json()[0]
        for field in ("id", "area_kamera", "url", "captured_at", "updated_at"):
            assert field in item, f"Field '{field}' missing from response"

    def test_empty_for_cafe_with_no_snapshots(self, client: TestClient, db: Session):
        """A cafe with no snapshots should return an empty list."""
        empty_cafe = Cafe(id=42, nama="NoSnap", slug="no-snap")
        db.add(empty_cafe)
        db.commit()

        resp = client.get("/cafes/42/snapshot")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_404_for_unknown_cafe(self, client: TestClient):
        """Should return 404 when the cafe does not exist."""
        resp = client.get("/cafes/9999/snapshot")
        assert resp.status_code == 404

    def test_ordered_by_area_kamera(self, client: TestClient, cafe: Cafe, db: Session):
        """Snapshots must be returned ordered by area_kamera."""
        self._make_snapshot(db, cafe.id, "zone-c")
        self._make_snapshot(db, cafe.id, "zone-a")
        self._make_snapshot(db, cafe.id, "zone-b")

        resp = client.get(f"/cafes/{cafe.id}/snapshot")
        areas = [item["area_kamera"] for item in resp.json()]
        assert areas == sorted(areas)
