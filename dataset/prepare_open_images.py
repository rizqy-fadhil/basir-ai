#!/usr/bin/env python3
"""Prepare a reviewed Table/Chair subset of Open Images for YOLO training.

The script deliberately keeps source data outside Git.  It first creates a
candidate manifest from the official Open Images annotations and image
metadata.  Training labels and optional image downloads are only created for
rows that a human has marked as both license-verified and indoor/seating
scene-verified in the curation file.

The implementation uses only the Python standard library so that candidate
discovery and validation do not require the training environment.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


OPEN_IMAGES_CLASS_DESCRIPTIONS_URL = (
    "https://storage.googleapis.com/openimages/v5/class-descriptions-boxable.csv"
)
OPEN_IMAGES_ANNOTATION_URLS = {
    "train": "https://storage.googleapis.com/openimages/v6/oidv6-train-annotations-bbox.csv",
    "validation": "https://storage.googleapis.com/openimages/v5/validation-annotations-bbox.csv",
    "test": "https://storage.googleapis.com/openimages/v5/test-annotations-bbox.csv",
}
OPEN_IMAGES_METADATA_URLS = {
    "train": "https://storage.googleapis.com/openimages/2018_04/train/train-images-boxable.csv",
    "validation": "https://storage.googleapis.com/openimages/2018_04/validation/validation-images-with-rotation.csv",
    "test": "https://storage.googleapis.com/openimages/2018_04/test/test-images-with-rotation.csv",
}
OPEN_IMAGES_IMAGE_URL_TEMPLATE = (
    "https://open-images-dataset.s3.amazonaws.com/{split}/{image_id}.jpg"
)

CLASS_NAMES = ("table", "chair")
CLASS_IDS = {name: index for index, name in enumerate(CLASS_NAMES)}
SPLIT_ALIASES = {
    "val": "validation",
    "validation": "validation",
    "train": "train",
    "test": "test",
}
USER_AGENT = "basir-ai-open-images-preparer/1.0"

CANDIDATE_FIELDS = (
    "image_id",
    "split",
    "source",
    "label_names",
    "box_count",
    "original_url",
    "original_landing_url",
    "license",
    "author",
    "title",
    "curation_status",
    "license_verified",
    "scene_verified",
)
PROVENANCE_FIELDS = (
    "image_id",
    "split",
    "source",
    "original_url",
    "original_landing_url",
    "license",
    "author",
    "title",
    "label_names",
    "box_count",
    "curation_status",
    "license_verified",
    "scene_verified",
)


class DatasetPreparationError(RuntimeError):
    """Raised when source data or curation input is invalid."""


@dataclass(frozen=True)
class BoundingBox:
    """A normalized Open Images bounding box with a two-class YOLO label."""

    image_id: str
    class_name: str
    class_id: int
    xmin: float
    xmax: float
    ymin: float
    ymax: float

    def to_yolo_line(self) -> str:
        center_x = (self.xmin + self.xmax) / 2
        center_y = (self.ymin + self.ymax) / 2
        width = self.xmax - self.xmin
        height = self.ymax - self.ymin
        return f"{self.class_id} {center_x:.6f} {center_y:.6f} {width:.6f} {height:.6f}"


def canonical_split(split: str) -> str:
    """Return the Open Images split name used in URLs and output folders."""

    try:
        return SPLIT_ALIASES[split.strip().lower()]
    except KeyError as exc:
        choices = ", ".join(sorted(SPLIT_ALIASES))
        raise DatasetPreparationError(
            f"split harus salah satu dari: {choices}"
        ) from exc


def as_bool(value: object) -> bool:
    """Parse the boolean values used by Open Images and the curation CSV."""

    return str(value or "").strip().casefold() in {"1", "true", "t", "yes", "y"}


def _float_field(row: Mapping[str, str], name: str, default: float = 0.0) -> float:
    value = str(row.get(name, "") or "").strip()
    if not value:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise DatasetPreparationError(f"nilai {name!r} bukan angka: {value!r}") from exc


def _clip_unit(value: float) -> float:
    return min(1.0, max(0.0, value))


def _atomic_download(url: str, destination: Path, timeout: int = 120) -> None:
    """Download a source file atomically, without leaving partial CSVs."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.name}.",
            suffix=".part",
            dir=destination.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                shutil.copyfileobj(response, temporary)
        os.replace(temporary_path, destination)
    except (OSError, urllib.error.URLError) as exc:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise DatasetPreparationError(f"gagal mengunduh {url}: {exc}") from exc


def ensure_source_files(raw_dir: Path, split: str, fetch: bool) -> dict[str, Path]:
    """Return local source paths, downloading them only when explicitly requested."""

    split = canonical_split(split)
    files = {
        "classes": raw_dir / "class-descriptions-boxable.csv",
        "annotations": raw_dir / f"{split}-annotations-bbox.csv",
        "metadata": raw_dir / f"{split}-images.csv",
    }
    urls = {
        "classes": OPEN_IMAGES_CLASS_DESCRIPTIONS_URL,
        "annotations": OPEN_IMAGES_ANNOTATION_URLS[split],
        "metadata": OPEN_IMAGES_METADATA_URLS[split],
    }
    if fetch:
        for name, path in files.items():
            if not path.exists():
                print(f"Mengunduh {name}: {urls[name]}", file=sys.stderr)
                _atomic_download(urls[name], path)
    missing = [f"{name} ({path})" for name, path in files.items() if not path.is_file()]
    if missing:
        joined = ", ".join(missing)
        raise DatasetPreparationError(
            f"source belum tersedia: {joined}. Jalankan ulang dengan --fetch-sources."
        )
    return files


def load_class_mids(class_file: Path) -> dict[str, str]:
    """Resolve the Open Images MIDs for Table and Chair."""

    resolved: dict[str, str] = {}
    with class_file.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.reader(stream):
            if len(row) < 2 or row[0].strip().casefold() == "mid":
                continue
            mid, display_name = row[0].strip(), row[1].strip().casefold()
            if display_name in CLASS_IDS:
                resolved[display_name] = mid
    missing = sorted(set(CLASS_NAMES) - set(resolved))
    if missing:
        raise DatasetPreparationError(
            f"class Open Images tidak ditemukan: {', '.join(missing)}"
        )
    return resolved


def load_annotations(
    annotation_file: Path,
    class_mids: Mapping[str, str],
    *,
    min_confidence: float = 0.5,
) -> dict[str, list[BoundingBox]]:
    """Load only Table/Chair boxes and convert their coordinates safely."""

    mid_to_name = {mid: name for name, mid in class_mids.items()}
    by_image: dict[str, list[BoundingBox]] = defaultdict(list)
    required = {"ImageID", "LabelName", "XMin", "XMax", "YMin", "YMax"}
    with annotation_file.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        missing_headers = required - set(reader.fieldnames or ())
        if missing_headers:
            raise DatasetPreparationError(
                f"kolom anotasi tidak lengkap: {', '.join(sorted(missing_headers))}"
            )
        for row in reader:
            class_name = mid_to_name.get(str(row.get("LabelName", "")).strip())
            if class_name is None:
                continue
            if (
                row.get("Confidence")
                and _float_field(row, "Confidence") < min_confidence
            ):
                continue
            if as_bool(row.get("IsGroupOf")) or as_bool(row.get("IsDepiction")):
                continue
            image_id = str(row.get("ImageID", "")).strip()
            if not image_id:
                continue
            xmin = _clip_unit(_float_field(row, "XMin"))
            xmax = _clip_unit(_float_field(row, "XMax"))
            ymin = _clip_unit(_float_field(row, "YMin"))
            ymax = _clip_unit(_float_field(row, "YMax"))
            if xmax <= xmin or ymax <= ymin:
                continue
            by_image[image_id].append(
                BoundingBox(
                    image_id=image_id,
                    class_name=class_name,
                    class_id=CLASS_IDS[class_name],
                    xmin=xmin,
                    xmax=xmax,
                    ymin=ymin,
                    ymax=ymax,
                )
            )
    return dict(by_image)


def load_image_metadata(
    metadata_file: Path, image_ids: Iterable[str]
) -> dict[str, dict[str, str]]:
    """Load metadata only for candidate image IDs to keep memory bounded."""

    wanted = set(image_ids)
    metadata: dict[str, dict[str, str]] = {}
    if not wanted:
        return metadata
    with metadata_file.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if "ImageID" not in (reader.fieldnames or ()):
            raise DatasetPreparationError(
                "metadata gambar tidak memiliki kolom ImageID"
            )
        for row in reader:
            image_id = str(row.get("ImageID", "")).strip()
            if image_id not in wanted:
                continue
            metadata[image_id] = {
                "original_url": str(row.get("OriginalURL", "") or "").strip(),
                "original_landing_url": str(
                    row.get("OriginalLandingURL", "") or ""
                ).strip(),
                "license": str(row.get("License", "") or "").strip(),
                "author": str(row.get("Author", "") or "").strip(),
                "title": str(row.get("Title", "") or "").strip(),
            }
    return metadata


def candidate_rows(
    split: str,
    annotations: Mapping[str, Sequence[BoundingBox]],
    metadata: Mapping[str, Mapping[str, str]],
    *,
    max_images: int = 0,
) -> list[dict[str, str]]:
    """Build deterministic, human-reviewable curation rows."""

    split = canonical_split(split)
    image_ids = sorted(annotations)
    if max_images < 0:
        raise DatasetPreparationError("--max-images tidak boleh negatif")
    if max_images:
        image_ids = image_ids[:max_images]
    rows: list[dict[str, str]] = []
    for image_id in image_ids:
        boxes = annotations[image_id]
        labels = sorted(
            {box.class_name for box in boxes}, key=lambda name: CLASS_IDS[name]
        )
        source = "open_images_v7"
        details = metadata.get(image_id, {})
        rows.append(
            {
                "image_id": image_id,
                "split": split,
                "source": source,
                "label_names": ";".join(labels),
                "box_count": str(len(boxes)),
                "original_url": str(details.get("original_url", "")),
                "original_landing_url": str(details.get("original_landing_url", "")),
                "license": str(details.get("license", "")),
                "author": str(details.get("author", "")),
                "title": str(details.get("title", "")),
                "curation_status": "pending",
                "license_verified": "false",
                "scene_verified": "false",
            }
        )
    return rows


def write_csv(
    path: Path, rows: Iterable[Mapping[str, object]], fields: Sequence[str]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def load_curation(path: Path) -> dict[str, dict[str, str]]:
    """Load manual review flags and reject duplicate image IDs."""

    result: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if "image_id" not in (reader.fieldnames or ()):
            raise DatasetPreparationError("curation CSV wajib memiliki kolom image_id")
        for row in reader:
            image_id = str(row.get("image_id", "")).strip()
            if not image_id:
                continue
            if image_id in result:
                raise DatasetPreparationError(
                    f"image_id duplikat di curation CSV: {image_id}"
                )
            result[image_id] = {
                key: str(value or "").strip() for key, value in row.items()
            }
    return result


def reviewed_rows(
    rows: Sequence[Mapping[str, str]], curation: Mapping[str, Mapping[str, str]]
) -> list[dict[str, str]]:
    """Return rows explicitly approved for both licensing and scene suitability."""

    selected: list[dict[str, str]] = []
    for source_row in rows:
        row = dict(source_row)
        review = curation.get(row["image_id"], {})
        for field in ("curation_status", "license_verified", "scene_verified"):
            if field in review and review[field] != "":
                row[field] = review[field]
        if row["curation_status"].casefold() != "include":
            continue
        if not as_bool(row["license_verified"]) or not as_bool(row["scene_verified"]):
            continue
        if not row["license"]:
            raise DatasetPreparationError(
                f"{row['image_id']} ditandai include tetapi metadata License kosong"
            )
        if not row["original_url"] and not row["original_landing_url"]:
            raise DatasetPreparationError(
                f"{row['image_id']} ditandai include tetapi URL sumber kosong"
            )
        selected.append(row)
    return selected


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def _download_image(
    image_id: str, split: str, destination: Path, url_template: str
) -> None:
    url = url_template.format(split=split, image_id=image_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(f"{destination.suffix}.part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open(
            "wb"
        ) as stream:
            shutil.copyfileobj(response, stream)
        if temporary.stat().st_size == 0:
            raise DatasetPreparationError(f"gambar kosong dari {url}")
        os.replace(temporary, destination)
    except (OSError, urllib.error.URLError) as exc:
        temporary.unlink(missing_ok=True)
        raise DatasetPreparationError(
            f"gagal mengunduh gambar {image_id}: {exc}"
        ) from exc


def write_dataset_artifacts(
    output_dir: Path,
    split: str,
    selected_rows: Sequence[Mapping[str, str]],
    annotations: Mapping[str, Sequence[BoundingBox]],
    *,
    download_images: bool = False,
    image_url_template: str = OPEN_IMAGES_IMAGE_URL_TEMPLATE,
) -> dict[str, object]:
    """Write YOLO labels, provenance, and a local data YAML for reviewed rows."""

    split = canonical_split(split)
    labels_dir = output_dir / "labels" / split
    images_dir = output_dir / "images" / split
    for row in selected_rows:
        image_id = row["image_id"]
        boxes = annotations.get(image_id, ())
        if not boxes:
            raise DatasetPreparationError(f"anotasi kosong untuk image_id {image_id}")
        label_content = "\n".join(box.to_yolo_line() for box in boxes) + "\n"
        _write_text(labels_dir / f"{image_id}.txt", label_content)
        if download_images:
            _download_image(
                image_id, split, images_dir / f"{image_id}.jpg", image_url_template
            )
    write_csv(output_dir / f"provenance_{split}.csv", selected_rows, PROVENANCE_FIELDS)
    yaml_content = (
        f"# Generated locally; raw images, labels, and this directory are ignored by Git.\n"
        f"path: {output_dir.resolve().as_posix()}\n"
        f"train: images/train\n"
        f"val: images/validation\n"
        f"names:\n"
        f"  0: table\n"
        f"  1: chair\n"
    )
    _write_text(output_dir / "data.yaml", yaml_content)
    return {
        "split": split,
        "images_selected": len(selected_rows),
        "boxes_written": sum(
            len(annotations[row["image_id"]]) for row in selected_rows
        ),
        "images_downloaded": bool(download_images),
        "output_dir": str(output_dir),
    }


def prepare(
    *,
    raw_dir: Path,
    output_dir: Path,
    split: str,
    fetch_sources: bool = False,
    curation_file: Path | None = None,
    max_images: int = 0,
    min_confidence: float = 0.5,
    download_images: bool = False,
    image_url_template: str = OPEN_IMAGES_IMAGE_URL_TEMPLATE,
) -> dict[str, object]:
    """Run candidate generation and, when approved, YOLO artifact creation."""

    split = canonical_split(split)
    if not 0 <= min_confidence <= 1:
        raise DatasetPreparationError("--min-confidence harus berada di antara 0 dan 1")
    sources = ensure_source_files(raw_dir, split, fetch_sources)
    class_mids = load_class_mids(sources["classes"])
    annotations = load_annotations(
        sources["annotations"], class_mids, min_confidence=min_confidence
    )
    metadata = load_image_metadata(sources["metadata"], annotations)
    candidates = candidate_rows(split, annotations, metadata, max_images=max_images)
    candidate_path = output_dir / f"candidates_{split}.csv"
    write_csv(candidate_path, candidates, CANDIDATE_FIELDS)
    result: dict[str, object] = {
        "split": split,
        "candidate_images": len(candidates),
        "candidate_boxes": sum(int(row["box_count"]) for row in candidates),
        "candidate_manifest": str(candidate_path),
        "reviewed_images": 0,
    }
    if curation_file is None:
        result["next_step"] = (
            "review curation_status, license_verified, and scene_verified, "
            "then rerun with --curation-file"
        )
        return result
    curation = load_curation(curation_file)
    selected = reviewed_rows(candidates, curation)
    result.update(
        write_dataset_artifacts(
            output_dir,
            split,
            selected,
            annotations,
            download_images=download_images,
            image_url_template=image_url_template,
        )
    )
    result["reviewed_images"] = len(selected)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", default="validation", choices=sorted(SPLIT_ALIASES))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/open_images/raw"))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/open_images/processed")
    )
    parser.add_argument(
        "--fetch-sources",
        action="store_true",
        help="unduh CSV resmi Open Images jika belum ada di --raw-dir",
    )
    parser.add_argument(
        "--curation-file",
        type=Path,
        help="CSV hasil review manusia; hanya row include + dua verifikasi yang diproses",
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=0,
        help="batasi kandidat untuk smoke test; 0 = semua",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.5,
        help="confidence anotasi minimum (default: 0.5)",
    )
    parser.add_argument(
        "--download-images",
        action="store_true",
        help="unduh gambar S3 hanya untuk row yang telah diverifikasi dan di-include",
    )
    parser.add_argument(
        "--image-url-template",
        default=OPEN_IMAGES_IMAGE_URL_TEMPLATE,
        help="template URL gambar dengan placeholder {split} dan {image_id}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = prepare(
            raw_dir=args.raw_dir,
            output_dir=args.output_dir,
            split=args.split,
            fetch_sources=args.fetch_sources,
            curation_file=args.curation_file,
            max_images=args.max_images,
            min_confidence=args.min_confidence,
            download_images=args.download_images,
            image_url_template=args.image_url_template,
        )
    except DatasetPreparationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
