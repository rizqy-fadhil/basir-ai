"""Runtime person detection backed by the pretrained COCO YOLO model.

Only the COCO ``person`` class is exposed to the occupancy pipeline.  The
Ultralytics import and model construction are intentionally lazy so ROI and
unit tests can run without downloading model weights.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class DetectionConfigurationError(ValueError):
    """Raised when person detector configuration is invalid."""


class ModelLoadError(RuntimeError):
    """Raised when the runtime model cannot be imported or loaded."""


class DetectionInferenceError(RuntimeError):
    """Raised when the model fails while processing a frame."""


@dataclass(frozen=True)
class PersonDetectorConfig:
    """Validated settings for the pretrained COCO person detector."""

    model_path: str = "yolov8n.pt"
    class_id: int = 0
    confidence_threshold: float = 0.40
    iou_threshold: float = 0.45
    image_size: int = 640

    @classmethod
    def from_env(
        cls, environ: Mapping[str, str] | None = None
    ) -> "PersonDetectorConfig":
        values = os.environ if environ is None else environ
        model_path = str(values.get("YOLO_PERSON_MODEL_PATH", "yolov8n.pt")).strip()
        if not model_path:
            raise DetectionConfigurationError("YOLO_PERSON_MODEL_PATH wajib diisi.")
        class_id = _parse_non_negative_int(
            values.get("YOLO_PERSON_CLASS_ID", "0"), "YOLO_PERSON_CLASS_ID"
        )
        confidence_threshold = _parse_probability(
            values.get("YOLO_PERSON_CONFIDENCE_THRESHOLD", "0.40"),
            "YOLO_PERSON_CONFIDENCE_THRESHOLD",
        )
        iou_threshold = _parse_probability(
            values.get("YOLO_IOU_THRESHOLD", "0.45"), "YOLO_IOU_THRESHOLD"
        )
        image_size = _parse_positive_int(
            values.get("YOLO_IMAGE_SIZE", "640"), "YOLO_IMAGE_SIZE"
        )
        return cls(
            model_path=model_path,
            class_id=class_id,
            confidence_threshold=confidence_threshold,
            iou_threshold=iou_threshold,
            image_size=image_size,
        )


@dataclass(frozen=True)
class PersonDetection:
    """A filtered person bounding box in absolute ``xyxy`` frame coordinates."""

    bbox: tuple[float, float, float, float]
    confidence: float
    class_id: int = 0


class PersonDetector:
    """Load and run a YOLO model while returning only person detections."""

    def __init__(self, config: PersonDetectorConfig, model: Any | None = None) -> None:
        self.config = config
        self._model = (
            model if model is not None else self._load_model(config.model_path)
        )

    @staticmethod
    def _load_model(model_path: str) -> Any:
        try:
            from ultralytics import YOLO
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise ModelLoadError(
                "Ultralytics belum terpasang. Install inference/requirements.txt "
                "untuk menjalankan person detector."
            ) from exc
        try:
            return YOLO(model_path)
        except Exception as exc:  # pragma: no cover - depends on model/runtime
            raise ModelLoadError(
                f"Gagal memuat model person {model_path!r}: {exc}"
            ) from exc

    def predict(self, frame: Any) -> tuple[PersonDetection, ...]:
        """Run inference on one frame and return zero or more people.

        ``CapturedFrame`` instances from ``capture.py`` are converted to their
        source path when that path exists, which lets the mock PPM fixture be
        passed directly to a real Ultralytics model. Other frame objects are
        forwarded unchanged.
        """

        source = _model_source(frame)
        try:
            results = self._model.predict(
                source=source,
                conf=self.config.confidence_threshold,
                iou=self.config.iou_threshold,
                imgsz=self.config.image_size,
                verbose=False,
            )
        except Exception as exc:
            raise DetectionInferenceError(
                f"Inferensi person detector gagal: {exc}"
            ) from exc
        return _parse_person_results(results, self.config)

    __call__ = predict


def load_person_detector(environ: Mapping[str, str] | None = None) -> PersonDetector:
    """Create the runtime detector from the documented environment variables."""

    return PersonDetector(PersonDetectorConfig.from_env(environ))


def _model_source(frame: Any) -> Any:
    source = getattr(frame, "source", None)
    if source:
        path = Path(str(source))
        if path.is_file():
            return str(path)
    return getattr(frame, "payload", frame)


def _parse_person_results(
    results: Any, config: PersonDetectorConfig
) -> tuple[PersonDetection, ...]:
    if results is None:
        return ()
    if not isinstance(results, (list, tuple)):
        results = (results,)
    detections: list[PersonDetection] = []
    for result in results:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue
        xyxy = _to_list(getattr(boxes, "xyxy", None))
        confidence = _to_list(getattr(boxes, "conf", None))
        class_ids = _to_list(getattr(boxes, "cls", None))
        if xyxy is None or confidence is None or class_ids is None:
            continue
        for raw_bbox, raw_confidence, raw_class_id in zip(xyxy, confidence, class_ids):
            bbox = _parse_bbox(raw_bbox)
            if bbox is None:
                continue
            try:
                score = float(raw_confidence)
                class_id = int(float(raw_class_id))
            except (TypeError, ValueError):
                continue
            if class_id != config.class_id or score < config.confidence_threshold:
                continue
            detections.append(
                PersonDetection(bbox=bbox, confidence=score, class_id=class_id)
            )
    return tuple(detections)


def _to_list(value: Any) -> Any:
    if value is None:
        return None
    detached = value.detach() if hasattr(value, "detach") else value
    cpu_value = detached.cpu() if hasattr(detached, "cpu") else detached
    return cpu_value.tolist() if hasattr(cpu_value, "tolist") else cpu_value


def _parse_bbox(value: Any) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    try:
        coordinates = tuple(float(item) for item in value)
    except (TypeError, ValueError):
        return None
    if len(coordinates) != 4 or not all(math.isfinite(item) for item in coordinates):
        return None
    x_min, y_min, x_max, y_max = coordinates
    if x_max < x_min or y_max < y_min:
        return None
    return coordinates  # type: ignore[return-value]


def _parse_non_negative_int(value: object, name: str) -> int:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as exc:
        raise DetectionConfigurationError(f"{name} harus berupa integer.") from exc
    if parsed < 0:
        raise DetectionConfigurationError(f"{name} tidak boleh negatif.")
    return parsed


def _parse_positive_int(value: object, name: str) -> int:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as exc:
        raise DetectionConfigurationError(
            f"{name} harus berupa integer positif."
        ) from exc
    if parsed <= 0:
        raise DetectionConfigurationError(f"{name} harus lebih besar dari nol.")
    return parsed


def _parse_probability(value: object, name: str) -> float:
    try:
        parsed = float(str(value))
    except (TypeError, ValueError) as exc:
        raise DetectionConfigurationError(f"{name} harus berupa angka.") from exc
    if not math.isfinite(parsed) or not 0 <= parsed <= 1:
        raise DetectionConfigurationError(f"{name} harus berada di antara 0 dan 1.")
    return parsed
