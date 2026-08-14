#!/usr/bin/env python3
"""Create deterministic train/validation/test manifests from reviewed rows.

The splitter refuses pending or unverified rows. It only manages metadata and
already-generated YOLO artifacts; no raw image is committed to the repository.
Use ``--materialize`` after images and labels have been generated to copy them
into the local split directories expected by Ultralytics.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence


SPLIT_NAMES = ("train", "validation", "test")
DEFAULT_RATIOS = {"train": 0.70, "validation": 0.15, "test": 0.15}
REQUIRED_FIELDS = {
    "image_id",
    "split",
    "label_names",
    "curation_status",
    "license_verified",
    "scene_verified",
}


class SplitManifestError(RuntimeError):
    """Raised when reviewed dataset rows cannot be split safely."""


def _is_true(value: object) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "y", "on"}


def load_reviewed_rows(path: Path) -> list[dict[str, str]]:
    """Load only explicitly included rows with both required verification flags."""

    try:
        stream = path.open("r", encoding="utf-8", newline="")
    except OSError as exc:
        raise SplitManifestError(
            f"gagal membuka manifest curation {path}: {exc}"
        ) from exc
    with stream:
        reader = csv.DictReader(stream)
        missing = REQUIRED_FIELDS - set(reader.fieldnames or ())
        if missing:
            raise SplitManifestError(
                f"kolom curation belum lengkap: {', '.join(sorted(missing))}"
            )
        rows: list[dict[str, str]] = []
        seen_ids: set[str] = set()
        for raw_row in reader:
            row = {key: str(value or "").strip() for key, value in raw_row.items()}
            image_id = row.get("image_id", "")
            if not image_id:
                continue
            if image_id in seen_ids:
                raise SplitManifestError(f"image_id duplikat: {image_id}")
            seen_ids.add(image_id)
            if row.get("curation_status", "").casefold() != "include":
                continue
            if not _is_true(row.get("license_verified")) or not _is_true(
                row.get("scene_verified")
            ):
                continue
            rows.append(row)
    if not rows:
        raise SplitManifestError(
            "tidak ada row yang siap dibagi; tandai curation_status=include, "
            "license_verified=true, dan scene_verified=true setelah review manual."
        )
    return rows


def _stable_key(image_id: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{image_id}".encode("utf-8")).hexdigest()


def _allocate_counts(size: int, ratios: Mapping[str, float]) -> dict[str, int]:
    raw = {name: size * ratios[name] for name in SPLIT_NAMES}
    counts = {name: int(raw[name]) for name in SPLIT_NAMES}
    remainder = size - sum(counts.values())
    order = sorted(
        SPLIT_NAMES,
        key=lambda name: (raw[name] - counts[name], -SPLIT_NAMES.index(name)),
        reverse=True,
    )
    for name in order[:remainder]:
        counts[name] += 1
    return counts


def split_rows(
    rows: Sequence[Mapping[str, str]],
    *,
    seed: int = 42,
    ratios: Mapping[str, float] | None = None,
) -> dict[str, list[dict[str, str]]]:
    """Split rows deterministically while keeping each label combination represented."""

    selected_ratios = dict(DEFAULT_RATIOS if ratios is None else ratios)
    if set(selected_ratios) != set(SPLIT_NAMES):
        raise SplitManifestError("rasio harus memiliki train, validation, dan test")
    if any(value <= 0 for value in selected_ratios.values()):
        raise SplitManifestError("setiap rasio split harus lebih besar dari nol")
    ratio_total = sum(selected_ratios.values())
    if abs(ratio_total - 1.0) > 1e-9:
        raise SplitManifestError("jumlah rasio split harus sama dengan 1")

    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        labels = row.get("label_names", "").strip() or "unknown"
        groups[labels].append(dict(row))

    result = {name: [] for name in SPLIT_NAMES}
    for label_group in sorted(groups):
        group_rows = sorted(
            groups[label_group], key=lambda row: _stable_key(row["image_id"], seed)
        )
        counts = _allocate_counts(len(group_rows), selected_ratios)
        start = 0
        for split_name in SPLIT_NAMES:
            end = start + counts[split_name]
            for row in group_rows[start:end]:
                row["local_split"] = split_name
                result[split_name].append(row)
            start = end
    for split_name in SPLIT_NAMES:
        result[split_name].sort(key=lambda row: row["image_id"])
    return result


def _write_csv(path: Path, rows: Iterable[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row_list = [dict(row) for row in rows]
    fields = list(row_list[0]) if row_list else ["image_id", "local_split"]
    if "local_split" not in fields:
        fields.append("local_split")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(row_list)


def _copy_artifacts(rows: Iterable[Mapping[str, str]], processed_dir: Path) -> int:
    copied = 0
    for row in rows:
        local_split = row["local_split"]
        source_split = row["split"]
        image_id = row["image_id"]
        sources = (
            processed_dir / "labels" / source_split / f"{image_id}.txt",
            processed_dir / "images" / source_split / f"{image_id}.jpg",
        )
        destinations = (
            processed_dir / "labels" / local_split / f"{image_id}.txt",
            processed_dir / "images" / local_split / f"{image_id}.jpg",
        )
        missing = [str(path) for path in sources if not path.is_file()]
        if missing:
            raise SplitManifestError(
                f"artifact belum lengkap untuk {image_id}: {', '.join(missing)}"
            )
        for source, destination in zip(sources, destinations):
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        copied += 1
    return copied


def write_split_artifacts(
    input_path: Path,
    processed_dir: Path,
    split_rows_by_name: Mapping[str, Sequence[Mapping[str, str]]],
    *,
    seed: int,
    ratios: Mapping[str, float],
    materialize: bool = False,
) -> dict[str, object]:
    """Write split CSVs, dataset YAML, and an auditable split manifest."""

    splits_dir = processed_dir / "splits"
    for split_name in SPLIT_NAMES:
        _write_csv(splits_dir / f"{split_name}.csv", split_rows_by_name[split_name])

    all_rows = [row for split in SPLIT_NAMES for row in split_rows_by_name[split]]
    copied = _copy_artifacts(all_rows, processed_dir) if materialize else 0
    yaml_content = (
        "# Generated locally; data/open_images is ignored by Git.\n"
        f"path: {processed_dir.resolve().as_posix()}\n"
        "train: images/train\n"
        "val: images/validation\n"
        "test: images/test\n"
        "names:\n"
        "  0: table\n"
        "  1: chair\n"
    )
    yaml_path = processed_dir / "data.yaml"
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    yaml_path.write_text(yaml_content, encoding="utf-8")
    digest = hashlib.sha256(input_path.read_bytes()).hexdigest()
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_manifest": str(input_path),
        "source_manifest_sha256": digest,
        "seed": seed,
        "ratios": dict(ratios),
        "counts": {name: len(split_rows_by_name[name]) for name in SPLIT_NAMES},
        "materialized_artifacts": materialize,
        "artifacts_copied": copied,
    }
    manifest_path = splits_dir / "split_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/open_images/processed/candidates_validation.csv"),
        help="CSV kandidat yang sudah direview manual",
    )
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=Path("data/open_images/processed"),
        help="root artifact lokal yang di-ignore Git",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--materialize", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        rows = load_reviewed_rows(args.input)
        split_rows_by_name = split_rows(rows, seed=args.seed)
        manifest = write_split_artifacts(
            args.input,
            args.processed_dir,
            split_rows_by_name,
            seed=args.seed,
            ratios=DEFAULT_RATIOS,
            materialize=args.materialize,
        )
    except (OSError, SplitManifestError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
