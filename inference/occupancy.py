"""Map person detections to confirmed table ROIs and derive occupancy status."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Iterable, Sequence

from inference.roi import ROIConfig, build_shapely_geometries, map_point_to_table


AVAILABLE = "available"
PARTIAL = "partial"
OCCUPIED = "occupied"
VALID_STATUSES = frozenset({AVAILABLE, PARTIAL, OCCUPIED})


class OccupancyInputError(ValueError):
    """Raised when a detection box cannot be mapped safely."""


@dataclass(frozen=True)
class TableOccupancy:
    """Current occupancy for one configured table."""

    nomor_meja: int
    kapasitas: int
    terisi: int
    status: str

    def as_dict(self) -> dict[str, int | str]:
        return {
            "nomor_meja": self.nomor_meja,
            "kapasitas": self.kapasitas,
            "terisi": self.terisi,
            "status": self.status,
        }


@dataclass(frozen=True)
class OccupancySnapshot:
    """Occupancy result for one camera area."""

    cafe_id: int
    area_kamera: str
    meja: tuple[TableOccupancy, ...]

    def as_dict(self) -> dict[str, int | str | list[dict[str, int | str]]]:
        return {
            "cafe_id": self.cafe_id,
            "area_kamera": self.area_kamera,
            "meja": [table.as_dict() for table in self.meja],
        }


def bottom_center(bbox: Sequence[float]) -> tuple[float, float]:
    """Return the bottom-center anchor of an absolute ``xyxy`` box."""

    if len(bbox) != 4:
        raise OccupancyInputError(f"Bounding box harus berisi empat angka: {bbox!r}")
    try:
        x_min, y_min, x_max, y_max = (float(value) for value in bbox)
    except (TypeError, ValueError) as exc:
        raise OccupancyInputError(f"Bounding box tidak numerik: {bbox!r}") from exc
    if not all(isfinite(value) for value in (x_min, y_min, x_max, y_max)):
        raise OccupancyInputError(f"Bounding box berisi angka non-finite: {bbox!r}")
    if x_max < x_min or y_max < y_min:
        raise OccupancyInputError(f"Bounding box memiliki batas terbalik: {bbox!r}")
    return ((x_min + x_max) / 2, y_max)


def occupancy_status(terisi: int, kapasitas: int) -> str:
    """Apply the MVP status rules to a count and table capacity."""

    if kapasitas <= 0:
        raise OccupancyInputError("Kapasitas meja harus lebih besar dari nol.")
    if terisi < 0:
        raise OccupancyInputError("Jumlah orang tidak boleh negatif.")
    if terisi == 0:
        return AVAILABLE
    if terisi < kapasitas:
        return PARTIAL
    return OCCUPIED


def count_people_by_table(
    config: ROIConfig,
    detections: Iterable[Any],
    *,
    geometries: dict[int, Any] | None = None,
) -> dict[int, int]:
    """Count filtered person detections whose bottom-center falls in each ROI."""

    table_geometries = (
        build_shapely_geometries(config) if geometries is None else geometries
    )
    counts = {table.nomor_meja: 0 for table in config.rois}
    for detection in detections:
        class_id = getattr(detection, "class_id", 0)
        if class_id != 0:
            continue
        bbox = getattr(detection, "bbox", detection)
        table_number = map_point_to_table(bottom_center(bbox), table_geometries)
        if table_number is not None:
            counts[table_number] += 1
    return counts


def calculate_occupancy(
    config: ROIConfig,
    detections: Iterable[Any],
    *,
    geometries: dict[int, Any] | None = None,
) -> OccupancySnapshot:
    """Return stable per-table status from one frame's person detections."""

    counts = count_people_by_table(config, detections, geometries=geometries)
    tables = tuple(
        TableOccupancy(
            nomor_meja=table.nomor_meja,
            kapasitas=table.kapasitas,
            terisi=counts[table.nomor_meja],
            status=occupancy_status(counts[table.nomor_meja], table.kapasitas),
        )
        for table in config.rois
    )
    return OccupancySnapshot(
        cafe_id=config.cafe_id,
        area_kamera=config.area_kamera,
        meja=tables,
    )
