from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from inference.capture import (
    CaptureConfigurationError,
    CaptureConfig,
    FrameCaptureError,
    MockFrameCapture,
    open_capture,
)


class CaptureConfigTests(unittest.TestCase):
    def test_mock_config_requires_frame_path(self) -> None:
        with self.assertRaises(CaptureConfigurationError):
            CaptureConfig.from_env({"MOCK_MODE": "true"})

    def test_rtsp_config_requires_url_when_mock_disabled(self) -> None:
        with self.assertRaises(CaptureConfigurationError):
            CaptureConfig.from_env({"MOCK_MODE": "false"})

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


if __name__ == "__main__":
    unittest.main()
