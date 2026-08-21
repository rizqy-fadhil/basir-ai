from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from inference.capture import CapturedFrame
from inference.storage import (
    SnapshotStorageConfig,
    SnapshotStorageError,
    SnapshotStore,
    StorageConfigurationError,
    build_snapshot_store,
)


class _FakeS3Client:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def put_object(self, **kwargs):
        self.calls.append(kwargs)


class SnapshotStorageTests(unittest.TestCase):
    def test_storage_is_disabled_by_default_and_does_not_touch_frame(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = build_snapshot_store(
                {"SNAPSHOT_DIR": str(Path(directory) / "snapshots")}
            )

            self.assertIsNone(store)
            self.assertFalse((Path(directory) / "snapshots").exists())

    def test_local_storage_writes_private_file_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "snapshots"
            config = SnapshotStorageConfig(
                enabled=True, backend="local", snapshot_dir=root
            )
            captured_at = datetime(2026, 8, 21, 12, 30, tzinfo=timezone.utc)
            frame = CapturedFrame(
                b"P3\n1 1\n255\n255 0 0\n", "/tmp/frame.ppm", captured_at
            )

            reference = SnapshotStore(config).save(
                frame, cafe_id=7, captured_at=captured_at, area="workspace-1"
            )

            assert reference is not None
            self.assertEqual(reference.backend, "local")
            self.assertEqual(reference.content_type, "image/jpeg")
            saved_path = Path(reference.uri.removeprefix("file://"))
            self.assertTrue(saved_path.is_file())
            self.assertTrue(saved_path.read_bytes().startswith(b"\xff\xd8"))
            self.assertEqual(list(root.rglob(".snapshot-*")), [])

    def test_s3_storage_uses_private_put_without_public_acl(self) -> None:
        client = _FakeS3Client()
        config = SnapshotStorageConfig(
            enabled=True, backend="s3", s3_bucket_name="private-bucket"
        )
        captured_at = datetime(2026, 8, 21, tzinfo=timezone.utc)

        reference = SnapshotStore(config, s3_client=client).save(
            CapturedFrame(b"P3\n1 1\n255\n0 255 0\n", "frame.ppm", captured_at),
            cafe_id=1,
            captured_at=captured_at,
        )

        assert reference is not None
        self.assertEqual(reference.uri, f"s3://private-bucket/{reference.object_key}")
        self.assertEqual(len(client.calls), 1)
        self.assertTrue(client.calls[0]["Body"].startswith(b"\xff\xd8"))
        self.assertNotIn("ACL", client.calls[0])
        self.assertEqual(
            client.calls[0]["Metadata"]["privacy"], "camera-snapshot-private"
        )

    def test_video_frame_is_downscaled_before_local_storage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = SnapshotStorageConfig(
                enabled=True,
                backend="local",
                snapshot_dir=Path(directory),
                max_width=480,
                max_height=270,
            )
            image = np.zeros((540, 960, 3), dtype=np.uint8)
            captured_at = datetime.now(timezone.utc)
            reference = SnapshotStore(config).save(
                CapturedFrame(image, "video.avi#frame=0", captured_at),
                cafe_id=1,
                captured_at=captured_at,
            )

            assert reference is not None
            encoded = cv2.imdecode(
                np.fromfile(
                    Path(reference.uri.removeprefix("file://")), dtype=np.uint8
                ),
                cv2.IMREAD_COLOR,
            )
            self.assertIsNotNone(encoded)
            self.assertEqual(encoded.shape[:2], (270, 480))

    def test_unsafe_area_and_empty_payload_are_rejected(self) -> None:
        config = SnapshotStorageConfig(enabled=True, backend="local")
        captured_at = datetime.now(timezone.utc)
        store = SnapshotStore(config)

        with self.assertRaises(SnapshotStorageError):
            store.save(
                CapturedFrame(b"frame", "frame.bin", captured_at),
                cafe_id=1,
                captured_at=captured_at,
                area="../public",
            )
        with self.assertRaises(SnapshotStorageError):
            store.save(
                CapturedFrame(b"", "frame.jpg", captured_at),
                cafe_id=1,
                captured_at=captured_at,
            )

    def test_s3_configuration_requires_bucket_and_matching_credentials(self) -> None:
        with self.assertRaises(StorageConfigurationError):
            SnapshotStorageConfig.from_env(
                {"SNAPSHOT_STORAGE_ENABLED": "true", "SNAPSHOT_STORAGE_BACKEND": "s3"}
            )
        with self.assertRaises(StorageConfigurationError):
            SnapshotStorageConfig.from_env(
                {
                    "SNAPSHOT_STORAGE_ENABLED": "true",
                    "SNAPSHOT_STORAGE_BACKEND": "s3",
                    "S3_BUCKET_NAME": "bucket",
                    "S3_ACCESS_KEY": "access",
                }
            )


if __name__ == "__main__":
    unittest.main()
