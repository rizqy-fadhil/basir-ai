from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from dataset.evaluate_table_chair import (
    extract_class_metrics,
    run_evaluation,
    build_parser,
)


class EvaluationTests(unittest.TestCase):
    def test_extracts_per_class_metrics_without_fabricating_values(self) -> None:
        metrics = SimpleNamespace(
            names={0: "table", 1: "chair"},
            box=SimpleNamespace(
                ap_class_index=[0, 1],
                p=[0.8, 0.6],
                r=[0.7, 0.5],
                ap50=[0.75, 0.55],
                ap=[0.40, 0.30],
            ),
        )

        result = extract_class_metrics(metrics)

        self.assertEqual(result["table"]["precision"], 0.8)
        self.assertEqual(result["chair"]["recall"], 0.5)
        self.assertEqual(result["table"]["mAP50-95"], 0.4)

    def test_missing_metric_array_is_none(self) -> None:
        metrics = SimpleNamespace(
            names={0: "table"},
            box=SimpleNamespace(ap_class_index=[0], p=[0.8], r=[], ap50=[], ap=[]),
        )

        result = extract_class_metrics(metrics)

        self.assertIsNone(result["table"]["recall"])
        self.assertIsNone(result["table"]["mAP50"])

    def test_dry_run_does_not_need_model_or_ultralytics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args = build_parser().parse_args(
                [
                    "--dry-run",
                    "--model",
                    str(Path(directory) / "missing.pt"),
                    "--data",
                    str(Path(directory) / "missing.yaml"),
                ]
            )

            result = run_evaluation(args)

            self.assertEqual(result["status"], "dry-run")
            self.assertFalse(result["model_exists"])
            self.assertFalse(result["dataset_yaml_exists"])


if __name__ == "__main__":
    unittest.main()
