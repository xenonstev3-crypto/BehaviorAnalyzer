"""生成可用于完整 GUI 流程的合成 Cylinder CSV。"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


FIELDS = [
    "trial_id", "animal_id", "frame", "time_s", "fps", "coordinate_unit",
    "left_paw_tip_x", "left_paw_tip_y", "left_paw_tip_z", "left_paw_tip_likelihood",
    "right_paw_tip_x", "right_paw_tip_y", "right_paw_tip_z", "right_paw_tip_likelihood",
    "nose_tip_x", "nose_tip_y", "nose_tip_z", "nose_tip_likelihood",
    "cylinder_bottom_center_x", "cylinder_bottom_center_y", "cylinder_bottom_center_z",
    "cylinder_top_center_x", "cylinder_top_center_y", "cylinder_top_center_z",
    "x_axis_marker_x", "x_axis_marker_y", "x_axis_marker_z",
]


def paw(radius: float, z: float, likelihood: float = 0.99) -> dict[str, float]:
    return {"x": radius, "y": 0.0, "z": z, "likelihood": likelihood}


def make_rows() -> list[dict[str, object]]:
    rows = []
    # 预期事件：1 个双侧（10-16 帧），1 个左侧（35-39），1 个右侧（50-54）。
    for frame in range(90):
        left = paw(45, 50)
        right = paw(45, 50)
        if 10 <= frame <= 14: left = paw(100, 55)
        if 12 <= frame <= 16: right = paw(100, 55)
        if 35 <= frame <= 39: left = paw(100, 60)
        if 50 <= frame <= 54: right = paw(100, 60)
        # 一帧靠墙但低置信度：应出现在逐帧质量记录中，不应计为事件。
        if frame == 70: left = paw(100, 55, 0.20)
        row: dict[str, object] = {
            "trial_id": "desktop_full_workflow_001", "animal_id": "simulated_mouse_001",
            "frame": frame, "time_s": round(frame / 30, 6), "fps": 30,
            "coordinate_unit": "mm",
            "left_paw_tip_x": left["x"], "left_paw_tip_y": left["y"], "left_paw_tip_z": left["z"], "left_paw_tip_likelihood": left["likelihood"],
            "right_paw_tip_x": right["x"], "right_paw_tip_y": right["y"], "right_paw_tip_z": right["z"], "right_paw_tip_likelihood": right["likelihood"],
            "nose_tip_x": 20 + frame * 0.2, "nose_tip_y": 10, "nose_tip_z": 80, "nose_tip_likelihood": 0.99,
            "cylinder_bottom_center_x": 0, "cylinder_bottom_center_y": 0, "cylinder_bottom_center_z": 0,
            "cylinder_top_center_x": 0, "cylinder_top_center_y": 0, "cylinder_top_center_z": 300,
            "x_axis_marker_x": 100, "x_axis_marker_y": 0, "x_axis_marker_z": 0,
        }
        rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output
    if output.exists():
        raise FileExistsError(f"拒绝覆盖已有文件：{output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader(); writer.writerows(make_rows())
    print(output)


if __name__ == "__main__":
    main()
