"""Table/chair calibration suggestions that require human confirmation."""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


LOGGER = logging.getLogger(__name__)
# Must match dataset/prepare_roboflow_table_chair.py output.
TABLE_CLASS_ID = 0
CHAIR_CLASS_ID = 1


class CalibrationConfigurationError(ValueError):
    """Raised when calibration model configuration is invalid."""


class CalibrationModelError(RuntimeError):
    """Raised when the calibration model cannot be loaded."""


@dataclass(frozen=True)
class CalibrationConfig:
    """Settings for the fine-tuned Table/Chair detector."""

    model_path: str = "inference/models/table-chair-best.pt"
    confidence_threshold: float = 0.35
    iou_threshold: float = 0.45
    image_size: int = 640
    chair_distance_factor: float = 1.5

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "CalibrationConfig":
        values = os.environ if environ is None else environ
        model_path = str(
            values.get(
                "YOLO_CALIBRATION_MODEL_PATH", "inference/models/table-chair-best.pt"
            )
        ).strip()
        if not model_path:
            raise CalibrationConfigurationError(
                "YOLO_CALIBRATION_MODEL_PATH wajib diisi."
            )
        confidence_threshold = _parse_probability(
            values.get("YOLO_CALIBRATION_CONFIDENCE_THRESHOLD", "0.35"),
            "YOLO_CALIBRATION_CONFIDENCE_THRESHOLD",
        )
        iou_threshold = _parse_probability(
            values.get("YOLO_IOU_THRESHOLD", "0.45"), "YOLO_IOU_THRESHOLD"
        )
        image_size = _parse_positive_int(
            values.get("YOLO_IMAGE_SIZE", "640"), "YOLO_IMAGE_SIZE"
        )
        chair_distance_factor = _parse_positive_float(
            values.get("CALIBRATION_CHAIR_DISTANCE_FACTOR", "1.5"),
            "CALIBRATION_CHAIR_DISTANCE_FACTOR",
        )
        return cls(
            model_path=model_path,
            confidence_threshold=confidence_threshold,
            iou_threshold=iou_threshold,
            image_size=image_size,
            chair_distance_factor=chair_distance_factor,
        )


@dataclass(frozen=True)
class CalibrationDetection:
    """A table or chair detection in absolute frame coordinates."""

    bbox: tuple[float, float, float, float]
    confidence: float
    class_id: int


@dataclass(frozen=True)
class ROISuggestion:
    """One proposed table ROI; it is never treated as confirmed automatically."""

    nomor_meja: int
    polygon: tuple[tuple[float, float], ...]
    kapasitas: int
    table_confidence: float
    nearby_chair_count: int
    valid: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "nomor_meja": self.nomor_meja,
            "polygon": [[x, y] for x, y in self.polygon],
            "kapasitas": self.kapasitas,
            "table_confidence": self.table_confidence,
            "nearby_chair_count": self.nearby_chair_count,
            "valid": self.valid,
        }


@dataclass(frozen=True)
class CalibrationSuggestion:
    """Serializable calibration output with an explicit human-review gate."""

    cafe_id: int
    area_kamera: str
    reference_frame: str
    frame_width: int | None
    frame_height: int | None
    rois: tuple[ROISuggestion, ...]
    confirmed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "cafe_id": self.cafe_id,
            "area_kamera": self.area_kamera,
            "reference_frame": self.reference_frame,
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "confirmed": self.confirmed,
            "requires_manual_confirmation": not self.confirmed,
            "rois": [roi.as_dict() for roi in self.rois],
        }


class CalibrationDetector:
    """Lazy YOLO wrapper for the fine-tuned table/chair model."""

    def __init__(self, config: CalibrationConfig, model: Any | None = None) -> None:
        self.config = config
        self._model = (
            model if model is not None else self._load_model(config.model_path)
        )

    @staticmethod
    def _load_model(model_path: str) -> Any:
        try:
            from ultralytics import YOLO
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise CalibrationModelError(
                "Ultralytics belum terpasang; install inference/requirements.txt."
            ) from exc
        try:
            return YOLO(model_path)
        except Exception as exc:  # pragma: no cover - environment dependent
            raise CalibrationModelError(
                f"Gagal memuat calibration model {model_path!r}: {exc}"
            ) from exc

    def predict(self, frame: Any) -> tuple[CalibrationDetection, ...]:
        """Return only Table/Chair detections; empty/failed frames are safe."""

        payload = getattr(frame, "payload", frame)
        if payload is None or (isinstance(payload, (bytes, bytearray)) and not payload):
            LOGGER.warning("Reference frame kosong; tidak ada saran kalibrasi.")
            return ()
        source = _model_source(frame)
        if source is None or (isinstance(source, (bytes, bytearray)) and not source):
            LOGGER.warning("Reference frame kosong; tidak ada saran kalibrasi.")
            return ()
        try:
            results = self._model.predict(
                source=source,
                conf=self.config.confidence_threshold,
                iou=self.config.iou_threshold,
                imgsz=self.config.image_size,
                verbose=False,
            )
        except Exception as exc:  # pragma: no cover - model runtime dependent
            LOGGER.error("Calibration inference gagal; saran dikosongkan: %s", exc)
            return ()
        return _parse_results(results, self.config)


def suggest_calibration(
    detections: Sequence[CalibrationDetection],
    *,
    cafe_id: int,
    area_kamera: str,
    reference_frame: str,
    frame_width: int | None = None,
    frame_height: int | None = None,
    chair_distance_factor: float = 1.5,
) -> CalibrationSuggestion:
    """Suggest rectangular table ROIs and capacity from nearby chairs.

    Each chair is assigned to at most one table. A zero-chair suggestion is
    marked invalid and still requires manual correction instead of inventing a
    capacity. The output is never written to the runtime ROI config directly.
    """

    if chair_distance_factor <= 0 or not math.isfinite(chair_distance_factor):
        raise CalibrationConfigurationError("chair_distance_factor harus positif.")
    tables = sorted(
        (detection for detection in detections if detection.class_id == TABLE_CLASS_ID),
        key=lambda detection: (detection.bbox[1], detection.bbox[0]),
    )
    chairs = [
        detection for detection in detections if detection.class_id == CHAIR_CLASS_ID
    ]
    available_chair_indices = set(range(len(chairs)))
    suggestions: list[ROISuggestion] = []
    for number, table in enumerate(tables, start=1):
        bbox = _clip_bbox(table.bbox, frame_width, frame_height)
        if bbox is None:
            LOGGER.warning(
                "Table detection %s memiliki bbox tidak valid; dilewati.", number
            )
            continue
        x_min, y_min, x_max, y_max = bbox
        width = x_max - x_min
        height = y_max - y_min
        threshold = max(width, height) * chair_distance_factor
        nearby: list[int] = []
        for chair_index in sorted(available_chair_indices):
            distance = _point_to_rect_distance(_center(chairs[chair_index].bbox), bbox)
            if distance <= threshold:
                nearby.append(chair_index)
        for chair_index in nearby:
            available_chair_indices.remove(chair_index)
        capacity = len(nearby)
        suggestions.append(
            ROISuggestion(
                nomor_meja=number,
                polygon=(
                    (x_min, y_min),
                    (x_max, y_min),
                    (x_max, y_max),
                    (x_min, y_max),
                ),
                kapasitas=capacity,
                table_confidence=table.confidence,
                nearby_chair_count=capacity,
                valid=capacity > 0,
            )
        )
    return CalibrationSuggestion(
        cafe_id=cafe_id,
        area_kamera=area_kamera,
        reference_frame=reference_frame,
        frame_width=frame_width,
        frame_height=frame_height,
        rois=tuple(suggestions),
        confirmed=False,
    )


def save_calibration_suggestion(
    path: Path | str, suggestion: CalibrationSuggestion
) -> None:
    """Persist a reviewable suggestion without touching ``roi_config.json``."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(f"{destination.suffix}.tmp")
    temporary.write_text(
        json.dumps(suggestion.as_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, destination)


def _parse_results(
    results: Any, config: CalibrationConfig
) -> tuple[CalibrationDetection, ...]:
    if results is None:
        return ()
    if not isinstance(results, (list, tuple)):
        results = (results,)
    detections: list[CalibrationDetection] = []
    for result in results:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue
        xyxy = _to_list(getattr(boxes, "xyxy", None))
        confidences = _to_list(getattr(boxes, "conf", None))
        class_ids = _to_list(getattr(boxes, "cls", None))
        if xyxy is None or confidences is None or class_ids is None:
            continue
        for raw_bbox, raw_confidence, raw_class_id in zip(xyxy, confidences, class_ids):
            try:
                bbox = tuple(float(value) for value in raw_bbox)
                confidence = float(raw_confidence)
                class_id = int(float(raw_class_id))
            except (TypeError, ValueError):
                continue
            if (
                len(bbox) != 4
                or not all(math.isfinite(value) for value in bbox)
                or not math.isfinite(confidence)
                or confidence < config.confidence_threshold
                or class_id not in {TABLE_CLASS_ID, CHAIR_CLASS_ID}
                or bbox[2] < bbox[0]
                or bbox[3] < bbox[1]
            ):
                continue
            detections.append(
                CalibrationDetection(
                    bbox=bbox, confidence=confidence, class_id=class_id
                )
            )
    return tuple(detections)


def _to_list(value: Any) -> Any:
    if value is None:
        return None
    detached = value.detach() if hasattr(value, "detach") else value
    cpu_value = detached.cpu() if hasattr(detached, "cpu") else detached
    return cpu_value.tolist() if hasattr(cpu_value, "tolist") else cpu_value


def _model_source(frame: Any) -> Any:
    source = getattr(frame, "source", None)
    if source:
        path = Path(str(source))
        if path.is_file():
            return str(path)
    return getattr(frame, "payload", frame)


def _center(bbox: Sequence[float]) -> tuple[float, float]:
    return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)


def _point_to_rect_distance(
    point: tuple[float, float], bbox: tuple[float, float, float, float]
) -> float:
    x, y = point
    x_min, y_min, x_max, y_max = bbox
    dx = max(x_min - x, 0.0, x - x_max)
    dy = max(y_min - y, 0.0, y - y_max)
    return math.hypot(dx, dy)


def _clip_bbox(
    bbox: Sequence[float], frame_width: int | None, frame_height: int | None
) -> tuple[float, float, float, float] | None:
    if len(bbox) != 4:
        return None
    x_min, y_min, x_max, y_max = (float(value) for value in bbox)
    if frame_width is not None:
        x_min, x_max = max(0, x_min), min(frame_width, x_max)
    if frame_height is not None:
        y_min, y_max = max(0, y_min), min(frame_height, y_max)
    if x_max <= x_min or y_max <= y_min:
        return None
    return x_min, y_min, x_max, y_max


def _parse_probability(value: object, name: str) -> float:
    try:
        parsed = float(str(value))
    except (TypeError, ValueError) as exc:
        raise CalibrationConfigurationError(f"{name} harus berupa angka.") from exc
    if not math.isfinite(parsed) or not 0 <= parsed <= 1:
        raise CalibrationConfigurationError(f"{name} harus berada di antara 0 dan 1.")
    return parsed


def _parse_positive_int(value: object, name: str) -> int:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as exc:
        raise CalibrationConfigurationError(
            f"{name} harus berupa integer positif."
        ) from exc
    if parsed <= 0:
        raise CalibrationConfigurationError(f"{name} harus lebih besar dari nol.")
    return parsed


def _parse_positive_float(value: object, name: str) -> float:
    try:
        parsed = float(str(value))
    except (TypeError, ValueError) as exc:
        raise CalibrationConfigurationError(f"{name} harus berupa angka.") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise CalibrationConfigurationError(f"{name} harus lebih besar dari nol.")
    return parsed
