"""生成含噪声、质量波动和多类触壁事件的 60 秒模拟 trial。"""

from __future__ import annotations

import argparse
import csv
import math
import random
from pathlib import Path


FIELDS = [
    "trial_id", "animal_id", "frame", "time_s", "fps", "coordinate_unit",
    "left_paw_tip_x", "left_paw_tip_y", "left_paw_tip_z", "left_paw_tip_likelihood", "left_paw_tip_error",
    "right_paw_tip_x", "right_paw_tip_y", "right_paw_tip_z", "right_paw_tip_likelihood", "right_paw_tip_error",
    "nose_tip_x", "nose_tip_y", "nose_tip_z", "nose_tip_likelihood",
    "trunk_center_x", "trunk_center_y", "trunk_center_z", "trunk_center_likelihood",
    "cylinder_bottom_center_x", "cylinder_bottom_center_y", "cylinder_bottom_center_z",
    "cylinder_top_center_x", "cylinder_top_center_y", "cylinder_top_center_z",
    "x_axis_marker_x", "x_axis_marker_y", "x_axis_marker_z",
]

LEFT_EVENTS = [(420, 434), (700, 716), (1350, 1370)]
RIGHT_EVENTS = [(540, 558), (1100, 1118), (1550, 1568)]
BILATERAL_EVENTS = [(180, 198), (950, 966)]
SHORT_FALSE_CONTACTS = {300, 301, 302, 1200, 1201}


def in_event(frame: int, events: list[tuple[int, int]]) -> bool:
    return any(start <= frame <= end for start, end in events)


def paw(frame: int, side: str, rng: random.Random) -> tuple[float, float, float, float, float]:
    events = LEFT_EVENTS if side == "left" else RIGHT_EVENTS
    contact = in_event(frame, events) or in_event(frame, BILATERAL_EVENTS) or (side == "left" and frame in SHORT_FALSE_CONTACTS)
    angle = 0.4 * math.sin(frame / 57.0) + (0 if side == "left" else math.pi)
    if contact:
        radius = 100 + rng.gauss(0, 1.1); z = 55 + 8 * math.sin(frame / 19.0)
    else:
        radius = 34 + 9 * math.sin(frame / 43.0 + (0 if side == "left" else 1)) + rng.gauss(0, 2.0); z = 32 + 5 * math.sin(frame / 31.0)
    likelihood = 0.99
    if (side == "left" and frame in {1200, 1201}) or (side == "right" and frame in {800, 801}): likelihood = 0.35
    error = 0.6 + abs(rng.gauss(0, 0.25))
    return radius * math.cos(angle), radius * math.sin(angle), z, likelihood, error


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("output", type=Path); args = parser.parse_args()
    if args.output.exists(): raise FileExistsError(f"拒绝覆盖已有文件：{args.output}")
    rng = random.Random(20260913); args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS); writer.writeheader()
        for frame in range(1800):
            left = paw(frame, "left", rng); right = paw(frame, "right", rng)
            drift_x = 0.15 * math.sin(frame / 120.0); drift_y = 0.12 * math.cos(frame / 95.0)
            row = {
                "trial_id": "desktop_complex_workflow_001", "animal_id": "simulated_mouse_complex_001", "frame": frame, "time_s": round(frame / 30, 6), "fps": 30, "coordinate_unit": "mm",
                "left_paw_tip_x": left[0], "left_paw_tip_y": left[1], "left_paw_tip_z": left[2], "left_paw_tip_likelihood": left[3], "left_paw_tip_error": left[4],
                "right_paw_tip_x": right[0], "right_paw_tip_y": right[1], "right_paw_tip_z": right[2], "right_paw_tip_likelihood": right[3], "right_paw_tip_error": right[4],
                "nose_tip_x": 18 + 10*math.sin(frame/80), "nose_tip_y": 15*math.cos(frame/100), "nose_tip_z": 92 + 6*math.sin(frame/35), "nose_tip_likelihood": 0.99,
                "trunk_center_x": 9*math.sin(frame/90), "trunk_center_y": 8*math.cos(frame/120), "trunk_center_z": 42, "trunk_center_likelihood": 0.99,
                "cylinder_bottom_center_x": drift_x, "cylinder_bottom_center_y": drift_y, "cylinder_bottom_center_z": 0,
                "cylinder_top_center_x": drift_x, "cylinder_top_center_y": drift_y, "cylinder_top_center_z": 300,
                "x_axis_marker_x": 100+drift_x, "x_axis_marker_y": drift_y, "x_axis_marker_z": 0,
            }
            writer.writerow(row)
    print(args.output)


if __name__ == "__main__": main()
