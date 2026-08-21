"""Opt-in private snapshot storage for local demos and S3-compatible stores.

Camera snapshots can contain identifiable people, so storage is disabled by
default. The runtime may opt in explicitly through environment variables; the
module never uploads or writes a frame when the feature is disabled.
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


class StorageConfigurationError(ValueError):
    """Raised when snapshot storage configuration is unsafe or incomplete."""


class SnapshotStorageError(RuntimeError):
    """Raised when an enabled snapshot cannot be persisted."""


@dataclass(frozen=True)
class SnapshotStorageConfig:
    """Validated opt-in storage settings."""

    enabled: bool = False
    backend: str = "local"
    snapshot_dir: Path = Path("snapshots")
    s3_endpoint_url: str | None = None
    s3_bucket_name: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_region_name: str | None = None
    max_width: int = 480
    max_height: int = 270
    jpeg_quality: int = 65

    @classmethod
    def from_env(
        cls, environ: Mapping[str, str] | None = None
    ) -> "SnapshotStorageConfig":
        values = os.environ if environ is None else environ
        enabled = _parse_bool(
            values.get("SNAPSHOT_STORAGE_ENABLED", "false"),
            "SNAPSHOT_STORAGE_ENABLED",
        )
        backend = str(values.get("SNAPSHOT_STORAGE_BACKEND", "local")).strip().lower()
        if backend not in {"local", "s3"}:
            raise StorageConfigurationError(
                "SNAPSHOT_STORAGE_BACKEND harus berupa local atau s3."
            )
        snapshot_dir = Path(
            str(values.get("SNAPSHOT_DIR", "snapshots")).strip() or "snapshots"
        )
        endpoint = _optional_value(values.get("S3_ENDPOINT_URL"))
        bucket = _optional_value(values.get("S3_BUCKET_NAME"))
        access_key = _optional_value(values.get("S3_ACCESS_KEY"))
        secret_key = _optional_value(values.get("S3_SECRET_KEY"))
        region = _optional_value(values.get("AWS_REGION"))
        max_width = _parse_positive_int(
            values.get("SNAPSHOT_MAX_WIDTH", "480"), "SNAPSHOT_MAX_WIDTH"
        )
        max_height = _parse_positive_int(
            values.get("SNAPSHOT_MAX_HEIGHT", "270"), "SNAPSHOT_MAX_HEIGHT"
        )
        jpeg_quality = _parse_int_in_range(
            values.get("SNAPSHOT_JPEG_QUALITY", "65"),
            "SNAPSHOT_JPEG_QUALITY",
            minimum=1,
            maximum=100,
        )

        if enabled and backend == "s3" and bucket is None:
            raise StorageConfigurationError(
                "S3_BUCKET_NAME wajib diisi saat snapshot storage memakai s3."
            )
        if (access_key is None) != (secret_key is None):
            raise StorageConfigurationError(
                "S3_ACCESS_KEY dan S3_SECRET_KEY harus diisi berpasangan."
            )
        return cls(
            enabled=enabled,
            backend=backend,
            snapshot_dir=snapshot_dir,
            s3_endpoint_url=endpoint,
            s3_bucket_name=bucket,
            s3_access_key=access_key,
            s3_secret_key=secret_key,
            s3_region_name=region,
            max_width=max_width,
            max_height=max_height,
            jpeg_quality=jpeg_quality,
        )


@dataclass(frozen=True)
class SnapshotReference:
    """Private location returned after a snapshot is persisted."""

    uri: str
    backend: str
    object_key: str
    content_type: str
    captured_at: datetime


class SnapshotStore:
    """Persist snapshots only when explicitly enabled by configuration."""

    def __init__(
        self,
        config: SnapshotStorageConfig,
        *,
        s3_client: Any | None = None,
    ) -> None:
        self.config = config
        self._s3_client_override = s3_client

    def save(
        self,
        frame: Any,
        *,
        cafe_id: int,
        captured_at: datetime,
        area: str = "workspace",
    ) -> SnapshotReference | None:
        """Save one frame and return a private reference, or ``None`` if off."""

        if not self.config.enabled:
            return None
        if cafe_id <= 0:
            raise SnapshotStorageError("cafe_id snapshot harus lebih besar dari nol.")
        normalized_time = _as_utc(captured_at)
        payload = getattr(frame, "payload", frame)
        source = str(getattr(frame, "source", ""))
        content, content_type, suffix = _encode_payload(
            payload,
            source,
            max_width=self.config.max_width,
            max_height=self.config.max_height,
            jpeg_quality=self.config.jpeg_quality,
        )
        key = _snapshot_key(cafe_id, area, normalized_time, suffix)
        if self.config.backend == "local":
            return self._save_local(content, content_type, key, normalized_time)
        return self._save_s3(content, content_type, key, normalized_time)

    def _save_local(
        self,
        content: bytes,
        content_type: str,
        key: str,
        captured_at: datetime,
    ) -> SnapshotReference:
        root = self.config.snapshot_dir.expanduser().resolve()
        target = root / Path(key)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=target.parent, prefix=".snapshot-", delete=False
            ) as temporary:
                temporary.write(content)
                temporary_path = Path(temporary.name)
            temporary_path.replace(target)
        except OSError as exc:
            raise SnapshotStorageError(
                f"Gagal menyimpan snapshot lokal di {target}: {exc}"
            ) from exc
        return SnapshotReference(
            uri=target.as_uri(),
            backend="local",
            object_key=key,
            content_type=content_type,
            captured_at=captured_at,
        )

    def _save_s3(
        self,
        content: bytes,
        content_type: str,
        key: str,
        captured_at: datetime,
    ) -> SnapshotReference:
        bucket = self.config.s3_bucket_name
        if bucket is None:  # defensive guard for manually constructed configs
            raise SnapshotStorageError("S3_BUCKET_NAME belum dikonfigurasi.")
        try:
            self._get_s3_client().put_object(
                Bucket=bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
                Metadata={
                    "captured-at": _iso_timestamp(captured_at),
                    "privacy": "camera-snapshot-private",
                },
            )
        except Exception as exc:
            raise SnapshotStorageError(
                f"Gagal menyimpan snapshot ke bucket S3 {bucket!r}: {exc}"
            ) from exc
        return SnapshotReference(
            uri=f"s3://{bucket}/{key}",
            backend="s3",
            object_key=key,
            content_type=content_type,
            captured_at=captured_at,
        )

    def _get_s3_client(self) -> Any:
        if self._s3_client_override is not None:
            return self._s3_client_override
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise SnapshotStorageError(
                "boto3 belum terpasang; install inference/requirements.txt."
            ) from exc
        kwargs: dict[str, Any] = {}
        if self.config.s3_endpoint_url:
            kwargs["endpoint_url"] = self.config.s3_endpoint_url
        if self.config.s3_access_key and self.config.s3_secret_key:
            kwargs["aws_access_key_id"] = self.config.s3_access_key
            kwargs["aws_secret_access_key"] = self.config.s3_secret_key
        if self.config.s3_region_name:
            kwargs["region_name"] = self.config.s3_region_name
        return boto3.client("s3", **kwargs)


def build_snapshot_store(
    environ: Mapping[str, str] | None = None,
) -> SnapshotStore | None:
    """Build the optional store; return ``None`` when privacy default is off."""

    config = SnapshotStorageConfig.from_env(environ)
    return SnapshotStore(config) if config.enabled else None


def _encode_payload(
    payload: Any,
    source: str,
    *,
    max_width: int,
    max_height: int,
    jpeg_quality: int,
) -> tuple[bytes, str, str]:
    if isinstance(payload, (bytes, bytearray, memoryview)):
        content = bytes(payload)
        if not content:
            raise SnapshotStorageError("Payload snapshot kosong.")
        content_type, suffix = _content_type_from_source(source)
        if content_type.startswith("image/"):
            try:
                import cv2
                import numpy as np
            except ImportError as exc:  # pragma: no cover - environment dependent
                raise SnapshotStorageError(
                    "OpenCV dan NumPy diperlukan untuk transformasi privasi snapshot."
                ) from exc
            image = cv2.imdecode(
                np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR
            )
            if image is None:
                raise SnapshotStorageError(
                    f"Payload image snapshot tidak dapat didekode: {source}"
                )
            return _encode_image(
                image,
                max_width=max_width,
                max_height=max_height,
                jpeg_quality=jpeg_quality,
                cv2_module=cv2,
            )
        return content, content_type, suffix

    try:
        import cv2
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise SnapshotStorageError(
            "Payload frame bukan bytes dan OpenCV belum terpasang."
        ) from exc
    return _encode_image(
        payload,
        max_width=max_width,
        max_height=max_height,
        jpeg_quality=jpeg_quality,
        cv2_module=cv2,
    )


def _encode_image(
    image: Any,
    *,
    max_width: int,
    max_height: int,
    jpeg_quality: int,
    cv2_module: Any | None = None,
) -> tuple[bytes, str, str]:
    cv2 = cv2_module
    if cv2 is None:
        try:
            import cv2
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise SnapshotStorageError(
                "OpenCV diperlukan untuk transformasi privasi snapshot."
            ) from exc
    try:
        height, width = image.shape[:2]
        scale = min(max_width / width, max_height / height, 1.0)
        if scale < 1.0:
            image = cv2.resize(
                image,
                (max(1, round(width * scale)), max(1, round(height * scale))),
                interpolation=cv2.INTER_AREA,
            )
        encoded_ok, encoded = cv2.imencode(
            ".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
        )
    except Exception as exc:
        raise SnapshotStorageError(f"Gagal encode frame snapshot: {exc}") from exc
    if not encoded_ok:
        raise SnapshotStorageError("OpenCV gagal encode frame snapshot ke JPEG.")
    return encoded.tobytes(), "image/jpeg", ".jpg"


def _content_type_from_source(source: str) -> tuple[str, str]:
    suffix = Path(source.split("#", 1)[0]).suffix.lower()
    mapping = {
        ".jpg": ("image/jpeg", ".jpg"),
        ".jpeg": ("image/jpeg", ".jpg"),
        ".png": ("image/png", ".png"),
        ".ppm": ("image/x-portable-pixmap", ".ppm"),
        ".webp": ("image/webp", ".webp"),
    }
    return mapping.get(suffix, ("application/octet-stream", ".bin"))


def _snapshot_key(cafe_id: int, area: str, captured_at: datetime, suffix: str) -> str:
    safe_area = _safe_component(area, "area")
    timestamp = captured_at.strftime("%Y%m%dT%H%M%S.%fZ")
    return f"cafe-{cafe_id}/{safe_area}/{timestamp}{suffix}"


def _safe_component(value: str, name: str) -> str:
    normalized = str(value).strip()
    if not normalized or not re.fullmatch(r"[A-Za-z0-9_.-]{1,120}", normalized):
        raise SnapshotStorageError(
            f"Komponen path {name} tidak aman untuk penyimpanan snapshot."
        )
    return normalized


def _optional_value(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _parse_bool(value: object, name: str) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise StorageConfigurationError(
        f"{name} harus berupa boolean (true/false), bukan {value!r}."
    )


def _parse_positive_int(value: object, name: str) -> int:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as exc:
        raise StorageConfigurationError(f"{name} harus berupa integer.") from exc
    if parsed <= 0:
        raise StorageConfigurationError(f"{name} harus lebih besar dari nol.")
    return parsed


def _parse_int_in_range(value: object, name: str, *, minimum: int, maximum: int) -> int:
    parsed = _parse_positive_int(value, name)
    if not minimum <= parsed <= maximum:
        raise StorageConfigurationError(
            f"{name} harus berada di antara {minimum} dan {maximum}."
        )
    return parsed


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso_timestamp(value: datetime) -> str:
    return _as_utc(value).isoformat().replace("+00:00", "Z")
