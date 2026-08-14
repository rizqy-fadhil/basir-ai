from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dataset.split_manifest import (
    SplitManifestError,
    load_reviewed_rows,
    split_rows,
    write_split_artifacts,
)


def _row(image_id: str, labels: str = "table") -> dict[str, str]:
    return {
        "image_id": image_id,
        "split": "validation",
        "label_names": labels,
        "curation_status": "include",
        "license_verified": "true",
        "scene_verified": "true",
        "license": "CC BY 2.0",
        "original_url": "https://example.test/image.jpg",
    }


class SplitManifestTests(unittest.TestCase):
    def test_split_is_deterministic_and_disjoint(self) -> None:
        rows = [
            _row(f"image-{index}", "chair" if index % 3 == 0 else "table")
            for index in range(30)
        ]

        first = split_rows(rows, seed=7)
        second = split_rows(rows, seed=7)

        self.assertEqual(first, second)
        ids = [
            row["image_id"] for rows_in_split in first.values() for row in rows_in_split
        ]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), len(rows))
        self.assertEqual(
            sum(len(rows_in_split) for rows_in_split in first.values()), 30
        )

    def test_unverified_manifest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidates.csv"
            path.write_text(
                "image_id,split,label_names,curation_status,license_verified,scene_verified\n"
                "pending,validation,table,pending,false,false\n",
                encoding="utf-8",
            )

            with self.assertRaises(SplitManifestError):
                load_reviewed_rows(path)

    def test_write_split_artifacts_records_counts(self) -> None:
        rows = [_row(f"image-{index}") for index in range(10)]
        split = split_rows(rows, seed=42)
        with tempfile.TemporaryDirectory() as directory:
            processed_dir = Path(directory) / "processed"
            input_path = Path(directory) / "candidates.csv"
            input_path.write_text("candidate metadata", encoding="utf-8")

            manifest = write_split_artifacts(
                input_path,
                processed_dir,
                split,
                seed=42,
                ratios={"train": 0.7, "validation": 0.15, "test": 0.15},
            )

            self.assertEqual(
                manifest["counts"], {"train": 7, "validation": 2, "test": 1}
            )
            self.assertTrue(
                (processed_dir / "splits" / "split_manifest.json").is_file()
            )
            self.assertTrue((processed_dir / "data.yaml").is_file())


if __name__ == "__main__":
    unittest.main()
