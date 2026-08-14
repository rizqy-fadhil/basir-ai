from __future__ import annotations

import unittest
from pathlib import Path

from inference.capture import MockFrameCapture
from inference.detect import (
    DetectionConfigurationError,
    PersonDetector,
    PersonDetectorConfig,
)


class _FakeBoxes:
    def __init__(self, boxes, confidence, class_ids) -> None:
        self.xyxy = boxes
        self.conf = confidence
        self.cls = class_ids


class _FakeResult:
    def __init__(self, boxes) -> None:
        self.boxes = boxes


class _FakeModel:
    def __init__(self, results) -> None:
        self.results = results
        self.calls: list[dict] = []

    def predict(self, **kwargs):
        self.calls.append(kwargs)
        return self.results


class PersonDetectorConfigTests(unittest.TestCase):
    def test_defaults_match_architecture(self) -> None:
        config = PersonDetectorConfig.from_env({})

        self.assertEqual(config.model_path, "yolov8n.pt")
        self.assertEqual(config.class_id, 0)
        self.assertEqual(config.confidence_threshold, 0.40)
        self.assertEqual(config.iou_threshold, 0.45)
        self.assertEqual(config.image_size, 640)

    def test_invalid_threshold_is_rejected(self) -> None:
        with self.assertRaises(DetectionConfigurationError):
            PersonDetectorConfig.from_env({"YOLO_PERSON_CONFIDENCE_THRESHOLD": "1.1"})


class PersonDetectorTests(unittest.TestCase):
    def test_filters_class_and_confidence(self) -> None:
        model = _FakeModel(
            [
                _FakeResult(
                    _FakeBoxes(
                        [[1, 2, 10, 12], [2, 3, 9, 11], [4, 5, 8, 10]],
                        [0.95, 0.99, 0.20],
                        [0, 56, 0],
                    )
                )
            ]
        )
        detector = PersonDetector(PersonDetectorConfig(), model=model)

        detections = detector.predict(b"frame")

        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0].bbox, (1.0, 2.0, 10.0, 12.0))
        self.assertEqual(detections[0].confidence, 0.95)
        self.assertEqual(model.calls[0]["conf"], 0.40)
        self.assertEqual(model.calls[0]["iou"], 0.45)

    def test_empty_result_is_safe(self) -> None:
        detector = PersonDetector(
            PersonDetectorConfig(), model=_FakeModel([_FakeResult(None)])
        )

        self.assertEqual(detector.predict(b"frame"), ())

    def test_empty_frame_does_not_call_model(self) -> None:
        model = _FakeModel([])
        detector = PersonDetector(PersonDetectorConfig(), model=model)

        self.assertEqual(detector.predict(b""), ())
        self.assertEqual(model.calls, [])

    def test_mock_frame_path_is_forwarded_to_model(self) -> None:
        fixture = (
            Path(__file__).resolve().parents[2] / "dataset" / "mock" / "workspace.ppm"
        )
        capture = MockFrameCapture(fixture)
        model = _FakeModel([])
        detector = PersonDetector(PersonDetectorConfig(), model=model)

        detector.predict(capture.read())

        self.assertEqual(model.calls[0]["source"], str(fixture))


if __name__ == "__main__":
    unittest.main()
