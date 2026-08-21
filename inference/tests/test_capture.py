from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from inference.capture import (
    CaptureConfigurationError,
    CaptureConfig,
    FrameCaptureError,
    MockFrameCapture,
    MockVideoCapture,
    open_capture,
)


class CaptureConfigTests(unittest.TestCase):
    def test_mock_config_requires_frame_path(self) -> None:
        with self.assertRaises(CaptureConfigurationError):
            CaptureConfig.from_env({"MOCK_MODE": "true"})

    def test_rtsp_config_requires_url_when_mock_disabled(self) -> None:
        with self.assertRaises(CaptureConfigurationError):
            CaptureConfig.from_env({"MOCK_MODE": "false"})

    def test_mock_config_accepts_video_path_without_frame_path(self) -> None:
        config = CaptureConfig.from_env(
            {
                "MOCK_MODE": "true",
                "MOCK_VIDEO_PATH": "demo.mp4",
                "MOCK_VIDEO_LOOP": "false",
            }
        )

        self.assertIsNone(config.mock_frame_path)
        self.assertEqual(config.mock_video_path, Path("demo.mp4"))
        self.assertFalse(config.mock_video_loop)

    def test_invalid_interval_is_rejected(self) -> None:
        with self.assertRaises(CaptureConfigurationError):
            CaptureConfig.from_env(
                {
                    "MOCK_MODE": "true",
                    "MOCK_FRAME_PATH": "fixture.ppm",
                    "DETECTION_INTERVAL_SECONDS": "0",
                }
            )


class MockFrameCaptureTests(unittest.TestCase):
    def test_repository_fixture_is_a_non_empty_ppm(self) -> None:
        fixture = (
            Path(__file__).resolve().parents[2] / "dataset" / "mock" / "workspace.ppm"
        )
        frame = MockFrameCapture(fixture).read()

        self.assertTrue(frame.payload.startswith(b"P3\n"))
        self.assertGreater(len(frame.payload), 100)

    def test_read_returns_fixture_bytes_and_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.ppm"
            path.write_bytes(b"P3\n1 1\n255\n0 0 0\n")
            capture = MockFrameCapture(path)

            frame = capture.read()

            self.assertEqual(frame.payload, path.read_bytes())
            self.assertEqual(frame.source, str(path))
            self.assertIsNotNone(frame.captured_at.tzinfo)
            capture.close()
            with self.assertRaises(FrameCaptureError):
                capture.read()

    def test_missing_fixture_is_rejected(self) -> None:
        with self.assertRaises(FrameCaptureError):
            MockFrameCapture(Path("does-not-exist.ppm"))

    def test_open_capture_uses_mock_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.ppm"
            path.write_bytes(b"mock")
            config = CaptureConfig.from_env(
                {"MOCK_MODE": "true", "MOCK_FRAME_PATH": str(path)}
            )
            capture = open_capture(config)
            self.assertEqual(capture.read().payload, b"mock")

    def test_video_capture_decodes_frames_and_loops(self) -> None:
        class _FakeVideoCapture:
            def __init__(self, frames) -> None:
                self.frames = frames
                self.index = 0
                self.released = False

            def isOpened(self):
                return True

            def read(self):
                if self.index >= len(self.frames):
                    return False, None
                frame = self.frames[self.index]
                self.index += 1
                return True, frame

            def set(self, _property, value):
                self.index = int(value)
                return True

            def release(self):
                self.released = True

        class _FakeCV2:
            CAP_PROP_POS_FRAMES = 1

            def __init__(self) -> None:
                self.capture = _FakeVideoCapture(["frame-0", "frame-1"])

            def VideoCapture(self, _source):
                return self.capture

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.mp4"
            path.write_bytes(b"video")
            fake_cv2 = _FakeCV2()
            with patch("inference.capture._load_cv2", return_value=fake_cv2):
                capture = MockVideoCapture(path, loop=True)
                first = capture.read()
                second = capture.read()
                third = capture.read()

            self.assertEqual(
                (first.payload, second.payload, third.payload),
                ("frame-0", "frame-1", "frame-0"),
            )
            self.assertEqual(
                (first.frame_index, second.frame_index, third.frame_index), (0, 1, 0)
            )
            self.assertIn("#frame=0", first.source)
            capture.close()
            self.assertTrue(fake_cv2.capture.released)

    def test_video_capture_without_loop_reports_end_of_file(self) -> None:
        class _FakeCapture:
            def isOpened(self):
                return True

            def read(self):
                return False, None

            def release(self):
                pass

        class _FakeCV2:
            def VideoCapture(self, _source):
                return _FakeCapture()

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.mp4"
            path.write_bytes(b"video")
            with patch("inference.capture._load_cv2", return_value=_FakeCV2()):
                capture = MockVideoCapture(path, loop=False)
                with self.assertRaises(FrameCaptureError):
                    capture.read()
                capture.close()


if __name__ == "__main__":
    unittest.main()
