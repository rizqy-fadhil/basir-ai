#!/usr/bin/env python3
"""Evaluate the fine-tuned Table/Chair detector on a held-out split."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


class EvaluationError(RuntimeError):
    """Raised when held-out evaluation cannot be completed safely."""


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


def _sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    detached = value.detach() if hasattr(value, "detach") else value
    cpu_value = detached.cpu() if hasattr(detached, "cpu") else detached
    converted = cpu_value.tolist() if hasattr(cpu_value, "tolist") else cpu_value
    if isinstance(converted, (list, tuple)):
        return list(converted)
    return [converted]


def _class_name(names: Any, class_id: int) -> str:
    if isinstance(names, Mapping):
        return str(names.get(class_id, names.get(str(class_id), class_id)))
    if isinstance(names, Sequence) and not isinstance(names, (str, bytes)):
        return str(names[class_id]) if class_id < len(names) else str(class_id)
    return str(class_id)


def extract_class_metrics(metrics: Any) -> dict[str, dict[str, float | None]]:
    """Extract precision, recall, mAP50, and mAP50-95 for each class.

    Ultralytics exposes these arrays on ``DetMetrics.box``. Missing arrays are
    represented as ``None`` rather than guessed values.
    """

    box = getattr(metrics, "box", None)
    if box is None:
        return {}
    precision = _sequence(getattr(box, "p", None))
    recall = _sequence(getattr(box, "r", None))
    map50 = _sequence(getattr(box, "ap50", None))
    map5095 = _sequence(getattr(box, "ap", None))
    class_indices = [
        int(float(value)) for value in _sequence(getattr(box, "ap_class_index", None))
    ]
    if not class_indices:
        class_indices = list(
            range(max(len(precision), len(recall), len(map50), len(map5095)))
        )
    names = getattr(metrics, "names", {})

    def value_or_none(values: Sequence[Any], index: int) -> float | None:
        if index >= len(values):
            return None
        try:
            return float(values[index])
        except (TypeError, ValueError):
            return None

    result: dict[str, dict[str, float | None]] = {}
    for position, class_id in enumerate(class_indices):
        result[_class_name(names, class_id)] = {
            "class_id": class_id,
            "precision": value_or_none(precision, position),
            "recall": value_or_none(recall, position),
            "mAP50": value_or_none(map50, position),
            "mAP50-95": value_or_none(map5095, position),
        }
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_evaluation_artifacts(data_path: Path, split: str) -> None:
    root = data_path.parent
    missing: list[str] = []
    for kind in ("images", "labels"):
        directory = root / kind / split
        if not directory.is_dir() or not any(directory.iterdir()):
            missing.append(str(directory))
    if missing:
        raise EvaluationError(
            f"artifact split {split} belum tersedia; jalankan split_manifest.py "
            "--materialize terlebih dahulu. Missing: " + ", ".join(missing)
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        type=Path,
        default=Path(
            os.environ.get(
                "YOLO_CALIBRATION_MODEL_PATH", "inference/models/table-chair-best.pt"
            )
        ),
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data/open_images/processed/data.yaml"),
    )
    parser.add_argument("--split", choices=("validation", "test"), default="test")
    parser.add_argument(
        "--imgsz", type=int, default=int(os.environ.get("YOLO_IMAGE_SIZE", "640"))
    )
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("runs/calibration/table-chair/evaluation.json"),
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def run_evaluation(args: argparse.Namespace) -> dict[str, Any]:
    if not args.data.is_file() and not args.dry_run:
        raise EvaluationError(f"dataset YAML tidak ditemukan: {args.data}")
    if not args.model.is_file() and not args.dry_run:
        raise EvaluationError(f"bobot calibration tidak ditemukan: {args.model}")
    result: dict[str, Any] = {
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": str(args.model),
        "weights_sha256": sha256_file(args.model) if args.model.is_file() else None,
        "dataset_yaml": str(args.data),
        "split": args.split,
        "image_size": args.imgsz,
        "batch": args.batch,
        "device": args.device or "ultralytics-default",
        "workers": args.workers,
        "model_exists": args.model.is_file(),
        "dataset_yaml_exists": args.data.is_file(),
    }
    if args.dry_run:
        result["status"] = "dry-run"
        return result
    _require_evaluation_artifacts(args.data, args.split)
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise EvaluationError(
            "Ultralytics belum terpasang. Install inference/requirements.txt."
        ) from exc

    model = YOLO(str(args.model))
    val_kwargs: dict[str, Any] = {
        "data": str(args.data),
        "split": args.split,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "workers": args.workers,
        "plots": False,
        "verbose": False,
    }
    if args.device:
        val_kwargs["device"] = args.device
    metrics = model.val(**val_kwargs)
    result["status"] = "completed"
    result["aggregate_metrics"] = _json_safe(getattr(metrics, "results_dict", {}) or {})
    result["per_class_metrics"] = extract_class_metrics(metrics)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(_json_safe(result), indent=2) + "\n", encoding="utf-8"
    )
    result["output"] = str(args.output)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.imgsz <= 0 or args.batch <= 0 or args.workers < 0:
        print(
            "ERROR: imgsz dan batch harus positif, workers tidak boleh negatif",
            file=sys.stderr,
        )
        return 2
    try:
        result = run_evaluation(args)
    except EvaluationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(_json_safe(result), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
