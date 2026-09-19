from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from core.errors import DataContractError
from experiments.cylinder.analysis import CylinderConfig, analyze_cylinder, write_cylinder_outputs


def config() -> CylinderConfig:
    return CylinderConfig(
        preset_name="test", preset_version="1", cylinder_radius=10, cylinder_height=30,
        left_paw_point="left_paw", right_paw_point="right_paw", wall_tolerance=1,
        max_outside_wall=1, contact_min_z=2, contact_max_z=28, min_contact_frames=3,
        max_interruption_frames=0, bilateral_window_frames=1, minimum_likelihood=0.9,
    )


def reconstructed_trial() -> pd.DataFrame:
    rows = []
    for frame in range(12):
        left_radius = 10 if frame in {1, 2, 3, 7, 8, 9} else 5
        right_radius = 10 if frame in {2, 3, 4, 10, 11} else 5
        row = {"trial_id": "trial_events", "animal_id": "mouse_events", "frame": frame, "time_s": frame/30, "fps": 30, "coordinate_unit": "mm"}
        for point, radius in (("left_paw", left_radius), ("right_paw", right_radius)):
            row.update({f"{point}_reconstructed_x": radius, f"{point}_reconstructed_y": 0, f"{point}_reconstructed_z": 10, f"{point}_likelihood": 0.99, f"{point}_x": radius, f"{point}_y": 0, f"{point}_z": 10})
        rows.append(row)
    return pd.DataFrame(rows)


class CylinderAnalysisTests(unittest.TestCase):
    def test_bilateral_pairing_and_weighted_metrics(self):
        result = analyze_cylinder(reconstructed_trial(), config())
        self.assertEqual(result.summary["left_touch_events"], 1)
        self.assertEqual(result.summary["right_touch_events"], 0)
        self.assertEqual(result.summary["bilateral_touch_events"], 1)
        self.assertEqual(result.summary["total_effective_events"], 2)
        self.assertAlmostEqual(result.summary["left_usage_proportion"], 0.75)
        self.assertAlmostEqual(result.summary["laterality_index"], -0.5)
        self.assertIn("shorter_than_min_contact_frames", set(result.event_audit["exclusion_reason"]))

    def test_only_reconstructed_coordinates_are_accepted(self):
        data = reconstructed_trial().drop(columns=["left_paw_reconstructed_x"])
        with self.assertRaisesRegex(DataContractError, "重建坐标列"):
            analyze_cylinder(data, config())

    def test_low_likelihood_excludes_candidate(self):
        data = reconstructed_trial(); data.loc[1:3, "left_paw_likelihood"] = 0.1
        result = analyze_cylinder(data, config())
        self.assertEqual(result.summary["bilateral_touch_events"], 0)
        self.assertIn("low_likelihood", set(result.frame_quality["quality_reason"]))

    def test_outputs_are_auditable_and_not_overwritten(self):
        result = analyze_cylinder(reconstructed_trial(), config())
        with tempfile.TemporaryDirectory() as temporary:
            paths = write_cylinder_outputs(temporary, result)
            self.assertTrue(all(path.exists() for path in paths.values()))
            summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
            self.assertEqual(summary["config"]["preset_name"], "test")
            with self.assertRaisesRegex(FileExistsError, "拒绝覆盖"):
                write_cylinder_outputs(temporary, result)


if __name__ == "__main__":
    unittest.main()
