from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from dataset.prepare_roboflow_table_chair import (
    RoboflowPreparationError,
    materialize_dataset,
)


class PrepareRoboflowTests(unittest.TestCase):
    def test_filters_extra_classes_and_remaps_table_chair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            for split in ("train", "valid", "test"):
                (source / split / "images").mkdir(parents=True)
                (source / split / "labels").mkdir(parents=True)
                (source / split / "images" / "frame.jpg").write_bytes(b"image")
                (source / split / "labels" / "frame.txt").write_text(
                    "0 0.1 0.2 0.3 0.4\n" "3 0.5 0.6 0.2 0.2\n" "1 0.2 0.3 0.1 0.1\n",
                    encoding="utf-8",
                )
            (source / "data.yaml").write_text(
                "train: ../train/images\n"
                "val: ../valid/images\n"
                "test: ../test/images\n"
                "names: [chair, customer, staff, table]\n",
                encoding="utf-8",
            )
            output = root / "output"

            manifest = materialize_dataset(
                source,
                output,
                source_url="https://universe.roboflow.com/example/project",
            )

            self.assertEqual(manifest["target_box_counts"], {"chair": 3, "table": 3})
            self.assertEqual(
                manifest["discarded_non_target_box_counts"], {"customer": 3}
            )
            self.assertEqual(
                (output / "labels" / "train" / "frame.txt").read_text(encoding="utf-8"),
                "1 0.100000 0.200000 0.300000 0.400000\n"
                "0 0.500000 0.600000 0.200000 0.200000\n",
            )
            data = yaml.safe_load((output / "data.yaml").read_text(encoding="utf-8"))
            self.assertEqual(data["names"], {0: "table", 1: "chair"})
            self.assertEqual(data["val"], "images/validation")

    def test_rejects_missing_target_class(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            (source / "train" / "images").mkdir(parents=True)
            (source / "data.yaml").write_text(
                "train: train/images\nnames: [chair, customer]\n", encoding="utf-8"
            )
            with self.assertRaises(RoboflowPreparationError):
                materialize_dataset(source, root / "output")


if __name__ == "__main__":
    unittest.main()
