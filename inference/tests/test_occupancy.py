from __future__ import annotations

import unittest
from pathlib import Path

from inference.detect import PersonDetection
from inference.occupancy import (
    AVAILABLE,
    OCCUPIED,
    PARTIAL,
    OccupancyInputError,
    bottom_center,
    calculate_occupancy,
    occupancy_status,
)
from inference.roi import build_shapely_geometries, load_roi_config


ROOT = Path(__file__).resolve().parents[2]
ROI_PATH = ROOT / "inference" / "config" / "roi_config.json"


class OccupancyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_roi_config(ROI_PATH)
        self.geometries = build_shapely_geometries(self.config)

    def test_status_boundaries(self) -> None:
        self.assertEqual(occupancy_status(0, 2), AVAILABLE)
        self.assertEqual(occupancy_status(1, 2), PARTIAL)
        self.assertEqual(occupancy_status(2, 2), OCCUPIED)
        self.assertEqual(occupancy_status(5, 2), OCCUPIED)

    def test_bottom_center_uses_feet_of_person_box(self) -> None:
        self.assertEqual(bottom_center((2, 3, 6, 10)), (4.0, 10.0))

    def test_empty_frame_marks_all_tables_available(self) -> None:
        snapshot = calculate_occupancy(self.config, [], geometries=self.geometries)

        self.assertEqual(len(snapshot.meja), 4)
        self.assertTrue(all(table.terisi == 0 for table in snapshot.meja))
        self.assertTrue(all(table.status == AVAILABLE for table in snapshot.meja))

    def test_mock_rois_count_people_per_table(self) -> None:
        detections = [
            PersonDetection((2, 0, 4, 5), 0.9),  # table 1: one -> partial
            PersonDetection((18, 0, 20, 5), 0.9),  # table 2
            PersonDetection((21, 0, 22, 5), 0.9),  # table 2 -> occupied
            PersonDetection((2, 8, 4, 12), 0.9),  # table 3: one -> partial
            PersonDetection((18, 8, 20, 12), 0.9),  # table 4
            PersonDetection((21, 8, 23, 12), 0.9),  # table 4
            PersonDetection((24, 8, 26, 12), 0.9),  # table 4
            PersonDetection((27, 8, 29, 12), 0.9),  # table 4 -> occupied
        ]

        snapshot = calculate_occupancy(
            self.config, detections, geometries=self.geometries
        )
        by_number = {table.nomor_meja: table for table in snapshot.meja}

        self.assertEqual((by_number[1].terisi, by_number[1].status), (1, PARTIAL))
        self.assertEqual((by_number[2].terisi, by_number[2].status), (2, OCCUPIED))
        self.assertEqual((by_number[3].terisi, by_number[3].status), (1, PARTIAL))
        self.assertEqual((by_number[4].terisi, by_number[4].status), (4, OCCUPIED))

    def test_non_person_detection_is_ignored(self) -> None:
        detection = PersonDetection((2, 0, 4, 5), 0.9, class_id=56)

        snapshot = calculate_occupancy(
            self.config, [detection], geometries=self.geometries
        )

        self.assertTrue(all(table.terisi == 0 for table in snapshot.meja))

    def test_invalid_bbox_is_rejected(self) -> None:
        with self.assertRaises(OccupancyInputError):
            bottom_center((1, 2, 0, 3))


if __name__ == "__main__":
    unittest.main()
