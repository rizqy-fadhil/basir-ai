"""Local visual smoke test for a webcam or video file.

This module is intentionally separate from the production occupancy loop. It
runs the pretrained person detector and the fine-tuned table/chair detector
side by side so an operator can inspect the models before using a camera
configuration. It never writes runtime ROI configuration or calls the backend.

The inference Docker image uses a headless OpenCV build, so live display is
best run from a host Python environment with ``opencv-python`` installed.
``--headless`` remains available for repeatable video-file smoke tests.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Mapping

from inference.calibration import (
    CalibrationConfig,
    CalibrationDetection,
    CalibrationDetector,
)
from inference.detect import PersonDetection, PersonDetector, PersonDetectorConfig


PERSON_COLOR = (0, 0, 255)
TABLE_COLOR = (255, 0, 0)
CHAIR_COLOR = (255, 255, 0)
WINDOW_NAME = "Basir AI - Camera Test"


class CameraTestConfigurationError(ValueError):
    """Raised when camera-test arguments are invalid."""


class CameraTestError(RuntimeError):
    """Raised when a camera-test source cannot be opened or read."""


@dataclass(frozen=True)
class CameraTestConfig:
    """Validated source and display settings for the local test runner."""

    source: str = "0"
    width: int | None = None
    height: int | None = None
    max_frames: int = 0
    display: bool = True
    save_dir: Path | None = None
    window_name: str = WINDOW_NAME

    def __post_init__(self) -> None:
        if not str(self.source).strip():
            raise CameraTestConfigurationError("Source webcam/video wajib diisi.")
        if self.width is not None and self.width <= 0:
            raise CameraTestConfigurationError("Lebar kamera harus lebih besar dari 0.")
        if self.height is not None and self.height <= 0:
            raise CameraTestConfigurationError(
                "Tinggi kamera harus lebih besar dari 0."
            )
        if self.max_frames < 0:
            raise CameraTestConfigurationError("max_frames tidak boleh negatif.")
        if not self.window_name.strip():
            raise CameraTestConfigurationError("Nama window tidak boleh kosong.")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "CameraTestConfig":
        values = os.environ if environ is None else environ
        source = str(
            values.get("CAMERA_TEST_SOURCE", values.get("WEBCAM_INDEX", "0"))
        ).strip()
        return cls(source=source)


@dataclass(frozen=True)
class CameraFrameSummary:
    """Counts emitted for one processed frame."""

    frame_index: int
    person_count: int
    table_count: int
    chair_count: int

    def as_dict(self) -> dict[str, int]:
        return {
            "frame_index": self.frame_index,
            "person_count": self.person_count,
            "table_count": self.table_count,
            "chair_count": self.chair_count,
        }

    @property
    def counts(self) -> tuple[int, int, int]:
        return self.person_count, self.table_count, self.chair_count


def parse_source(source: str) -> int | str:
    """Convert a numeric source such as ``"0"`` to a webcam index."""

    text = str(source).strip()
    if not text:
        raise CameraTestConfigurationError("Source webcam/video wajib diisi.")
    try:
        camera_index = int(text)
    except ValueError:
        return text
    if camera_index < 0:
        raise CameraTestConfigurationError("Index webcam tidak boleh negatif.")
    return camera_index


def open_capture(config: CameraTestConfig, cv2_module: Any) -> Any:
    """Open a webcam index or video path and apply optional camera dimensions."""

    source = parse_source(config.source)
    capture = cv2_module.VideoCapture(source)
    if capture is None or not capture.isOpened():
        raise CameraTestError(
            f"Tidak dapat membuka source kamera/video {config.source!r}. "
            "Pastikan kamera tidak sedang dipakai aplikasi lain dan path video benar."
        )
    if config.width is not None:
        capture.set(cv2_module.CAP_PROP_FRAME_WIDTH, config.width)
    if config.height is not None:
        capture.set(cv2_module.CAP_PROP_FRAME_HEIGHT, config.height)
    return capture


class CameraTestRunner:
    """Process frames with both detectors and optionally render annotations."""

    def __init__(
        self,
        capture: Any,
        person_detector: Any,
        calibration_detector: Any | None,
        cv2_module: Any,
        *,
        display: bool,
        max_frames: int = 0,
        save_dir: Path | None = None,
        window_name: str = WINDOW_NAME,
        on_summary: Callable[[CameraFrameSummary], None] | None = None,
    ) -> None:
        if max_frames < 0:
            raise CameraTestConfigurationError("max_frames tidak boleh negatif.")
        self.capture = capture
        self.person_detector = person_detector
        self.calibration_detector = calibration_detector
        self.cv2 = cv2_module
        self.display = display
        self.max_frames = max_frames
        self.save_dir = save_dir
        self.window_name = window_name
        self.on_summary = on_summary

    def process_frame(
        self, frame: Any, frame_index: int
    ) -> tuple[CameraFrameSummary, Any]:
        """Run both model roles on one frame and return an annotated copy."""

        person_detections = tuple(self.person_detector.predict(frame))
        calibration_detections: tuple[CalibrationDetection, ...] = ()
        if self.calibration_detector is not None:
            calibration_detections = tuple(self.calibration_detector.predict(frame))

        annotated = frame.copy() if hasattr(frame, "copy") else frame
        draw_annotations(
            annotated,
            person_detections,
            calibration_detections,
            self.cv2,
        )
        summary = CameraFrameSummary(
            frame_index=frame_index,
            person_count=len(person_detections),
            table_count=sum(
                detection.class_id == 0 for detection in calibration_detections
            ),
            chair_count=sum(
                detection.class_id == 1 for detection in calibration_detections
            ),
        )
        return summary, annotated

    def run(self) -> int:
        """Read, process, and optionally display frames until quit or EOF."""

        if self.save_dir is not None:
            self.save_dir.mkdir(parents=True, exist_ok=True)

        processed = 0
        try:
            while self.max_frames == 0 or processed < self.max_frames:
                ok, frame = self.capture.read()
                if not ok or frame is None:
                    if processed == 0:
                        raise CameraTestError(
                            "Source terbuka tetapi tidak menghasilkan frame pertama."
                        )
                    break

                processed += 1
                summary, annotated = self.process_frame(frame, processed)
                if self.on_summary is not None:
                    self.on_summary(summary)

                if self.save_dir is not None:
                    output_path = self.save_dir / f"frame-{processed:06d}.jpg"
                    saved = self.cv2.imwrite(str(output_path), annotated)
                    if saved is False:
                        raise CameraTestError(
                            f"Gagal menyimpan frame anotasi ke {output_path}."
                        )

                if self.display:
                    try:
                        self.cv2.imshow(self.window_name, annotated)
                        key = self.cv2.waitKey(1) & 0xFF
                    except Exception as exc:  # pragma: no cover - GUI dependent
                        raise CameraTestError(
                            "OpenCV GUI tidak tersedia. Install opencv-python "
                            "di environment lokal atau jalankan dengan --headless."
                        ) from exc
                    if key in (27, ord("q")):
                        break
        finally:
            self.capture.release()
            if self.display:
                try:
                    self.cv2.destroyAllWindows()
                except Exception:  # pragma: no cover - GUI dependent
                    pass
        return processed


def draw_annotations(
    frame: Any,
    person_detections: tuple[PersonDetection, ...],
    calibration_detections: tuple[CalibrationDetection, ...],
    cv2_module: Any,
) -> Any:
    """Draw color-coded boxes without changing the detector outputs."""

    for detection in person_detections:
        _draw_detection(
            frame,
            detection.bbox,
            f"person {detection.confidence:.2f}",
            PERSON_COLOR,
            cv2_module,
        )
    for detection in calibration_detections:
        if detection.class_id == 0:
            label, color = "table", TABLE_COLOR
        elif detection.class_id == 1:
            label, color = "chair", CHAIR_COLOR
        else:  # Defensive: CalibrationDetector already filters this.
            continue
        _draw_detection(
            frame,
            detection.bbox,
            f"{label} {detection.confidence:.2f}",
            color,
            cv2_module,
        )
    return frame


def _draw_detection(
    frame: Any,
    bbox: tuple[float, float, float, float],
    label: str,
    color: tuple[int, int, int],
    cv2_module: Any,
) -> None:
    x_min, y_min, x_max, y_max = (int(round(value)) for value in bbox)
    cv2_module.rectangle(frame, (x_min, y_min), (x_max, y_max), color, 2)
    text_origin = (x_min, max(0, y_min - 8))
    cv2_module.putText(
        frame,
        label,
        text_origin,
        cv2_module.FONT_HERSHEY_SIMPLEX,
        0.5,
        color,
        1,
        cv2_module.LINE_AA,
    )


def _load_cv2() -> Any:
    try:
        import cv2
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise CameraTestError(
            "OpenCV belum terpasang. Install inference/requirements.txt."
        ) from exc
    return cv2


def _build_parser(environ: Mapping[str, str] | None = None) -> argparse.ArgumentParser:
    values = os.environ if environ is None else environ
    parser = argparse.ArgumentParser(
        description=(
            "Uji lokal webcam/video dengan model person runtime dan "
            "table/chair calibration secara terpisah."
        )
    )
    parser.add_argument(
        "--source",
        default=values.get("CAMERA_TEST_SOURCE", values.get("WEBCAM_INDEX", "0")),
        help="Index webcam, misalnya 0, atau path file video.",
    )
    parser.add_argument(
        "--person-model",
        default=None,
        help="Override YOLO_PERSON_MODEL_PATH untuk pengujian lokal.",
    )
    parser.add_argument(
        "--calibration-model",
        default=None,
        help="Override YOLO_CALIBRATION_MODEL_PATH untuk pengujian lokal.",
    )
    parser.add_argument(
        "--person-only",
        action="store_true",
        help="Jalankan hanya person detector untuk cek kamera.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Tanpa window GUI; cocok untuk video smoke test atau Docker.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Jumlah frame maksimum; 0 berarti sampai q/ESC atau EOF.",
    )
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument(
        "--save-dir",
        type=Path,
        default=None,
        help="Opsional: simpan frame anotasi ke folder ini.",
    )
    parser.add_argument("--window-name", default=WINDOW_NAME)
    return parser


def run_cli(
    argv: list[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> int:
    """Run the local camera test and return a process exit code."""

    if environ is None:
        _load_project_env()
    values = os.environ if environ is None else environ
    args = _build_parser(values).parse_args(argv)
    try:
        config = CameraTestConfig(
            source=args.source,
            width=args.width,
            height=args.height,
            max_frames=args.max_frames,
            display=not args.headless,
            save_dir=args.save_dir,
            window_name=args.window_name,
        )
        person_config = PersonDetectorConfig.from_env(values)
        calibration_config = (
            None if args.person_only else CalibrationConfig.from_env(values)
        )
        if args.person_model:
            person_config = replace(person_config, model_path=args.person_model)
        if args.calibration_model and calibration_config is not None:
            calibration_config = replace(
                calibration_config, model_path=args.calibration_model
            )

        cv2_module = _load_cv2()
        person_detector = PersonDetector(person_config)
        calibration_detector = (
            None if args.person_only else CalibrationDetector(calibration_config)
        )
        capture = open_capture(config, cv2_module)
        last_counts: tuple[int, int, int] | None = None

        def emit_summary(summary: CameraFrameSummary) -> None:
            nonlocal last_counts
            if config.display and summary.counts == last_counts:
                return
            print(json.dumps(summary.as_dict(), ensure_ascii=False), flush=True)
            last_counts = summary.counts

        runner = CameraTestRunner(
            capture,
            person_detector,
            calibration_detector,
            cv2_module,
            display=config.display,
            max_frames=config.max_frames,
            save_dir=config.save_dir,
            window_name=config.window_name,
            on_summary=emit_summary,
        )
        processed = runner.run()
        if processed == 0:
            print("Tidak ada frame yang diproses.", file=sys.stderr)
            return 1
        return 0
    except (
        CameraTestConfigurationError,
        CameraTestError,
        RuntimeError,
        ValueError,
    ) as exc:
        print(f"camera-test gagal: {exc}", file=sys.stderr)
        return 2


def _load_project_env() -> None:
    """Load the repository ``.env`` when python-dotenv is available."""

    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dependency is pinned for runtime
        return
    root_env = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(root_env)


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":  # pragma: no cover - exercised through CLI
    main()
