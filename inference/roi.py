"""ROI configuration validation and Shapely-based point mapping."""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Any, Iterable


class ROIConfigError(ValueError):
    """Raised when ROI configuration is malformed or geometrically invalid."""


Point = tuple[float, float]


@dataclass(frozen=True)
class TableROI:
    nomor_meja: int
    kapasitas: int
    polygon: tuple[Point, ...]


@dataclass(frozen=True)
class ROIConfig:
    cafe_id: int
    area_kamera: str
    frame_width: int | None
    frame_height: int | None
    rois: tuple[TableROI, ...]


def load_roi_config(config_path: Path | str) -> ROIConfig:
    """Load and validate the JSON ROI document without requiring Shapely."""

    path = Path(config_path)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ROIConfigError(f"File ROI tidak ditemukan: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ROIConfigError(f"JSON ROI tidak valid: {path}") from exc

    if not isinstance(document, dict):
        raise ROIConfigError("Dokumen ROI harus berupa object JSON.")
    cafe_id = _positive_int(document.get("cafe_id"), "cafe_id")
    area_kamera = _non_empty_string(document.get("area_kamera"), "area_kamera")
    frame_width = _optional_positive_int(document.get("frame_width"), "frame_width")
    frame_height = _optional_positive_int(document.get("frame_height"), "frame_height")
    raw_rois = document.get("rois")
    if not isinstance(raw_rois, list) or not raw_rois:
        raise ROIConfigError("rois harus berupa array yang berisi minimal satu meja.")

    tables: list[TableROI] = []
    seen_numbers: set[int] = set()
    for index, raw_roi in enumerate(raw_rois):
        if not isinstance(raw_roi, dict):
            raise ROIConfigError(f"rois[{index}] harus berupa object JSON.")
        nomor_meja = _positive_int(
            raw_roi.get("nomor_meja"), f"rois[{index}].nomor_meja"
        )
        if nomor_meja in seen_numbers:
            raise ROIConfigError(f"nomor_meja duplikat: {nomor_meja}.")
        seen_numbers.add(nomor_meja)
        kapasitas = _positive_int(raw_roi.get("kapasitas"), f"rois[{index}].kapasitas")
        polygon = _parse_polygon(raw_roi.get("polygon"), f"rois[{index}].polygon")
        _validate_bounds(polygon, frame_width, frame_height, index)
        tables.append(
            TableROI(
                nomor_meja=nomor_meja,
                kapasitas=kapasitas,
                polygon=polygon,
            )
        )

    return ROIConfig(
        cafe_id=cafe_id,
        area_kamera=area_kamera,
        frame_width=frame_width,
        frame_height=frame_height,
        rois=tuple(tables),
    )


def build_shapely_geometries(config: ROIConfig) -> dict[int, Any]:
    """Build valid Shapely polygons and reject overlapping table areas."""

    try:
        from shapely.geometry import Polygon
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise ROIConfigError(
            "Shapely wajib terpasang untuk membangun geometri ROI."
        ) from exc

    geometries: dict[int, Any] = {}
    for table in config.rois:
        polygon = Polygon(table.polygon)
        if polygon.is_empty or polygon.area <= 0 or not polygon.is_valid:
            raise ROIConfigError(f"Polygon meja {table.nomor_meja} tidak valid.")
        for other_number, other_polygon in geometries.items():
            if polygon.intersection(other_polygon).area > 0:
                raise ROIConfigError(
                    f"ROI meja {table.nomor_meja} overlap dengan meja {other_number}."
                )
        geometries[table.nomor_meja] = polygon
    return geometries


def map_point_to_table(point: Point, geometries: dict[int, Any]) -> int | None:
    """Map a detection point to one ROI using Shapely ``covers``."""

    try:
        from shapely.geometry import Point as ShapelyPoint
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise ROIConfigError(
            "Shapely wajib terpasang untuk memetakan titik ke ROI."
        ) from exc

    if len(point) != 2 or not all(isfinite(value) for value in point):
        raise ROIConfigError(f"Titik deteksi tidak valid: {point!r}.")
    detection_point = ShapelyPoint(point)
    matches = [
        table_number
        for table_number, polygon in geometries.items()
        if polygon.covers(detection_point)
    ]
    if len(matches) > 1:
        raise ROIConfigError(f"Titik {point!r} masuk ke beberapa ROI: {matches}.")
    return matches[0] if matches else None


def _parse_polygon(value: Any, field_name: str) -> tuple[Point, ...]:
    if not isinstance(value, list) or len(value) < 3:
        raise ROIConfigError(f"{field_name} harus memiliki minimal tiga titik.")
    points: list[Point] = []
    for point_index, raw_point in enumerate(value):
        if (
            not isinstance(raw_point, list)
            or len(raw_point) != 2
            or not all(isinstance(item, (int, float)) for item in raw_point)
        ):
            raise ROIConfigError(f"{field_name}[{point_index}] harus berupa [x, y].")
        point = (float(raw_point[0]), float(raw_point[1]))
        if not all(isfinite(item) for item in point):
            raise ROIConfigError(
                f"{field_name}[{point_index}] berisi angka non-finite."
            )
        points.append(point)
    if len(set(points)) < 3:
        raise ROIConfigError(f"{field_name} harus memiliki tiga titik unik.")
    return tuple(points)


def _validate_bounds(
    polygon: Iterable[Point],
    frame_width: int | None,
    frame_height: int | None,
    index: int,
) -> None:
    if frame_width is not None and any(x < 0 or x > frame_width for x, _ in polygon):
        raise ROIConfigError(f"rois[{index}] berada di luar frame_width.")
    if frame_height is not None and any(y < 0 or y > frame_height for _, y in polygon):
        raise ROIConfigError(f"rois[{index}] berada di luar frame_height.")


def _positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ROIConfigError(f"{field_name} harus berupa integer positif.")
    return value


def _optional_positive_int(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    return _positive_int(value, field_name)


def _non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ROIConfigError(f"{field_name} harus berupa string non-empty.")
    return value.strip()
