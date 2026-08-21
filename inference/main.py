"""Runtime orchestrator: capture, person detection, occupancy, backend sync."""

from __future__ import annotations

import argparse
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from inference.capture import CaptureConfig, open_capture
from inference.detect import PersonDetector, load_person_detector
from inference.occupancy import calculate_occupancy
from inference.roi import ROIConfig, load_roi_config
from inference.storage import SnapshotStore, build_snapshot_store


LOGGER = logging.getLogger("basir_ai.inference")
VALID_ACTIONS = frozenset({"inserted", "updated"})


class InferenceConfigurationError(ValueError):
    """Raised when runtime orchestration configuration is invalid."""


class BackendClientError(RuntimeError):
    """Raised when the backend cannot serve a request or returns bad data."""


@dataclass(frozen=True)
class RuntimeConfig:
    """Environment-backed settings for one inference process."""

    cafe_id: int = 1
    roi_config_path: Path = Path("inference/config/roi_config.json")
    backend_base_url: str = "http://localhost:8000"
    backend_api_key: str = ""
    backend_timeout_seconds: float = 10.0
    backend_retry_count: int = 1

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "RuntimeConfig":
        values = os.environ if environ is None else environ
        cafe_id = _parse_positive_int(values.get("CAFE_ID", "1"), "CAFE_ID")
        roi_path = Path(
            str(values.get("ROI_CONFIG_PATH", "inference/config/roi_config.json"))
        )
        backend_base_url = (
            str(values.get("BACKEND_API_URL", "http://localhost:8000"))
            .strip()
            .rstrip("/")
        )
        if not backend_base_url.startswith(("http://", "https://")):
            raise InferenceConfigurationError(
                "BACKEND_API_URL harus dimulai dengan http:// atau https://."
            )
        api_key = str(values.get("BACKEND_API_KEY", "")).strip()
        if not api_key:
            raise InferenceConfigurationError(
                "BACKEND_API_KEY wajib diisi untuk mengirim status ke backend."
            )
        timeout = _parse_positive_float(
            values.get("BACKEND_REQUEST_TIMEOUT_SECONDS", "10"),
            "BACKEND_REQUEST_TIMEOUT_SECONDS",
        )
        retry_count = _parse_non_negative_int(
            values.get("BACKEND_RETRY_COUNT", "1"), "BACKEND_RETRY_COUNT"
        )
        return cls(
            cafe_id=cafe_id,
            roi_config_path=roi_path,
            backend_base_url=backend_base_url,
            backend_api_key=api_key,
            backend_timeout_seconds=timeout,
            backend_retry_count=retry_count,
        )


@dataclass(frozen=True)
class CycleResult:
    """Summary of one capture-to-backend cycle."""

    captured_at: datetime | None
    detections: int
    configured_tables: int
    successful_updates: int
    failed_updates: int
    skipped_reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
            "detections": self.detections,
            "configured_tables": self.configured_tables,
            "successful_updates": self.successful_updates,
            "failed_updates": self.failed_updates,
            "skipped_reason": self.skipped_reason,
        }


class BackendClient:
    """Small HTTP client for the existing backend status contract."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout_seconds: float = 10.0,
        retry_count: int = 1,
        client: Any | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if not api_key:
            raise InferenceConfigurationError("BACKEND_API_KEY wajib diisi.")
        if timeout_seconds <= 0 or retry_count < 0:
            raise InferenceConfigurationError("Timeout/retry backend tidak valid.")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.retry_count = retry_count
        self.logger = logger or LOGGER
        self._owns_client = client is None
        self._client = client if client is not None else self._create_client()

    def _create_client(self) -> Any:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise BackendClientError(
                "httpx belum terpasang; install inference/requirements.txt."
            ) from exc
        return httpx.Client(
            timeout=self.timeout_seconds,
            headers={"X-API-Key": self.api_key, "Accept": "application/json"},
        )

    def close(self) -> None:
        if self._owns_client and hasattr(self._client, "close"):
            self._client.close()

    def list_tables(self, cafe_id: int) -> dict[int, int]:
        """Return ``nomor_meja -> meja.id`` from the backend."""

        response = self._request("GET", f"/cafes/{cafe_id}/meja")
        try:
            payload = response.json()
        except Exception as exc:
            raise BackendClientError("Response daftar meja bukan JSON valid.") from exc
        if not isinstance(payload, list):
            raise BackendClientError("Response daftar meja harus berupa array.")
        result: dict[int, int] = {}
        for row in payload:
            if not isinstance(row, Mapping):
                raise BackendClientError("Item daftar meja bukan object JSON.")
            try:
                table_id = int(row["id"])
                table_number = int(row["nomor_meja"])
            except (KeyError, TypeError, ValueError) as exc:
                raise BackendClientError(
                    "Item daftar meja tidak memiliki id/nomor_meja."
                ) from exc
            if table_id <= 0 or table_number <= 0 or table_number in result:
                raise BackendClientError(
                    "Mapping meja dari backend tidak valid/duplikat."
                )
            result[table_number] = table_id
        return result

    def upsert_status(
        self,
        *,
        meja_id: int,
        terisi: int,
        status: str,
        updated_at: datetime,
    ) -> bool:
        """Post one table status; log and return False for an individual failure."""

        payload = {
            "meja_id": meja_id,
            "terisi": terisi,
            "status": status,
            "updated_at": _iso_timestamp(updated_at),
        }
        try:
            response = self._request("POST", "/internal/status", json=payload)
            result = response.json()
            if (
                not isinstance(result, Mapping)
                or result.get("action") not in VALID_ACTIONS
                or int(result.get("meja_id", 0)) != meja_id
            ):
                raise BackendClientError("Response upsert status tidak sesuai kontrak.")
            return True
        except (BackendClientError, ValueError, TypeError) as exc:
            self.logger.error("Gagal update meja_id=%s: %s", meja_id, exc)
            return False

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{path}"
        for attempt in range(self.retry_count + 1):
            try:
                response = self._client.request(method, url, **kwargs)
                status_code = int(response.status_code)
                if status_code >= 400:
                    raise BackendClientError(
                        f"Backend {method} {path} mengembalikan HTTP {status_code}."
                    )
                return response
            except BackendClientError:
                raise
            except Exception as exc:
                if attempt < self.retry_count:
                    self.logger.warning(
                        "Backend tidak dapat dihubungi (percobaan %s/%s): %s",
                        attempt + 1,
                        self.retry_count + 1,
                        exc,
                    )
                    time.sleep(0.1 * (attempt + 1))
                    continue
                raise BackendClientError(
                    f"Backend tidak dapat dihubungi setelah {self.retry_count + 1} percobaan."
                ) from exc
        raise BackendClientError("Request backend berhenti tanpa response.")


class InferenceRunner:
    """Coordinate one frame from capture through backend status updates."""

    def __init__(
        self,
        *,
        cafe_id: int,
        roi_config: ROIConfig,
        capture: Any,
        detector: PersonDetector,
        backend: BackendClient,
        snapshot_store: SnapshotStore | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.cafe_id = cafe_id
        self.roi_config = roi_config
        self.capture = capture
        self.detector = detector
        self.backend = backend
        self.snapshot_store = snapshot_store
        self.logger = logger or LOGGER

    def run_once(self) -> CycleResult:
        try:
            frame = self.capture.read()
        except Exception as exc:
            self.logger.error("Capture frame gagal; cycle dilewati: %s", exc)
            return CycleResult(
                None, 0, len(self.roi_config.rois), 0, 0, "capture_error"
            )

        captured_at = getattr(frame, "captured_at", datetime.now(timezone.utc))
        if self.snapshot_store is not None:
            try:
                reference = self.snapshot_store.save(
                    frame,
                    cafe_id=self.cafe_id,
                    captured_at=captured_at,
                )
                if reference is not None:
                    self.logger.info("Snapshot privat tersimpan: %s", reference.uri)
            except Exception as exc:
                self.logger.warning(
                    "Snapshot privat gagal disimpan; cycle tetap dilanjutkan: %s", exc
                )
        try:
            detections = tuple(self.detector.predict(frame))
        except Exception as exc:
            self.logger.error("Deteksi person gagal; frame dianggap kosong: %s", exc)
            detections = ()
        try:
            snapshot = calculate_occupancy(self.roi_config, detections)
        except Exception as exc:
            self.logger.error("Occupancy engine gagal; cycle dilewati: %s", exc)
            return CycleResult(
                captured_at,
                len(detections),
                len(self.roi_config.rois),
                0,
                0,
                "occupancy_error",
            )
        try:
            table_ids = self.backend.list_tables(self.cafe_id)
        except BackendClientError as exc:
            self.logger.error("Daftar meja gagal; cycle dilewati: %s", exc)
            return CycleResult(
                captured_at,
                len(detections),
                len(snapshot.meja),
                0,
                0,
                "backend_table_lookup_error",
            )

        successful = 0
        failed = 0
        for table in snapshot.meja:
            meja_id = table_ids.get(table.nomor_meja)
            if meja_id is None:
                self.logger.error(
                    "Meja nomor %s tidak ditemukan di backend; meja lain tetap diproses.",
                    table.nomor_meja,
                )
                failed += 1
                continue
            try:
                updated = self.backend.upsert_status(
                    meja_id=meja_id,
                    terisi=table.terisi,
                    status=table.status,
                    updated_at=captured_at,
                )
            except Exception as exc:
                self.logger.error(
                    "Update meja nomor %s gagal tanpa menghentikan meja lain: %s",
                    table.nomor_meja,
                    exc,
                )
                updated = False
            if updated:
                successful += 1
            else:
                failed += 1
        return CycleResult(
            captured_at,
            len(detections),
            len(snapshot.meja),
            successful,
            failed,
        )


def build_runtime(
    environ: Mapping[str, str] | None = None
) -> tuple[InferenceRunner, RuntimeConfig]:
    """Construct production components; imports optional runtime deps lazily."""

    _load_project_env()
    config = RuntimeConfig.from_env(environ)
    capture_config = CaptureConfig.from_env(environ)
    roi_config = load_roi_config(config.roi_config_path)
    detector = load_person_detector(environ)
    backend = BackendClient(
        config.backend_base_url,
        config.backend_api_key,
        timeout_seconds=config.backend_timeout_seconds,
        retry_count=config.backend_retry_count,
    )
    snapshot_store = build_snapshot_store(environ)
    capture = open_capture(capture_config)
    return (
        InferenceRunner(
            cafe_id=config.cafe_id,
            roi_config=roi_config,
            capture=capture,
            detector=detector,
            backend=backend,
            snapshot_store=snapshot_store,
        ),
        config,
    )


def run_scheduler(runner: InferenceRunner, interval_seconds: int) -> None:
    """Run recurring cycles through the pinned APScheduler dependency."""

    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise InferenceConfigurationError(
            "APScheduler belum terpasang; install inference/requirements.txt."
        ) from exc
    scheduler = BlockingScheduler()
    scheduler.add_job(
        runner.run_once, "interval", seconds=interval_seconds, max_instances=1
    )
    try:
        runner.run_once()
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown(wait=False)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--once", action="store_true", help="jalankan satu cycle lalu keluar"
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    try:
        runner, _config = build_runtime()
        if args.once:
            print(runner.run_once().as_dict())
        else:
            run_scheduler(runner, CaptureConfig.from_env().interval_seconds)
    except (
        InferenceConfigurationError,
        BackendClientError,
        OSError,
        RuntimeError,
        ValueError,
    ) as exc:
        LOGGER.error("Inference service tidak dapat dimulai: %s", exc)
        return 2
    finally:
        if "runner" in locals():
            runner.capture.close()
            runner.backend.close()
    return 0


def _iso_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_project_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    root_env = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(root_env)


def _parse_positive_int(value: object, name: str) -> int:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as exc:
        raise InferenceConfigurationError(
            f"{name} harus berupa integer positif."
        ) from exc
    if parsed <= 0:
        raise InferenceConfigurationError(f"{name} harus lebih besar dari nol.")
    return parsed


def _parse_non_negative_int(value: object, name: str) -> int:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as exc:
        raise InferenceConfigurationError(f"{name} harus berupa integer.") from exc
    if parsed < 0:
        raise InferenceConfigurationError(f"{name} tidak boleh negatif.")
    return parsed


def _parse_positive_float(value: object, name: str) -> float:
    try:
        parsed = float(str(value))
    except (TypeError, ValueError) as exc:
        raise InferenceConfigurationError(
            f"{name} harus berupa angka positif."
        ) from exc
    if parsed <= 0:
        raise InferenceConfigurationError(f"{name} harus lebih besar dari nol.")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
