from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from dataset.download_candidate_previews import (
    PreviewDownloadError,
    download_previews,
)


class _FakeHeaders:
    def __init__(self, content_length: str | None = None) -> None:
        self.content_length = content_length

    def get(self, name: str) -> str | None:
        return self.content_length if name == "Content-Length" else None


class _FakeResponse:
    def __init__(self, payload: bytes, content_length: str | None = None) -> None:
        self.payload = payload
        self.offset = 0
        self.headers = _FakeHeaders(content_length)

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args) -> None:
        return None

    def read(self, size: int) -> bytes:
        chunk = self.payload[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


def _write_candidates(path: Path, rows: list[dict[str, str]]) -> None:
    fields = [
        "image_id",
        "split",
        "original_url",
        "curation_status",
        "license_verified",
        "scene_verified",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class PreviewDownloadTests(unittest.TestCase):
    def test_download_writes_preview_and_preserves_review_flags(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "candidates.csv"
            _write_candidates(
                input_path,
                [
                    {
                        "image_id": "image-1",
                        "split": "validation",
                        "original_url": "https://example.test/image-1.jpg",
                        "curation_status": "pending",
                        "license_verified": "false",
                        "scene_verified": "false",
                    }
                ],
            )

            def opener(request, timeout):
                self.assertEqual(request.full_url, "https://example.test/image-1.jpg")
                self.assertEqual(timeout, 5)
                return _FakeResponse(b"fake-jpeg")

            result = download_previews(
                input_path,
                root / "preview",
                timeout_seconds=5,
                retry_count=0,
                urlopen=opener,
            )

            self.assertEqual(result["counts"]["downloaded"], 1)
            self.assertFalse(result["curation_flags_changed"])
            preview = root / "preview" / "validation" / "image-1.jpg"
            self.assertEqual(preview.read_bytes(), b"fake-jpeg")
            manifest = root / "preview" / "preview_manifest.csv"
            row = next(csv.DictReader(manifest.open(encoding="utf-8", newline="")))
            self.assertEqual(row["curation_status"], "pending")
            self.assertEqual(row["license_verified"], "false")
            self.assertEqual(row["scene_verified"], "false")

    def test_failed_download_is_bounded_and_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "candidates.csv"
            _write_candidates(
                input_path,
                [
                    {
                        "image_id": "image-1",
                        "split": "validation",
                        "original_url": "https://example.test/image-1.jpg",
                        "curation_status": "pending",
                        "license_verified": "false",
                        "scene_verified": "false",
                    }
                ],
            )
            attempts = 0

            def opener(request, timeout):
                nonlocal attempts
                attempts += 1
                raise OSError("connection refused")

            result = download_previews(
                input_path,
                root / "preview",
                retry_count=2,
                urlopen=opener,
            )

            self.assertEqual(attempts, 3)
            self.assertEqual(result["counts"]["failed"], 1)
            self.assertTrue("preview_manifest.csv" in str(result["manifest"]))

    def test_missing_url_is_reported_without_network_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "candidates.csv"
            _write_candidates(
                input_path,
                [
                    {
                        "image_id": "image-1",
                        "split": "validation",
                        "original_url": "",
                        "curation_status": "pending",
                        "license_verified": "false",
                        "scene_verified": "false",
                    }
                ],
            )
            result = download_previews(input_path, root / "preview")

            self.assertEqual(result["counts"]["missing_url"], 1)

    def test_invalid_candidate_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "candidates.csv"
            _write_candidates(
                input_path,
                [
                    {
                        "image_id": "../escape",
                        "split": "validation",
                        "original_url": "https://example.test/image.jpg",
                        "curation_status": "pending",
                        "license_verified": "false",
                        "scene_verified": "false",
                    }
                ],
            )

            with self.assertRaises(PreviewDownloadError):
                download_previews(input_path, root / "preview")

    def test_size_limit_rejects_large_response(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "candidates.csv"
            _write_candidates(
                input_path,
                [
                    {
                        "image_id": "image-1",
                        "split": "validation",
                        "original_url": "https://example.test/image-1.jpg",
                        "curation_status": "pending",
                        "license_verified": "false",
                        "scene_verified": "false",
                    }
                ],
            )

            def opener(request, timeout):
                return _FakeResponse(b"too-large", content_length="100")

            result = download_previews(
                input_path,
                root / "preview",
                retry_count=0,
                max_bytes=10,
                urlopen=opener,
            )

            self.assertEqual(result["counts"]["failed"], 1)


if __name__ == "__main__":
    unittest.main()
