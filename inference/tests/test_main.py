from __future__ import annotations

import logging
import unittest
from datetime import datetime, timezone
from pathlib import Path

from inference.capture import CapturedFrame
from inference.detect import PersonDetection
from inference.main import (
    BackendClient,
    InferenceConfigurationError,
    InferenceRunner,
    RuntimeConfig,
)
from inference.roi import load_roi_config


ROOT = Path(__file__).resolve().parents[2]
ROI_PATH = ROOT / "inference" / "config" / "roi_config.json"


class _FakeCapture:
    def __init__(self, frame=None, error: Exception | None = None) -> None:
        self.frame = frame
        self.error = error

    def read(self):
        if self.error:
            raise self.error
        return self.frame


class _FakeDetector:
    def __init__(self, detections) -> None:
        self.detections = detections

    def predict(self, frame):
        return self.detections


class _FakeBackend:
    def __init__(self, table_ids, failed_ids=None, error_ids=None) -> None:
        self.table_ids = table_ids
        self.failed_ids = set(failed_ids or ())
        self.error_ids = set(error_ids or ())
        self.updates: list[dict] = []

    def list_tables(self, cafe_id):
        return self.table_ids

    def upsert_status(self, **payload):
        self.updates.append(payload)
        if payload["meja_id"] in self.error_ids:
            raise RuntimeError("simulated backend failure")
        return payload["meja_id"] not in self.failed_ids


class _FakeResponse:
    def __init__(self, status_code: int, body) -> None:
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class _FakeHTTPClient:
    def __init__(self, responses) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict]] = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class RuntimeConfigTests(unittest.TestCase):
    def test_missing_api_key_is_rejected(self) -> None:
        with self.assertRaises(InferenceConfigurationError):
            RuntimeConfig.from_env({})

    def test_env_values_are_parsed(self) -> None:
        config = RuntimeConfig.from_env(
            {
                "CAFE_ID": "4",
                "ROI_CONFIG_PATH": "roi.json",
                "BACKEND_API_URL": "http://backend:8000/",
                "BACKEND_API_KEY": "secret",
                "BACKEND_REQUEST_TIMEOUT_SECONDS": "5",
                "BACKEND_RETRY_COUNT": "2",
            }
        )

        self.assertEqual(config.cafe_id, 4)
        self.assertEqual(config.backend_base_url, "http://backend:8000")
        self.assertEqual(config.backend_retry_count, 2)


class BackendClientTests(unittest.TestCase):
    def test_list_tables_and_post_follow_contract(self) -> None:
        http = _FakeHTTPClient(
            [
                _FakeResponse(200, [{"id": 101, "nomor_meja": 1}]),
                _FakeResponse(200, {"action": "inserted", "meja_id": 101}),
            ]
        )
        client = BackendClient("http://localhost:8000", "secret", client=http)

        self.assertEqual(client.list_tables(1), {1: 101})
        self.assertTrue(
            client.upsert_status(
                meja_id=101,
                terisi=1,
                status="partial",
                updated_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
            )
        )
        self.assertEqual(http.calls[1][2]["json"]["updated_at"], "2026-08-14T00:00:00Z")

    def test_connection_error_retries_then_succeeds(self) -> None:
        http = _FakeHTTPClient([ConnectionError("offline"), _FakeResponse(200, [])])
        client = BackendClient(
            "http://localhost:8000", "secret", client=http, retry_count=1
        )

        self.assertEqual(client.list_tables(1), {})
        self.assertEqual(len(http.calls), 2)

    def test_individual_http_failure_returns_false(self) -> None:
        http = _FakeHTTPClient([_FakeResponse(422, {"detail": "invalid"})])
        client = BackendClient(
            "http://localhost:8000",
            "secret",
            client=http,
            logger=logging.getLogger("test-backend"),
        )

        self.assertFalse(
            client.upsert_status(
                meja_id=101,
                terisi=1,
                status="partial",
                updated_at=datetime.now(timezone.utc),
            )
        )


class InferenceRunnerTests(unittest.TestCase):
    def test_single_cycle_updates_every_mapped_table(self) -> None:
        captured_at = datetime(2026, 8, 14, tzinfo=timezone.utc)
        frame = CapturedFrame(b"mock", "mock.ppm", captured_at)
        backend = _FakeBackend({1: 101, 2: 102, 3: 103, 4: 104})
        runner = InferenceRunner(
            cafe_id=1,
            roi_config=load_roi_config(ROI_PATH),
            capture=_FakeCapture(frame),
            detector=_FakeDetector([PersonDetection((2, 0, 4, 5), 0.9)]),
            backend=backend,
        )

        result = runner.run_once()

        self.assertEqual(result.successful_updates, 4)
        self.assertEqual(result.failed_updates, 0)
        self.assertEqual(len(backend.updates), 4)
        self.assertEqual(backend.updates[0]["status"], "partial")

    def test_failed_table_does_not_stop_other_tables(self) -> None:
        frame = CapturedFrame(b"mock", "mock.ppm", datetime.now(timezone.utc))
        backend = _FakeBackend({1: 101, 2: 102, 3: 103, 4: 104}, failed_ids={102})
        runner = InferenceRunner(
            cafe_id=1,
            roi_config=load_roi_config(ROI_PATH),
            capture=_FakeCapture(frame),
            detector=_FakeDetector([]),
            backend=backend,
        )

        result = runner.run_once()

        self.assertEqual(result.successful_updates, 3)
        self.assertEqual(result.failed_updates, 1)
        self.assertEqual(len(backend.updates), 4)

    def test_unexpected_table_error_does_not_stop_other_tables(self) -> None:
        frame = CapturedFrame(b"mock", "mock.ppm", datetime.now(timezone.utc))
        backend = _FakeBackend({1: 101, 2: 102, 3: 103, 4: 104}, error_ids={102})
        runner = InferenceRunner(
            cafe_id=1,
            roi_config=load_roi_config(ROI_PATH),
            capture=_FakeCapture(frame),
            detector=_FakeDetector([]),
            backend=backend,
        )

        result = runner.run_once()

        self.assertEqual(result.successful_updates, 3)
        self.assertEqual(result.failed_updates, 1)
        self.assertEqual(len(backend.updates), 4)

    def test_capture_failure_skips_cycle_without_crashing(self) -> None:
        backend = _FakeBackend({1: 101})
        runner = InferenceRunner(
            cafe_id=1,
            roi_config=load_roi_config(ROI_PATH),
            capture=_FakeCapture(error=OSError("camera unavailable")),
            detector=_FakeDetector([]),
            backend=backend,
        )

        result = runner.run_once()

        self.assertEqual(result.skipped_reason, "capture_error")
        self.assertEqual(backend.updates, [])


if __name__ == "__main__":
    unittest.main()
