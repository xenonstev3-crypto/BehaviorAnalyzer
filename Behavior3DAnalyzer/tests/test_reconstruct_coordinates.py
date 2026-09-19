from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from core.errors import DataContractError, ReconstructionError
from core.reconstruct_coordinates import reconstruction_from_environment_markers, reconstruction_from_metadata, reconstruction_from_perimeter_points, write_reconstruction_outputs


def synthetic_trial(unit: str = "mm") -> tuple[pd.DataFrame, dict]:
    axes = np.array([[0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    origin = np.array([11.0, -7.0, 5.0])
    def raw(point): return np.asarray(point) @ axes + origin
    points = {
        "cylinder_bottom_center": raw([0, 0, 0]), "cylinder_top_center": raw([0, 0, 20]),
        "x_axis_marker": raw([10, 0, 0]), "perimeter_a": raw([10, 0, 0]),
        "perimeter_b": raw([0, 10, 0]), "perimeter_c": raw([-10, 0, 0]),
        "left_paw_tip": raw([9, 1, 8]), "right_paw_tip": raw([-2, 4, 7]),
    }
    rows = []
    for frame in range(4):
        row = {"trial_id": "synthetic_01", "animal_id": "mouse_a", "frame": frame, "time_s": frame / 30, "fps": 30, "coordinate_unit": unit}
        for name, value in points.items():
            jitter = np.zeros(3) if name.startswith("cylinder") or name in {"x_axis_marker", "perimeter_a", "perimeter_b", "perimeter_c"} else np.array([0, 0, frame * 0.1]) @ axes
            for axis, coordinate in zip("xyz", value + jitter): row[f"{name}_{axis}"] = coordinate
        row["left_paw_tip_likelihood"] = 0.99
        rows.append(row)
    return pd.DataFrame(rows), {"bottom_center_raw": origin.tolist(), "top_center_raw": raw([0, 0, 20]).tolist(), "x_reference_raw": raw([10, 0, 0]).tolist(), "x_reference_is_point": True}


class ReconstructionTests(unittest.TestCase):
    def test_direct_metadata_recovers_known_coordinates(self):
        frame, metadata = synthetic_trial(); output, record = reconstruction_from_metadata(frame, metadata)
        np.testing.assert_allclose(output.loc[0, ["cylinder_bottom_center_reconstructed_x", "cylinder_bottom_center_reconstructed_y", "cylinder_bottom_center_reconstructed_z"]].to_numpy(dtype=float), [0, 0, 0], atol=1e-9)
        np.testing.assert_allclose(output.loc[0, ["cylinder_top_center_reconstructed_x", "cylinder_top_center_reconstructed_y", "cylinder_top_center_reconstructed_z"]].to_numpy(dtype=float), [0, 0, 20], atol=1e-9)
        self.assertAlmostEqual(float(output.loc[0, "left_paw_tip_reconstructed_x"]), 9.0); self.assertAlmostEqual(float(output.loc[0, "left_paw_tip_reconstructed_y"]), 1.0)
        self.assertEqual(record["reference_source"], "metadata_direct"); self.assertIn("left_paw_tip_likelihood", output.columns)

    def test_environment_markers_and_radius(self):
        frame, _ = synthetic_trial(); output, record = reconstruction_from_environment_markers(frame, max_marker_drift=0.01)
        self.assertAlmostEqual(float(np.hypot(output.loc[0, "perimeter_a_reconstructed_x"], output.loc[0, "perimeter_a_reconstructed_y"])), 10.0, places=8); self.assertEqual(record["quality_control"]["status"], "passed")

    def test_parallel_x_and_z_is_rejected(self):
        frame, metadata = synthetic_trial(); metadata["x_reference_raw"] = metadata["top_center_raw"]
        with self.assertRaisesRegex(ReconstructionError, "X 参考方向与 Z 轴"): reconstruction_from_metadata(frame, metadata)

    def test_missing_environment_marker_is_rejected(self):
        frame, _ = synthetic_trial(); frame = frame.drop(columns=["x_axis_marker_x"])
        with self.assertRaisesRegex(DataContractError, "x_axis_marker"): reconstruction_from_environment_markers(frame)

    def test_marker_drift_is_rejected(self):
        frame, _ = synthetic_trial(); frame.loc[3, "cylinder_top_center_x"] += 5
        with self.assertRaisesRegex(ReconstructionError, "漂移"): reconstruction_from_environment_markers(frame, max_marker_drift=0.1)

    def test_collinear_perimeter_markers_are_rejected(self):
        frame, _ = synthetic_trial()
        for axis in "xyz": frame[f"perimeter_c_{axis}"] = frame[f"perimeter_b_{axis}"] * 2 - frame[f"perimeter_a_{axis}"]
        with self.assertRaisesRegex(ReconstructionError, "共线"):
            reconstruction_from_perimeter_points(frame, perimeter_markers=["perimeter_a", "perimeter_b", "perimeter_c"], x_axis_marker="x_axis_marker", vertical_reference_raw=[0, 0, 1], expected_radius=10, max_plane_residual=0.01, max_circle_residual=0.01)

    def test_insufficient_perimeter_markers_are_rejected(self):
        frame, _ = synthetic_trial()
        with self.assertRaisesRegex(ReconstructionError, "至少需要三个"):
            reconstruction_from_perimeter_points(frame, perimeter_markers=["perimeter_a", "perimeter_b"], x_axis_marker="x_axis_marker", vertical_reference_raw=[0, 0, 1], expected_radius=10, max_plane_residual=0.01, max_circle_residual=0.01)

    def test_inconsistent_units_are_rejected(self):
        frame, metadata = synthetic_trial(); frame.loc[2, "coordinate_unit"] = "cm"
        with self.assertRaisesRegex(DataContractError, "coordinate_unit"): reconstruction_from_metadata(frame, metadata)

    def test_missing_body_coordinate_stays_missing(self):
        frame, metadata = synthetic_trial(); frame.loc[1, "left_paw_tip_x"] = np.nan
        output, _ = reconstruction_from_metadata(frame, metadata)
        self.assertTrue(np.isnan(output.loc[1, "left_paw_tip_reconstructed_x"]))
        self.assertTrue(np.isnan(output.loc[1, "left_paw_tip_reconstructed_y"]))

    def test_input_csv_is_never_overwritten(self):
        frame, metadata = synthetic_trial(); output, record = reconstruction_from_metadata(frame, metadata)
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.csv"; frame.to_csv(source, index=False); before = hashlib.sha256(source.read_bytes()).hexdigest()
            with self.assertRaisesRegex(DataContractError, "拒绝覆盖"): write_reconstruction_outputs(source, source, output, record)
            self.assertEqual(before, hashlib.sha256(source.read_bytes()).hexdigest())
            destination = Path(temporary) / "results" / "reconstructed.csv"; csv_path, json_path = write_reconstruction_outputs(source, destination, output, record)
            self.assertTrue(csv_path.exists() and json_path.exists()); self.assertEqual(before, hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["input_sha256"], before)


if __name__ == "__main__": unittest.main()
