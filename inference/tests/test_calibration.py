from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from inference.calibration import (
    CalibrationConfig,
    CalibrationDetection,
    CalibrationDetector,
    save_calibration_suggestion,
    suggest_calibration,
)


class CalibrationTests(unittest.TestCase):
    def test_defaults_match_environment_contract(self) -> None:
        config = CalibrationConfig.from_env({})

        self.assertEqual(config.model_path, "inference/models/table-chair-best.pt")
        self.assertEqual(config.confidence_threshold, 0.35)
        self.assertEqual(config.iou_threshold, 0.45)
        self.assertEqual(config.image_size, 640)

    def test_suggestion_counts_nearby_chairs_and_requires_confirmation(self) -> None:
        detections = [
            CalibrationDetection((10, 10, 30, 30), 0.9, 0),
            CalibrationDetection((70, 10, 90, 30), 0.8, 0),
            CalibrationDetection((2, 15, 8, 25), 0.8, 1),
            CalibrationDetection((32, 15, 38, 25), 0.8, 1),
            CalibrationDetection((62, 15, 68, 25), 0.8, 1),
            CalibrationDetection((92, 15, 98, 25), 0.8, 1),
        ]

        suggestion = suggest_calibration(
            detections,
            cafe_id=1,
            area_kamera="workspace-1",
            reference_frame="reference.ppm",
            frame_width=100,
            frame_height=100,
        )

        self.assertFalse(suggestion.confirmed)
        self.assertEqual([roi.kapasitas for roi in suggestion.rois], [2, 2])
        self.assertTrue(all(roi.valid for roi in suggestion.rois))
        self.assertTrue(suggestion.as_dict()["requires_manual_confirmation"])

    def test_zero_chair_suggestion_is_invalid_not_fabricated(self) -> None:
        suggestion = suggest_calibration(
            [CalibrationDetection((10, 10, 30, 30), 0.9, 0)],
            cafe_id=1,
            area_kamera="workspace-1",
            reference_frame="reference.ppm",
        )

        self.assertEqual(suggestion.rois[0].kapasitas, 0)
        self.assertFalse(suggestion.rois[0].valid)

    def test_save_keeps_confirmation_false(self) -> None:
        suggestion = suggest_calibration(
            [CalibrationDetection((0, 0, 10, 10), 0.9, 0)],
            cafe_id=1,
            area_kamera="workspace-1",
            reference_frame="reference.ppm",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calibration_suggestion.json"
            save_calibration_suggestion(path, suggestion)
            document = json.loads(path.read_text(encoding="utf-8"))

        self.assertFalse(document["confirmed"])
        self.assertTrue(document["requires_manual_confirmation"])

    def test_empty_frame_returns_no_calibration_detections(self) -> None:
        class EmptyModel:
            def predict(self, **kwargs):
                raise AssertionError("model tidak boleh dipanggil untuk frame kosong")

        detector = CalibrationDetector(CalibrationConfig(), model=EmptyModel())

        self.assertEqual(detector.predict(b""), ())

    def test_detector_filters_table_chair_classes(self) -> None:
        class Boxes:
            xyxy = [[0, 0, 10, 10], [1, 1, 9, 9], [2, 2, 8, 8]]
            conf = [0.9, 0.8, 0.9]
            cls = [0, 1, 2]

        class Result:
            boxes = Boxes()

        class Model:
            def predict(self, **kwargs):
                return [Result()]

        detector = CalibrationDetector(CalibrationConfig(), model=Model())

        detections = detector.predict(b"frame")

        self.assertEqual([d.class_id for d in detections], [0, 1])


if __name__ == "__main__":
    unittest.main()
