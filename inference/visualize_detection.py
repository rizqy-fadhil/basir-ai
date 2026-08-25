"""Create one annotated image for a manual person/table/chair demo.

This is a standalone proof-of-work utility. It does not call the occupancy
engine, update ROI configuration, or send anything to the backend.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

# Support both ``python -m inference.visualize_detection`` and direct
# execution such as ``python inference/visualize_detection.py image.jpg``.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2  # noqa: E402

from inference.calibration import (  # noqa: E402
    CHAIR_CLASS_ID,
    TABLE_CLASS_ID,
    CalibrationConfig,
    CalibrationDetection,
    CalibrationDetector,
)
from inference.detect import (  # noqa: E402
    PersonDetection,
    PersonDetector,
    PersonDetectorConfig,
)


PERSON_COLOR = (0, 255, 0)  # BGR green
TABLE_COLOR = (0, 165, 255)  # BGR orange
CHAIR_COLOR = (255, 255, 0)  # BGR cyan


class VisualizationError(RuntimeError):
    """Raised when the demo image cannot be loaded or written."""


@dataclass(frozen=True)
class VisualizationSummary:
    """Detection counts and output path for one annotated image."""

    output_path: Path
    person_count: int
    table_count: int
    chair_count: int


def load_image(image_path: Path) -> Any:
    """Load one color image and fail clearly for missing/invalid input."""

    if not image_path.is_file():
        raise VisualizationError(f"File gambar tidak ditemukan: {image_path}")
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise VisualizationError(f"Gambar tidak dapat dibaca: {image_path}")
    return image


def visualize_image(
    image_path: Path | str,
    *,
    output_path: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
    person_model_path: str | None = None,
    calibration_model_path: str | None = None,
) -> VisualizationSummary:
    """Run both detectors, annotate one image, and save a new image."""

    _load_project_env(environ)
    source_path = Path(image_path)
    destination = (
        Path(output_path)
        if output_path is not None
        else _default_output_path(source_path)
    )
    if source_path.resolve() == destination.resolve():
        raise VisualizationError(
            "Output harus berupa file baru, bukan input yang sama."
        )

    person_config = PersonDetectorConfig.from_env(environ)
    calibration_config = CalibrationConfig.from_env(environ)
    if person_model_path:
        person_config = replace(person_config, model_path=person_model_path)
    if calibration_model_path:
        calibration_config = replace(
            calibration_config, model_path=calibration_model_path
        )
    person_config = replace(
        person_config, model_path=_resolve_model_path(person_config.model_path)
    )
    calibration_config = replace(
        calibration_config,
        model_path=_resolve_model_path(calibration_config.model_path),
    )

    image = load_image(source_path)
    person_detector = PersonDetector(person_config)
    calibration_detector = CalibrationDetector(calibration_config)
    person_detections = person_detector.predict(image)
    calibration_detections = calibration_detector.predict(image)

    annotated = image.copy()
    draw_detections(annotated, person_detections, calibration_detections)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(destination), annotated):
        raise VisualizationError(f"Gagal menyimpan gambar anotasi: {destination}")

    return VisualizationSummary(
        output_path=destination,
        person_count=len(person_detections),
        table_count=sum(
            detection.class_id == TABLE_CLASS_ID for detection in calibration_detections
        ),
        chair_count=sum(
            detection.class_id == CHAIR_CLASS_ID for detection in calibration_detections
        ),
    )


def draw_detections(
    image: Any,
    person_detections: Sequence[PersonDetection],
    calibration_detections: Sequence[CalibrationDetection],
) -> Any:
    """Draw color-coded boxes and confidence labels onto an image."""

    for detection in person_detections:
        _draw_detection(
            image,
            detection.bbox,
            f"person {detection.confidence:.2f}",
            PERSON_COLOR,
        )
    for detection in calibration_detections:
        if detection.class_id == TABLE_CLASS_ID:
            label, color = "table", TABLE_COLOR
        elif detection.class_id == CHAIR_CLASS_ID:
            label, color = "chair", CHAIR_COLOR
        else:
            continue
        _draw_detection(
            image,
            detection.bbox,
            f"{label} {detection.confidence:.2f}",
            color,
        )
    return image


def _draw_detection(
    image: Any,
    bbox: tuple[float, float, float, float],
    label: str,
    color: tuple[int, int, int],
) -> None:
    x_min, y_min, x_max, y_max = (int(round(value)) for value in bbox)
    cv2.rectangle(image, (x_min, y_min), (x_max, y_max), color, 2)
    text_origin = (x_min, max(20, y_min - 8))
    # Black outline keeps colored labels readable on both dark and bright data.
    cv2.putText(
        image,
        label,
        text_origin,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 0, 0),
        4,
        cv2.LINE_AA,
    )
    cv2.putText(
        image,
        label,
        text_origin,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        color,
        2,
        cv2.LINE_AA,
    )


def _default_output_path(image_path: Path) -> Path:
    suffix = image_path.suffix or ".jpg"
    return image_path.with_name(f"{image_path.stem}_annotated{suffix}")


def _resolve_model_path(model_path: str) -> str:
    """Resolve documented repository-relative paths from any working directory."""

    path = Path(model_path)
    if path.is_absolute() or path.is_file():
        return str(path)
    project_path = PROJECT_ROOT / path
    if project_path.is_file():
        return str(project_path)
    return model_path


def _load_project_env(environ: Mapping[str, str] | None) -> None:
    """Load the repository ``.env`` without overriding explicit environment values."""

    if environ is not None:
        return
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dependency is pinned for inference
        return
    load_dotenv(PROJECT_ROOT / ".env")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Buat gambar demo beranotasi dari person dan table/chair detector."
        )
    )
    parser.add_argument("image", type=Path, help="Path ke satu gambar input.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Path output; default: <nama-input>_annotated.<ext>",
    )
    parser.add_argument(
        "--person-model",
        default=None,
        help="Override YOLO_PERSON_MODEL_PATH.",
    )
    parser.add_argument(
        "--calibration-model",
        default=None,
        help="Override YOLO_CALIBRATION_MODEL_PATH.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = visualize_image(
            args.image,
            output_path=args.output,
            person_model_path=args.person_model,
            calibration_model_path=args.calibration_model,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"visualize_detection gagal: {exc}", file=sys.stderr)
        return 2

    print(f"annotated_image: {summary.output_path}")
    print(f"person: {summary.person_count}")
    print(f"table: {summary.table_count}")
    print(f"chair: {summary.chair_count}")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through CLI
    raise SystemExit(main())
