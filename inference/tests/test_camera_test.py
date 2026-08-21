from __future__ import annotations

import unittest

from inference.calibration import CalibrationDetection
from inference.camera_test import (
    CameraTestConfig,
    CameraTestError,
    CameraTestRunner,
    open_capture,
    parse_source,
)
from inference.detect import PersonDetection


class _Frame:
    def copy(self):
        return _Frame()


class _FakeCapture:
    def __init__(self, frames) -> None:
        self.frames = list(frames)
        self.released = False
        self.settings: list[tuple[int, int]] = []

    def isOpened(self):
        return True

    def set(self, property_id, value):
        self.settings.append((property_id, value))
        return True

    def read(self):
        if not self.frames:
            return False, None
        return True, self.frames.pop(0)

    def release(self):
        self.released = True


class _FakeCV2:
    CAP_PROP_FRAME_WIDTH = 3
    CAP_PROP_FRAME_HEIGHT = 4
    FONT_HERSHEY_SIMPLEX = 0
    LINE_AA = 16

    def __init__(self, capture=None) -> None:
        self.capture = capture
        self.opened_source = None
        self.operations: list[tuple] = []

    def VideoCapture(self, source):
        self.opened_source = source
        return self.capture

    def rectangle(self, *args):
        self.operations.append(("rectangle", args))

    def putText(self, *args):
        self.operations.append(("putText", args))

    def imwrite(self, *args):
        self.operations.append(("imwrite", args))
        return True

    def imshow(self, *args):
        self.operations.append(("imshow", args))

    def waitKey(self, *args):
        return -1

    def destroyAllWindows(self):
        self.operations.append(("destroyAllWindows",))


class _FakePersonDetector:
    def __init__(self, detections=()) -> None:
        self.detections = tuple(detections)
        self.frames = []

    def predict(self, frame):
        self.frames.append(frame)
        return self.detections


class _FakeCalibrationDetector:
    def __init__(self, detections=()) -> None:
        self.detections = tuple(detections)
        self.frames = []

    def predict(self, frame):
        self.frames.append(frame)
        return self.detections


class CameraTestConfigTests(unittest.TestCase):
    def test_source_defaults_to_builtin_webcam(self) -> None:
        config = CameraTestConfig.from_env({})

        self.assertEqual(config.source, "0")
        self.assertTrue(config.display)

    def test_webcam_environment_overrides_source(self) -> None:
        config = CameraTestConfig.from_env({"WEBCAM_INDEX": "2"})

        self.assertEqual(config.source, "2")

    def test_invalid_source_index_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_source("-1")

    def test_video_path_remains_a_path(self) -> None:
        self.assertEqual(parse_source("fixtures/cafe.mp4"), "fixtures/cafe.mp4")


class CameraTestRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.person_detector = _FakePersonDetector(
            [PersonDetection((1, 2, 10, 12), 0.91)]
        )
        self.calibration_detector = _FakeCalibrationDetector(
            [
                CalibrationDetection((10, 10, 20, 20), 0.81, 0),
                CalibrationDetection((22, 10, 30, 20), 0.77, 1),
            ]
        )
        self.capture = _FakeCapture([_Frame(), _Frame(), _Frame()])
        self.cv2 = _FakeCV2(self.capture)

    def test_headless_runner_processes_two_frames_and_counts_both_models(self) -> None:
        summaries = []
        runner = CameraTestRunner(
            self.capture,
            self.person_detector,
            self.calibration_detector,
            self.cv2,
            display=False,
            max_frames=2,
            on_summary=summaries.append,
        )

        self.assertEqual(runner.run(), 2)
        self.assertTrue(self.capture.released)
        self.assertEqual(len(self.person_detector.frames), 2)
        self.assertEqual(len(self.calibration_detector.frames), 2)
        self.assertEqual(
            summaries[0].as_dict(),
            {
                "frame_index": 1,
                "person_count": 1,
                "table_count": 1,
                "chair_count": 1,
            },
        )
        self.assertFalse(
            any(operation[0] == "imshow" for operation in self.cv2.operations)
        )

    def test_person_only_runner_does_not_require_calibration_detector(self) -> None:
        summaries = []
        runner = CameraTestRunner(
            self.capture,
            self.person_detector,
            None,
            self.cv2,
            display=False,
            max_frames=1,
            on_summary=summaries.append,
        )

        self.assertEqual(runner.run(), 1)
        self.assertEqual(summaries[0].table_count, 0)
        self.assertEqual(summaries[0].chair_count, 0)

    def test_display_runner_uses_gui_and_stops_on_q(self) -> None:
        class QuitCV2(_FakeCV2):
            def waitKey(self, *args):
                return ord("q")

        cv2 = QuitCV2(self.capture)
        runner = CameraTestRunner(
            self.capture,
            self.person_detector,
            self.calibration_detector,
            cv2,
            display=True,
            on_summary=lambda summary: None,
        )

        self.assertEqual(runner.run(), 1)
        self.assertTrue(any(operation[0] == "imshow" for operation in cv2.operations))
        self.assertTrue(
            any(operation[0] == "destroyAllWindows" for operation in cv2.operations)
        )

    def test_empty_source_raises_and_releases(self) -> None:
        capture = _FakeCapture([])
        runner = CameraTestRunner(
            capture,
            self.person_detector,
            self.calibration_detector,
            self.cv2,
            display=False,
        )

        with self.assertRaises(CameraTestError):
            runner.run()
        self.assertTrue(capture.released)


class OpenCaptureTests(unittest.TestCase):
    def test_opens_numeric_source_and_applies_dimensions(self) -> None:
        capture = _FakeCapture([])
        cv2 = _FakeCV2(capture)
        config = CameraTestConfig(source="0", width=1280, height=720)

        opened = open_capture(config, cv2)

        self.assertIs(opened, capture)
        self.assertEqual(cv2.opened_source, 0)
        self.assertEqual(capture.settings, [(3, 1280), (4, 720)])


if __name__ == "__main__":
    unittest.main()
