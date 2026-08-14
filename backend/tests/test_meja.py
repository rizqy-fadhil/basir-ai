"""Tests for GET /cafes/{cafe_id}/meja."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Cafe, Meja


class TestListMeja:
    """GET /cafes/{cafe_id}/meja"""

    def test_returns_active_mejas(
        self, client: TestClient, cafe: Cafe, db: Session, meja: Meja
    ):
        """Should return all active mejas for a valid cafe."""
        m2 = Meja(cafe_id=cafe.id, nomor_meja=2, kapasitas=4)
        db.add(m2)
        db.commit()

        resp = client.get(f"/cafes/{cafe.id}/meja")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2  # the fixture meja (nomor 1) + m2

    def test_excludes_inactive_mejas(self, client: TestClient, cafe: Cafe, db: Session):
        """Inactive mejas (aktif=False) must not appear in the response."""
        # The `meja` fixture inserts an active meja first — we add an inactive one
        inactive = Meja(cafe_id=cafe.id, nomor_meja=3, kapasitas=2, aktif=False)
        db.add(inactive)
        db.commit()

        resp = client.get(f"/cafes/{cafe.id}/meja")
        assert resp.status_code == 200
        data = resp.json()
        # Only the active meja from the fixture should appear
        assert all(m["aktif"] for m in data)

    def test_response_shape(self, client: TestClient, meja: Meja, cafe: Cafe):
        """Response items must include the documented fields."""
        resp = client.get(f"/cafes/{cafe.id}/meja")
        assert resp.status_code == 200
        item = resp.json()[0]
        for field in ("id", "nomor_meja", "kapasitas", "roi", "aktif"):
            assert field in item, f"Field '{field}' missing from response"

    def test_empty_for_cafe_with_no_mejas(self, client: TestClient, db: Session):
        """A cafe with no mejas should return an empty list, not 404."""
        empty_cafe = Cafe(id=99, nama="Empty", slug="empty-cafe")
        db.add(empty_cafe)
        db.commit()

        resp = client.get("/cafes/99/meja")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_404_for_unknown_cafe(self, client: TestClient):
        """Should return 404 when the cafe does not exist."""
        resp = client.get("/cafes/9999/meja")
        assert resp.status_code == 404
        assert "9999" in resp.json()["detail"]

    def test_ordered_by_nomor_meja(self, client: TestClient, cafe: Cafe, db: Session):
        """Mejas must be returned in nomor_meja ascending order."""
        m5 = Meja(cafe_id=cafe.id, nomor_meja=5, kapasitas=2)
        m3 = Meja(cafe_id=cafe.id, nomor_meja=3, kapasitas=2)
        db.add_all([m5, m3])
        db.commit()

        resp = client.get(f"/cafes/{cafe.id}/meja")
        numbers = [item["nomor_meja"] for item in resp.json()]
        assert numbers == sorted(numbers)
