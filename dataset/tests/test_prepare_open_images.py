from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from dataset.prepare_open_images import (
    BoundingBox,
    DatasetPreparationError,
    CLASS_IDS,
    candidate_rows,
    load_annotations,
    load_curation,
    reviewed_rows,
    write_dataset_artifacts,
    write_csv,
)


class PrepareOpenImagesTests(unittest.TestCase):
    def test_candidate_order_and_review_gate(self) -> None:
        boxes = {
            "image-b": [
                BoundingBox("image-b", "chair", CLASS_IDS["chair"], 0, 1, 0, 1)
            ],
            "image-a": [
                BoundingBox("image-a", "table", CLASS_IDS["table"], 0.1, 0.5, 0.2, 0.8)
            ],
        }
        metadata = {
            "image-a": {
                "license": "CC BY 2.0",
                "original_url": "https://example.test/a.jpg",
                "original_landing_url": "https://example.test/a",
            },
            "image-b": {
                "license": "CC BY 2.0",
                "original_url": "https://example.test/b.jpg",
                "original_landing_url": "https://example.test/b",
            },
        }
        candidates = candidate_rows("validation", boxes, metadata)
        self.assertEqual(
            [row["image_id"] for row in candidates], ["image-a", "image-b"]
        )
        curation = {
            "image-a": {
                "curation_status": "include",
                "license_verified": "true",
                "scene_verified": "true",
            }
        }
        selected = reviewed_rows(candidates, curation)
        self.assertEqual([row["image_id"] for row in selected], ["image-a"])

    def test_review_requires_license_metadata(self) -> None:
        row = {
            "image_id": "image-a",
            "license": "",
            "original_url": "https://example.test/a.jpg",
            "original_landing_url": "",
            "curation_status": "include",
            "license_verified": "true",
            "scene_verified": "true",
        }
        with self.assertRaises(DatasetPreparationError):
            reviewed_rows([row], {})

    def test_annotation_filter_and_yolo_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            annotation_file = Path(directory) / "annotations.csv"
            with annotation_file.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=[
                        "ImageID",
                        "LabelName",
                        "Confidence",
                        "XMin",
                        "XMax",
                        "YMin",
                        "YMax",
                        "IsGroupOf",
                        "IsDepiction",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "ImageID": "ok",
                        "LabelName": "/m/table",
                        "Confidence": "1",
                        "XMin": "-0.1",
                        "XMax": "0.6",
                        "YMin": "0.2",
                        "YMax": "1.2",
                        "IsGroupOf": "0",
                        "IsDepiction": "0",
                    }
                )
                writer.writerow(
                    {
                        "ImageID": "group",
                        "LabelName": "/m/table",
                        "Confidence": "1",
                        "XMin": "0",
                        "XMax": "1",
                        "YMin": "0",
                        "YMax": "1",
                        "IsGroupOf": "1",
                        "IsDepiction": "0",
                    }
                )
            result = load_annotations(
                annotation_file,
                {"table": "/m/table", "chair": "/m/chair"},
            )
            self.assertEqual(list(result), ["ok"])
            self.assertEqual(
                result["ok"][0].to_yolo_line(), "0 0.300000 0.600000 0.600000 0.800000"
            )

    def test_artifact_writer_creates_labels_and_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "processed"
            row = {
                "image_id": "image-a",
                "split": "validation",
                "source": "open_images_v7",
                "original_url": "https://example.test/a.jpg",
                "original_landing_url": "https://example.test/a",
                "license": "CC BY 2.0",
                "author": "author",
                "title": "indoor seating",
                "label_names": "table",
                "box_count": "1",
                "license_verified": "true",
                "scene_verified": "true",
            }
            result = write_dataset_artifacts(
                output_dir,
                "validation",
                [row],
                {
                    "image-a": [
                        BoundingBox(
                            "image-a", "table", CLASS_IDS["table"], 0, 0.5, 0.25, 0.75
                        )
                    ]
                },
            )
            self.assertEqual(result["boxes_written"], 1)
            self.assertTrue(
                (output_dir / "labels" / "validation" / "image-a.txt").is_file()
            )
            self.assertTrue((output_dir / "provenance_validation.csv").is_file())
            self.assertIn(
                "path:", (output_dir / "data.yaml").read_text(encoding="utf-8")
            )

    def test_curation_csv_rejects_duplicate_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "curation.csv"
            write_csv(
                path,
                [
                    {"image_id": "same", "curation_status": "include"},
                    {"image_id": "same", "curation_status": "exclude"},
                ],
                ["image_id", "curation_status"],
            )
            with self.assertRaises(DatasetPreparationError):
                load_curation(path)


if __name__ == "__main__":
    unittest.main()
