"""Frame capture configuration and deterministic local mock capture.

The mock capture deliberately returns the original frame bytes. Decoding and
computer-vision processing belong to the later detection stage, so this
module can be tested without OpenCV or camera hardware installed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


class CaptureConfigurationError(ValueError):
    """Raised when capture-related environment variables are invalid."""


class FrameCaptureError(RuntimeError):
    """Raised when a frame cannot be read from the configured source."""


@dataclass(frozen=True)
class CapturedFrame:
    """A raw frame payload and the metadata needed by downstream stages."""

    payload: bytes
    source: str
    captured_at: datetime


@dataclass(frozen=True)
class CaptureConfig:
    """Validated capture settings loaded from environment variables."""

    mock_mode: bool
    mock_frame_path: Path | None
    rtsp_url: str | None
    interval_seconds: int

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "CaptureConfig":
        values = os.environ if environ is None else environ
        mock_mode = _parse_bool(values.get("MOCK_MODE", "true"), "MOCK_MODE")
        interval_seconds = _parse_positive_int(
            values.get("DETECTION_INTERVAL_SECONDS", "45"),
            "DETECTION_INTERVAL_SECONDS",
        )
        frame_value = values.get("MOCK_FRAME_PATH", "").strip()
        mock_frame_path = Path(frame_value) if frame_value else None
        rtsp_value = values.get("RTSP_URL", "").strip()
        rtsp_url = rtsp_value or None

        if mock_mode and mock_frame_path is None:
            raise CaptureConfigurationError(
                "MOCK_FRAME_PATH wajib diisi ketika MOCK_MODE aktif."
            )
        if not mock_mode and rtsp_url is None:
            raise CaptureConfigurationError(
                "RTSP_URL wajib diisi ketika MOCK_MODE tidak aktif."
            )

        return cls(
            mock_mode=mock_mode,
            mock_frame_path=mock_frame_path,
            rtsp_url=rtsp_url,
            interval_seconds=interval_seconds,
        )


class MockFrameCapture:
    """Read a deterministic frame fixture from the local filesystem."""

    def __init__(self, frame_path: Path | str) -> None:
        self._frame_path = Path(frame_path)
        self._closed = False
        if not self._frame_path.is_file():
            raise FrameCaptureError(f"Mock frame tidak ditemukan: {self._frame_path}")

    @property
    def frame_path(self) -> Path:
        return self._frame_path

    def read(self) -> CapturedFrame:
        """Read one frame and return its bytes with a UTC timestamp."""

        if self._closed:
            raise FrameCaptureError("Capture sudah ditutup.")
        try:
            payload = self._frame_path.read_bytes()
        except OSError as exc:
            raise FrameCaptureError(
                f"Gagal membaca mock frame {self._frame_path}: {exc}"
            ) from exc
        if not payload:
            raise FrameCaptureError(f"Mock frame kosong: {self._frame_path}")
        return CapturedFrame(
            payload=payload,
            source=str(self._frame_path),
            captured_at=datetime.now(timezone.utc),
        )

    def close(self) -> None:
        self._closed = True


def open_capture(config: CaptureConfig) -> MockFrameCapture:
    """Open the configured source available in the current foundation stage."""

    if config.mock_mode:
        # The validation above guarantees this is not None.
        assert config.mock_frame_path is not None
        return MockFrameCapture(config.mock_frame_path)
    raise NotImplementedError(
        "RTSP capture akan diaktifkan pada tahap ingest kamera berikutnya."
    )


def _parse_bool(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise CaptureConfigurationError(
        f"{name} harus berupa boolean (true/false), bukan {value!r}."
    )


def _parse_positive_int(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise CaptureConfigurationError(
            f"{name} harus berupa bilangan bulat positif."
        ) from exc
    if parsed <= 0:
        raise CaptureConfigurationError(f"{name} harus lebih besar dari nol.")
    return parsed
