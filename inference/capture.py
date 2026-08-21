"""Frame capture configuration and deterministic local capture sources.

Byte-backed mock frames remain available for fast tests. Video files and RTSP
sources are decoded with OpenCV so the detector receives the current frame,
not the same video path on every cycle.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


class CaptureConfigurationError(ValueError):
    """Raised when capture-related environment variables are invalid."""


class FrameCaptureError(RuntimeError):
    """Raised when a frame cannot be read from the configured source."""


@dataclass(frozen=True)
class CapturedFrame:
    """A raw frame payload and the metadata needed by downstream stages."""

    payload: Any
    source: str
    captured_at: datetime
    frame_index: int | None = None


@dataclass(frozen=True)
class CaptureConfig:
    """Validated capture settings loaded from environment variables."""

    mock_mode: bool
    mock_frame_path: Path | None
    mock_video_path: Path | None
    mock_video_loop: bool
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
        video_value = values.get("MOCK_VIDEO_PATH", "").strip()
        mock_video_path = Path(video_value) if video_value else None
        mock_video_loop = _parse_bool(
            values.get("MOCK_VIDEO_LOOP", "true"), "MOCK_VIDEO_LOOP"
        )
        rtsp_value = values.get("RTSP_URL", "").strip()
        rtsp_url = rtsp_value or None

        if mock_mode and mock_frame_path is None and mock_video_path is None:
            raise CaptureConfigurationError(
                "MOCK_FRAME_PATH atau MOCK_VIDEO_PATH wajib diisi ketika "
                "MOCK_MODE aktif."
            )
        if not mock_mode and rtsp_url is None:
            raise CaptureConfigurationError(
                "RTSP_URL wajib diisi ketika MOCK_MODE tidak aktif."
            )

        return cls(
            mock_mode=mock_mode,
            mock_frame_path=mock_frame_path,
            mock_video_path=mock_video_path,
            mock_video_loop=mock_video_loop,
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


class OpenCVVideoCapture:
    """Decode a video/RTSP source into one ``CapturedFrame`` per read."""

    def __init__(
        self,
        source: Path | str,
        *,
        loop: bool,
        require_file: bool,
    ) -> None:
        self._source = str(source)
        self._loop = loop
        self._require_file = require_file
        self._closed = False
        self._frame_index = 0
        if require_file and not Path(self._source).is_file():
            raise FrameCaptureError(f"Video mock tidak ditemukan: {self._source}")
        cv2 = _load_cv2()
        try:
            self._cv2 = cv2
            self._capture = cv2.VideoCapture(self._source)
            if not self._capture.isOpened():
                self._capture.release()
                raise FrameCaptureError(
                    f"Sumber video tidak dapat dibuka: {self._source}"
                )
        except FrameCaptureError:
            raise
        except Exception as exc:
            raise FrameCaptureError(
                f"Gagal membuka sumber video {self._source}: {exc}"
            ) from exc

    @property
    def source(self) -> str:
        return self._source

    def read(self) -> CapturedFrame:
        """Read the next decoded frame, optionally looping at end-of-file."""

        if self._closed:
            raise FrameCaptureError("Capture sudah ditutup.")
        try:
            ok, frame = self._capture.read()
            if not ok or frame is None:
                if not self._loop:
                    raise FrameCaptureError(f"Video sudah berakhir: {self._source}")
                if self._require_file:
                    self._capture.set(self._cv2.CAP_PROP_POS_FRAMES, 0)
                else:
                    self._capture.release()
                    self._capture = self._cv2.VideoCapture(self._source)
                    if not self._capture.isOpened():
                        raise FrameCaptureError(
                            f"RTSP source tidak dapat dibuka ulang: {self._source}"
                        )
                self._frame_index = 0
                ok, frame = self._capture.read()
            if not ok or frame is None:
                raise FrameCaptureError(
                    f"Video tidak menghasilkan frame: {self._source}"
                )
        except FrameCaptureError:
            raise
        except Exception as exc:
            raise FrameCaptureError(
                f"Gagal membaca video {self._source}: {exc}"
            ) from exc

        frame_index = self._frame_index
        self._frame_index += 1
        return CapturedFrame(
            payload=frame,
            source=f"{self._source}#frame={frame_index}",
            captured_at=datetime.now(timezone.utc),
            frame_index=frame_index,
        )

    def close(self) -> None:
        if not self._closed:
            self._capture.release()
            self._closed = True


class MockVideoCapture(OpenCVVideoCapture):
    """Local video-file capture used when ``MOCK_MODE`` is enabled."""

    def __init__(self, video_path: Path | str, *, loop: bool = True) -> None:
        super().__init__(video_path, loop=loop, require_file=True)

    @property
    def video_path(self) -> Path:
        return Path(self._source)


class RTSPCapture(OpenCVVideoCapture):
    """Open an RTSP source for production capture with reopen on read failure."""

    def __init__(self, rtsp_url: str) -> None:
        super().__init__(rtsp_url, loop=True, require_file=False)


def open_capture(config: CaptureConfig) -> Any:
    """Open the configured frame, video-file, or RTSP source."""

    if config.mock_mode:
        if config.mock_video_path is not None:
            return MockVideoCapture(config.mock_video_path, loop=config.mock_video_loop)
        # The validation above guarantees this is not None.
        assert config.mock_frame_path is not None
        return MockFrameCapture(config.mock_frame_path)
    # The validation above guarantees this is not None.
    assert config.rtsp_url is not None
    return RTSPCapture(config.rtsp_url)


def _load_cv2() -> Any:
    try:
        import cv2
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise FrameCaptureError(
            "OpenCV belum terpasang; install inference/requirements.txt."
        ) from exc
    return cv2


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
