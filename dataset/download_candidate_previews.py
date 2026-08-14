#!/usr/bin/env python3
"""Download local previews for manual Open Images candidate review.

The preview flow is deliberately separate from dataset materialization. It
only reads the candidate CSV, downloads the public source image to an ignored
directory, and writes an audit manifest. It never changes curation or license
verification flags; a human must review those fields separately.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


DEFAULT_INPUT = Path("data/open_images/processed/candidates_validation.csv")
DEFAULT_OUTPUT = Path("data/open_images/preview")
DEFAULT_MAX_BYTES = 15 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_RETRY_COUNT = 2
USER_AGENT = "basir-ai-open-images-preview/1.0"
IMAGE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
PREVIEW_FIELDS = (
    "image_id",
    "split",
    "source_url",
    "preview_path",
    "status",
    "bytes",
    "sha256",
    "error",
    "curation_status",
    "license_verified",
    "scene_verified",
)


class PreviewDownloadError(RuntimeError):
    """Raised when candidate preview input or output is unsafe."""


UrlOpen = Callable[..., Any]


def load_candidates(path: Path) -> list[dict[str, str]]:
    """Load candidates while preserving all human-review fields unchanged."""

    try:
        stream = path.open("r", encoding="utf-8", newline="")
    except OSError as exc:
        raise PreviewDownloadError(f"gagal membuka kandidat {path}: {exc}") from exc
    with stream:
        reader = csv.DictReader(stream)
        required = {"image_id", "split", "original_url"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise PreviewDownloadError(
                f"kolom kandidat belum lengkap: {', '.join(sorted(missing))}"
            )
        rows: list[dict[str, str]] = []
        seen_ids: set[str] = set()
        for line_number, raw_row in enumerate(reader, start=2):
            row = {key: str(value or "").strip() for key, value in raw_row.items()}
            image_id = row.get("image_id", "")
            if not image_id or not IMAGE_ID_PATTERN.fullmatch(image_id):
                raise PreviewDownloadError(
                    f"image_id tidak aman pada baris {line_number}: {image_id!r}"
                )
            if image_id in seen_ids:
                raise PreviewDownloadError(f"image_id duplikat: {image_id}")
            seen_ids.add(image_id)
            rows.append(row)
    if not rows:
        raise PreviewDownloadError(f"CSV kandidat kosong: {path}")
    return rows


def download_previews(
    input_path: Path,
    output_dir: Path,
    *,
    max_images: int = 0,
    overwrite: bool = False,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    retry_count: int = DEFAULT_RETRY_COUNT,
    max_bytes: int = DEFAULT_MAX_BYTES,
    urlopen: UrlOpen | None = None,
) -> dict[str, object]:
    """Download candidate previews and return a summary with manifest path.

    Failed downloads are recorded and do not stop other candidates. The caller
    receives a non-zero CLI exit code when any row failed, so a partial preview
    set cannot be mistaken for a complete review set.
    """

    if max_images < 0:
        raise PreviewDownloadError("--max-images tidak boleh negatif")
    if timeout_seconds <= 0:
        raise PreviewDownloadError("--timeout harus lebih besar dari nol")
    if retry_count < 0:
        raise PreviewDownloadError("--retry-count tidak boleh negatif")
    if max_bytes <= 0:
        raise PreviewDownloadError("--max-bytes harus lebih besar dari nol")

    rows = load_candidates(input_path)
    selected = rows if max_images == 0 else rows[:max_images]
    opener = urlopen or urllib.request.urlopen
    manifest_rows: list[dict[str, str]] = []
    counts = {"downloaded": 0, "exists": 0, "missing_url": 0, "failed": 0}

    for row in selected:
        image_id = row["image_id"]
        split = row.get("split", "unknown") or "unknown"
        source_url = row.get("original_url", "")
        destination = output_dir / split / f"{image_id}.jpg"
        result = {
            "image_id": image_id,
            "split": split,
            "source_url": source_url,
            "preview_path": str(destination),
            "status": "",
            "bytes": "0",
            "sha256": "",
            "error": "",
            "curation_status": row.get("curation_status", ""),
            "license_verified": row.get("license_verified", ""),
            "scene_verified": row.get("scene_verified", ""),
        }
        try:
            if not source_url:
                result["status"] = "missing_url"
                counts["missing_url"] += 1
            elif destination.is_file() and not overwrite:
                result["status"] = "exists"
                result["bytes"] = str(destination.stat().st_size)
                result["sha256"] = sha256_file(destination)
                counts["exists"] += 1
            else:
                size, digest = _download_one(
                    source_url,
                    destination,
                    timeout_seconds=timeout_seconds,
                    retry_count=retry_count,
                    max_bytes=max_bytes,
                    urlopen=opener,
                )
                result["status"] = "downloaded"
                result["bytes"] = str(size)
                result["sha256"] = digest
                counts["downloaded"] += 1
        except PreviewDownloadError as exc:
            result["status"] = "failed"
            result["error"] = str(exc)
            counts["failed"] += 1
        manifest_rows.append(result)

    manifest_path = output_dir / "preview_manifest.csv"
    _write_manifest(manifest_path, manifest_rows)
    return {
        "input": str(input_path),
        "output_dir": str(output_dir),
        "manifest": str(manifest_path),
        "requested": len(selected),
        "total_candidates": len(rows),
        "counts": counts,
        "curation_flags_changed": False,
    }


def _download_one(
    url: str,
    destination: Path,
    *,
    timeout_seconds: float,
    retry_count: int,
    max_bytes: int,
    urlopen: UrlOpen,
) -> tuple[int, str]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(f"{destination.suffix}.part")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "image/*"},
    )
    last_error: Exception | None = None
    for attempt in range(retry_count + 1):
        temporary.unlink(missing_ok=True)
        try:
            with urlopen(request, timeout=timeout_seconds) as response, temporary.open(
                "wb"
            ) as stream:
                declared_length = response.headers.get("Content-Length")
                if declared_length and int(declared_length) > max_bytes:
                    raise PreviewDownloadError(
                        f"ukuran image melebihi batas {max_bytes} byte"
                    )
                total = 0
                digest = hashlib.sha256()
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise PreviewDownloadError(
                            f"ukuran image melebihi batas {max_bytes} byte"
                        )
                    stream.write(chunk)
                    digest.update(chunk)
            if total == 0:
                raise PreviewDownloadError("response image kosong")
            os.replace(temporary, destination)
            return total, digest.hexdigest()
        except PreviewDownloadError:
            temporary.unlink(missing_ok=True)
            raise
        except (OSError, TimeoutError, urllib.error.URLError, ValueError) as exc:
            last_error = exc
            temporary.unlink(missing_ok=True)
            if attempt < retry_count:
                time.sleep(0.1 * (attempt + 1))
                continue
    raise PreviewDownloadError(
        f"gagal mengunduh preview setelah {retry_count + 1} percobaan: {last_error}"
    )


def _write_manifest(path: Path, rows: Iterable[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=PREVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def sha256_file(path: Path) -> str:
    """Return the checksum used to identify a downloaded preview."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--max-images",
        type=int,
        default=0,
        help="batasi jumlah preview; 0 = semua kandidat",
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="unduh ulang preview yang sudah ada"
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--retry-count", type=int, default=DEFAULT_RETRY_COUNT)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = download_previews(
            args.input,
            args.output_dir,
            max_images=args.max_images,
            overwrite=args.overwrite,
            timeout_seconds=args.timeout,
            retry_count=args.retry_count,
            max_bytes=args.max_bytes,
        )
    except PreviewDownloadError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result["counts"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
