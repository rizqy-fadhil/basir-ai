from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from inference.roi import ROIConfigError, load_roi_config


ROOT = Path(__file__).resolve().parents[2]
ROI_PATH = ROOT / "inference" / "config" / "roi_config.json"


class ROIConfigTests(unittest.TestCase):
    def test_repository_fixture_has_four_unique_tables(self) -> None:
        config = load_roi_config(ROI_PATH)

        self.assertEqual(config.cafe_id, 1)
        self.assertEqual(config.area_kamera, "workspace-1")
        self.assertEqual((config.frame_width, config.frame_height), (32, 18))
        self.assertEqual(len(config.rois), 4)
        self.assertEqual([table.nomor_meja for table in config.rois], [1, 2, 3, 4])

    def test_duplicate_table_number_is_rejected(self) -> None:
        document = {
            "cafe_id": 1,
            "area_kamera": "workspace-1",
            "frame_width": 10,
            "frame_height": 10,
            "rois": [
                {"nomor_meja": 1, "kapasitas": 2, "polygon": [[0, 0], [2, 0], [2, 2]]},
                {"nomor_meja": 1, "kapasitas": 2, "polygon": [[3, 0], [5, 0], [5, 2]]},
            ],
        }
        with self.assertRaises(ROIConfigError):
            self._load_temporary(document)

    def test_out_of_bounds_polygon_is_rejected(self) -> None:
        document = {
            "cafe_id": 1,
            "area_kamera": "workspace-1",
            "frame_width": 10,
            "frame_height": 10,
            "rois": [
                {"nomor_meja": 1, "kapasitas": 2, "polygon": [[0, 0], [11, 0], [0, 2]]}
            ],
        }
        with self.assertRaises(ROIConfigError):
            self._load_temporary(document)

    @staticmethod
    def _load_temporary(document: dict) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "roi.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            load_roi_config(path)


if __name__ == "__main__":
    unittest.main()
