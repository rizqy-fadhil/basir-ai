#!/usr/bin/env python3
"""Materialize a two-class Table/Chair dataset from a Roboflow YOLO export.

The source export may contain additional classes. This script keeps every
source image, filters only the ``table`` and ``chair`` boxes, and writes a
reproducible two-class dataset for the calibration model. The downloaded
dataset itself remains local and must not be committed to Git.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


TARGET_CLASSES = ("table", "chair")
SOURCE_SPLITS = (("train", "train"), ("val", "validation"), ("test", "test"))
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


class RoboflowPreparationError(RuntimeError):
    """Raised when a Roboflow export cannot be converted safely."""


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RoboflowPreparationError(
            "PyYAML belum terpasang; install inference/requirements.txt."
        ) from exc
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RoboflowPreparationError(
            f"gagal membaca dataset YAML {path}: {exc}"
        ) from exc
    if not isinstance(document, dict):
        raise RoboflowPreparationError(f"dataset YAML harus berupa mapping: {path}")
    return document


def _class_names(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        pairs = sorted(
            ((int(key), str(name)) for key, name in value.items()),
            key=lambda item: item[0],
        )
        return [name for _, name in pairs]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [str(name) for name in value]
    raise RoboflowPreparationError("field names pada dataset YAML tidak valid")


def _split_image_dir(
    source_root: Path, document: Mapping[str, Any], source_split: str
) -> Path:
    value = document.get(source_split)
    if value is None and source_split == "val":
        value = document.get("validation")
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        if len(value) != 1:
            raise RoboflowPreparationError(
                f"split {source_split} memiliki lebih dari satu path; tidak didukung"
            )
        value = value[0]
    if not isinstance(value, str) or not value.strip():
        raise RoboflowPreparationError(f"path split {source_split} tidak ditemukan")
    path = Path(value)
    if path.is_absolute():
        return path
    candidate = (source_root / path).resolve()
    if candidate.is_dir():
        return candidate
    # Some Roboflow exports contain ``../train/images`` although the archive
    # root already contains ``train``. Resolve that packaging inconsistency
    # only when the canonical path is absent and the safe fallback exists.
    relative_parts = [part for part in path.parts if part not in {"", ".", ".."}]
    fallback = source_root.joinpath(*relative_parts).resolve()
    if fallback.is_dir():
        return fallback
    return candidate


def _label_dir(image_dir: Path) -> Path:
    """Return the labels sibling used by a Roboflow YOLO export."""

    return image_dir.parent / "labels"


def _parse_label_line(line: str, label_path: Path, line_number: int) -> tuple[int, str]:
    fields = line.split()
    if len(fields) != 5:
        raise RoboflowPreparationError(
            f"format label tidak valid di {label_path}:{line_number}; expected 5 kolom"
        )
    try:
        class_id = int(fields[0])
        coordinates = [float(value) for value in fields[1:]]
    except ValueError as exc:
        raise RoboflowPreparationError(
            f"nilai label tidak valid di {label_path}:{line_number}"
        ) from exc
    if class_id < 0 or any(value < 0 or value > 1 for value in coordinates):
        raise RoboflowPreparationError(
            f"label di luar rentang YOLO normalized di {label_path}:{line_number}"
        )
    return class_id, " ".join(f"{value:.6f}" for value in coordinates)


def _write_yaml(output_dir: Path) -> None:
    content = (
        "# Generated from a local Roboflow Universe export; images and labels are ignored by Git.\n"
        f"path: {output_dir.resolve().as_posix()}\n"
        "train: images/train\n"
        "val: images/validation\n"
        "test: images/test\n"
        "names:\n"
        "  0: table\n"
        "  1: chair\n"
    )
    (output_dir / "data.yaml").write_text(content, encoding="utf-8")


def materialize_dataset(
    source_dir: Path,
    output_dir: Path,
    *,
    source_url: str | None = None,
    author: str | None = None,
    license_name: str | None = None,
    source_archive_sha256: str | None = None,
) -> dict[str, Any]:
    """Convert a Roboflow export into a two-class calibration dataset."""

    source_dir = source_dir.resolve()
    source_yaml = source_dir / "data.yaml"
    if not source_yaml.is_file():
        raise RoboflowPreparationError(f"dataset YAML tidak ditemukan: {source_yaml}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RoboflowPreparationError(
            f"output sudah berisi file, agar tidak menimpa artifact: {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    document = _load_yaml(source_yaml)
    names = _class_names(document.get("names"))
    normalized_names = {name.casefold(): index for index, name in enumerate(names)}
    missing_classes = [name for name in TARGET_CLASSES if name not in normalized_names]
    if missing_classes:
        raise RoboflowPreparationError(
            "class target tidak ditemukan di source YAML: " + ", ".join(missing_classes)
        )
    roboflow_metadata = document.get("roboflow", {})
    if not isinstance(roboflow_metadata, Mapping):
        roboflow_metadata = {}
    source_url = source_url or str(roboflow_metadata.get("url", ""))
    license_name = license_name or str(roboflow_metadata.get("license", ""))

    split_counts: dict[str, dict[str, int]] = {}
    provenance_rows: list[dict[str, str]] = []
    discarded_counts: Counter[str] = Counter()
    source_box_counts: Counter[str] = Counter()
    target_box_counts: Counter[str] = Counter()

    for source_split, output_split in SOURCE_SPLITS:
        source_images = _split_image_dir(source_dir, document, source_split)
        source_labels = _label_dir(source_images)
        if not source_images.is_dir():
            raise RoboflowPreparationError(
                f"folder image split tidak ditemukan: {source_images}"
            )
        output_images = output_dir / "images" / output_split
        output_labels = output_dir / "labels" / output_split
        output_images.mkdir(parents=True, exist_ok=True)
        output_labels.mkdir(parents=True, exist_ok=True)
        image_count = 0
        selected_image_count = 0
        image_paths = sorted(
            path
            for path in source_images.iterdir()
            if path.is_file() and path.suffix.casefold() in IMAGE_SUFFIXES
        )
        for image_path in image_paths:
            image_count += 1
            label_path = source_labels / f"{image_path.stem}.txt"
            output_image = output_images / image_path.name
            output_label = output_labels / f"{image_path.stem}.txt"
            shutil.copy2(image_path, output_image)
            selected_lines: list[str] = []
            source_box_count = 0
            if label_path.is_file():
                for line_number, raw_line in enumerate(
                    label_path.read_text(encoding="utf-8").splitlines(), start=1
                ):
                    if not raw_line.strip():
                        continue
                    source_class_id, coordinates = _parse_label_line(
                        raw_line, label_path, line_number
                    )
                    if source_class_id >= len(names):
                        raise RoboflowPreparationError(
                            f"class id {source_class_id} tidak ada di names pada {label_path}"
                        )
                    source_name = names[source_class_id].casefold()
                    source_box_counts[source_name] += 1
                    source_box_count += 1
                    if source_name not in TARGET_CLASSES:
                        discarded_counts[source_name] += 1
                        continue
                    target_id = TARGET_CLASSES.index(source_name)
                    selected_lines.append(f"{target_id} {coordinates}")
                    target_box_counts[source_name] += 1
            output_label.write_text(
                ("\n".join(selected_lines) + "\n") if selected_lines else "",
                encoding="utf-8",
            )
            if selected_lines:
                selected_image_count += 1
            provenance_rows.append(
                {
                    "source_split": source_split,
                    "output_split": output_split,
                    "source_image": str(image_path.relative_to(source_dir)),
                    "output_image": str(output_image.relative_to(output_dir)),
                    "source_label": (
                        str(label_path.relative_to(source_dir))
                        if label_path.exists()
                        else ""
                    ),
                    "source_box_count": str(source_box_count),
                    "target_box_count": str(len(selected_lines)),
                    "discarded_box_count": str(source_box_count - len(selected_lines)),
                }
            )
        split_counts[output_split] = {
            "images": image_count,
            "images_with_table_or_chair": selected_image_count,
        }

    _write_yaml(output_dir)
    provenance_path = output_dir / "provenance.csv"
    with provenance_path.open("w", encoding="utf-8", newline="") as stream:
        fields = list(provenance_rows[0]) if provenance_rows else ["source_split"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(provenance_rows)

    manifest: dict[str, Any] = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_dataset": "Roboflow Universe restaurant inference",
        "source_url": source_url,
        "author": author or "datasetvision",
        "license": license_name,
        "source_dir": str(source_dir),
        "source_yaml": str(source_yaml),
        "source_archive_sha256": source_archive_sha256,
        "source_class_names": names,
        "target_class_mapping": {"0": "table", "1": "chair"},
        "split_counts": split_counts,
        "source_box_counts": dict(source_box_counts),
        "target_box_counts": dict(target_box_counts),
        "discarded_non_target_box_counts": dict(discarded_counts),
        "preprocessing": {
            "source_format": "Roboflow YOLOv8",
            "target_coordinate_format": "YOLO normalized xywh",
            "image_policy": "keep every exported source image",
            "label_policy": "retain only table and chair; remap to class ids 0 and 1",
        },
        "provenance_file": str(provenance_path),
        "dataset_yaml": str(output_dir / "data.yaml"),
    }
    manifest_path = output_dir / "preparation_manifest.json"
    manifest["manifest_path"] = str(manifest_path)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-url", default="")
    parser.add_argument("--author", default="datasetvision")
    parser.add_argument("--license", dest="license_name", default="CC BY 4.0")
    parser.add_argument("--source-archive-sha256", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = materialize_dataset(
            args.source_dir,
            args.output_dir,
            source_url=args.source_url,
            author=args.author,
            license_name=args.license_name,
            source_archive_sha256=args.source_archive_sha256,
        )
    except (OSError, RoboflowPreparationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
