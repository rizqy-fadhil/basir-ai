#!/usr/bin/env python3
"""Fine-tune the calibration detector on the reviewed Table/Chair dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


CLASS_MAPPING = {"0": "table", "1": "chair"}
EXPECTED_CLASS_NAMES = ("table", "chair")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data/open_images/processed/data.yaml"),
        help="Ultralytics dataset YAML dua class table/chair",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("YOLO_PERSON_MODEL_PATH", "yolov8n.pt"),
        help="base YOLOv8n untuk fine-tuning; default mengikuti YOLO_PERSON_MODEL_PATH",
    )
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument(
        "--imgsz", type=int, default=int(os.environ.get("YOLO_IMAGE_SIZE", "640"))
    )
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument(
        "--device",
        default="",
        help="misalnya cpu, 0, atau kosong untuk default Ultralytics",
    )
    parser.add_argument("--project", type=Path, default=Path("runs/calibration"))
    parser.add_argument("--name", default="table-chair")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument(
        "--manifest-out",
        type=Path,
        help="lokasi training manifest; default berada di folder run Ultralytics",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validasi konfigurasi tanpa mengimpor Ultralytics atau menjalankan training",
    )
    return parser


def _manifest_path(args: argparse.Namespace, run_dir: Path) -> Path:
    return args.manifest_out or (run_dir / "training_manifest.json")


def _dataset_metadata(data_path: Path) -> dict[str, Any]:
    """Read lightweight YAML metadata without making training depend on it early."""

    try:
        import yaml
    except ImportError:
        return {}
    try:
        document = yaml.safe_load(data_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    if isinstance(document, dict) and isinstance(document.get("roboflow"), Mapping):
        return document
    preparation_path = data_path.parent / "preparation_manifest.json"
    try:
        preparation = json.loads(preparation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return document if isinstance(document, dict) else {}
    if not isinstance(preparation, dict):
        return document if isinstance(document, dict) else {}
    return {
        "roboflow": {
            "source_dataset": preparation.get("source_dataset"),
            "source_url": preparation.get("source_url"),
            "author": preparation.get("author"),
            "license": preparation.get("license"),
            "source_archive_sha256": preparation.get("source_archive_sha256"),
            "source_class_names": preparation.get("source_class_names"),
            "target_class_mapping": preparation.get("target_class_mapping"),
        }
    }


def _provenance_path(data_path: Path) -> str | None:
    for filename in ("provenance.csv", "provenance_train.csv"):
        path = data_path.parent / filename
        if path.is_file():
            return str(path)
    return None


def _base_manifest(args: argparse.Namespace, run_dir: Path) -> dict[str, Any]:
    data_path = args.data.resolve()
    dataset_metadata = _dataset_metadata(data_path)
    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_model": args.model,
        "class_mapping": CLASS_MAPPING,
        "dataset_yaml": str(data_path),
        "provenance_file": _provenance_path(data_path),
        "dataset_metadata": dataset_metadata.get("roboflow", {}),
        "preprocessing": {
            "image_size": args.imgsz,
            "coordinate_format": "YOLO normalized xywh",
            "source_filter": "dataset-specific; see dataset_metadata and provenance_file",
        },
        "split": {
            "train": "images/train",
            "validation": "images/validation",
            "test": "images/test",
        },
        "hyperparameters": {
            "epochs": args.epochs,
            "batch": args.batch,
            "device": args.device or "ultralytics-default",
            "seed": args.seed,
            "workers": args.workers,
        },
        "run_dir": str(run_dir),
    }


def _require_training_artifacts(data_path: Path) -> None:
    """Reject an empty/generated-only YAML before Ultralytics starts training."""

    root = data_path.parent
    missing: list[str] = []
    for split in ("train", "validation"):
        for kind in ("images", "labels"):
            directory = root / kind / split
            if not directory.is_dir() or not any(directory.iterdir()):
                missing.append(str(directory))
    if missing:
        raise RuntimeError(
            "artifact train/validation belum siap; jalankan review, prepare, "
            "split_manifest.py --materialize terlebih dahulu. Missing: "
            + ", ".join(missing)
        )


def _require_table_chair_classes(data_path: Path) -> None:
    document = _dataset_metadata(data_path)
    names = document.get("names")
    if isinstance(names, Mapping):
        ordered_names = [
            str(value)
            for _, value in sorted(names.items(), key=lambda item: int(item[0]))
        ]
    elif isinstance(names, Sequence) and not isinstance(names, (str, bytes)):
        ordered_names = [str(value) for value in names]
    else:
        raise RuntimeError("dataset YAML tidak memiliki mapping names yang valid")
    if tuple(name.casefold() for name in ordered_names) != EXPECTED_CLASS_NAMES:
        raise RuntimeError(
            "dataset YAML harus memiliki tepat dua class dengan urutan table, chair; "
            f"ditemukan: {ordered_names}"
        )


def run_training(args: argparse.Namespace) -> dict[str, Any]:
    if not args.data.is_file() and not args.dry_run:
        raise RuntimeError(
            f"dataset YAML tidak ditemukan: {args.data}. "
            "Siapkan dataset dengan pipeline dataset yang terdokumentasi."
        )
    run_dir = args.project / args.name
    manifest = _base_manifest(args, run_dir)
    manifest["dataset_yaml_exists"] = args.data.is_file()
    if args.dry_run:
        manifest["status"] = "dry-run"
        return manifest
    _require_training_artifacts(args.data)
    _require_table_chair_classes(args.data)
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError(
            "Ultralytics belum terpasang. Install inference/requirements.txt "
            "di environment training, lalu ulangi perintah ini."
        ) from exc

    train_kwargs: dict[str, Any] = {
        "data": str(args.data),
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "project": str(args.project),
        "name": args.name,
        "seed": args.seed,
        "workers": args.workers,
    }
    if args.device:
        train_kwargs["device"] = args.device
    model = YOLO(args.model)
    results = model.train(**train_kwargs)
    actual_run_dir = Path(getattr(results, "save_dir", run_dir))
    manifest["run_dir"] = str(actual_run_dir)
    manifest["status"] = "completed"
    manifest["metrics"] = _json_safe(getattr(results, "results_dict", {}) or {})
    best_weights = actual_run_dir / "weights" / "best.pt"
    manifest["best_weights"] = str(best_weights)
    manifest["best_weights_sha256"] = (
        sha256_file(best_weights) if best_weights.is_file() else None
    )
    manifest_path = _manifest_path(args, actual_run_dir)
    manifest["manifest_path"] = str(manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.epochs <= 0 or args.imgsz <= 0 or args.batch <= 0 or args.workers < 0:
        print(
            "ERROR: epochs, imgsz, batch harus positif dan workers tidak boleh negatif",
            file=sys.stderr,
        )
        return 2
    try:
        result = run_training(args)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(_json_safe(result), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
