"""生成 10 秒可复现 cylinder 模拟数据、论文风格图和三维关键点动画。

该脚本只新建输出目录，绝不覆盖 CSV 或既有分析结果。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import Circle
import numpy as np
import pandas as pd

from core.reconstruct_coordinates import reconstruction_from_environment_markers
from experiments.cylinder.analysis import CylinderConfig, analyze_cylinder, write_cylinder_outputs


FPS = 30
N_FRAMES = 300
RADIUS_MM = 100.0
HEIGHT_MM = 300.0
ORIGIN_RAW = np.array([200.0, -100.0, 50.0])
# Rows are the reconstructed X/Y/Z axes represented in the raw coordinate frame.
ROTATION = np.array([[0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
LEFT_EVENTS = [(25, 31), (115, 121), (205, 211)]
RIGHT_EVENTS = [(160, 166)]
REARING_EVENTS = [(20, 35), (65, 80), (110, 125), (155, 170), (200, 215), (245, 260)]

FIELDS = [
    "trial_id", "animal_id", "frame", "time_s", "fps", "coordinate_unit",
    "left_paw_tip_x", "left_paw_tip_y", "left_paw_tip_z", "left_paw_tip_likelihood", "left_paw_tip_error",
    "right_paw_tip_x", "right_paw_tip_y", "right_paw_tip_z", "right_paw_tip_likelihood", "right_paw_tip_error",
    "nose_tip_x", "nose_tip_y", "nose_tip_z", "nose_tip_likelihood",
    "trunk_center_x", "trunk_center_y", "trunk_center_z", "trunk_center_likelihood",
    "cylinder_bottom_center_x", "cylinder_bottom_center_y", "cylinder_bottom_center_z",
    "cylinder_top_center_x", "cylinder_top_center_y", "cylinder_top_center_z",
    "x_axis_marker_x", "x_axis_marker_y", "x_axis_marker_z",
    "simulated_rearing_truth", "simulated_touch_truth",
]


def in_intervals(frame: int, intervals: list[tuple[int, int]]) -> bool:
    return any(start <= frame <= end for start, end in intervals)


def raw(point: np.ndarray) -> np.ndarray:
    """Map cylinder coordinates into a deliberately offset/rotated raw frame."""
    return ORIGIN_RAW + point @ ROTATION


def point_row(prefix: str, point: np.ndarray, likelihood: float = 0.99, error: float | None = None) -> dict[str, float]:
    xyz = raw(point)
    values = {f"{prefix}_x": xyz[0], f"{prefix}_y": xyz[1], f"{prefix}_z": xyz[2], f"{prefix}_likelihood": likelihood}
    if error is not None:
        values[f"{prefix}_error"] = error
    return values


def generate_csv(destination: Path) -> Path:
    if destination.exists():
        raise FileExistsError(f"拒绝覆盖已有原始 CSV：{destination}")
    rng = np.random.default_rng(20260913)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for frame in range(N_FRAMES):
            time_s = frame / FPS
            rearing = in_intervals(frame, REARING_EVENTS)
            left_touch = in_intervals(frame, LEFT_EVENTS)
            right_touch = in_intervals(frame, RIGHT_EVENTS)
            # A smooth, non-contact posture with small measurement noise.
            trunk = np.array([11 * math.sin(frame / 27), 9 * math.cos(frame / 31), 76.0 if rearing else 40.0])
            nose = np.array([trunk[0] + 6, trunk[1] + 4, 165.0 if rearing else 82.0])
            left = np.array([-32 + 5 * math.sin(frame / 17), 20 + 6 * math.cos(frame / 23), 93.0 if rearing else 37.0])
            right = np.array([32 + 5 * math.sin(frame / 19), -20 + 6 * math.cos(frame / 21), 93.0 if rearing else 37.0])
            if left_touch:
                angle = 2.25 + 0.03 * math.sin(frame)
                left = np.array([RADIUS_MM * math.cos(angle), RADIUS_MM * math.sin(angle), 97.0])
            if right_touch:
                angle = -0.72 + 0.03 * math.sin(frame)
                right = np.array([RADIUS_MM * math.cos(angle), RADIUS_MM * math.sin(angle), 98.0])
            left += rng.normal(0, 0.35, 3)
            right += rng.normal(0, 0.35, 3)
            bottom = raw(np.array([0.0, 0.0, 0.0]))
            top = raw(np.array([0.0, 0.0, HEIGHT_MM]))
            x_marker = raw(np.array([RADIUS_MM, 0.0, 0.0]))
            row: dict[str, object] = {
                "trial_id": "demo_10s_left3_right1_rearing6", "animal_id": "simulated_mouse_10s_001",
                "frame": frame, "time_s": round(time_s, 6), "fps": FPS, "coordinate_unit": "mm",
                "cylinder_bottom_center_x": bottom[0], "cylinder_bottom_center_y": bottom[1], "cylinder_bottom_center_z": bottom[2],
                "cylinder_top_center_x": top[0], "cylinder_top_center_y": top[1], "cylinder_top_center_z": top[2],
                "x_axis_marker_x": x_marker[0], "x_axis_marker_y": x_marker[1], "x_axis_marker_z": x_marker[2],
                "simulated_rearing_truth": int(rearing),
                "simulated_touch_truth": "left" if left_touch else ("right" if right_touch else "none"),
            }
            row.update(point_row("left_paw_tip", left, error=0.7))
            row.update(point_row("right_paw_tip", right, error=0.7))
            row.update(point_row("nose_tip", nose))
            row.update(point_row("trunk_center", trunk))
            writer.writerow(row)
    return destination


def settings() -> CylinderConfig:
    return CylinderConfig(
        preset_name="10 秒演示配置（仅作模拟数据真值核对）", preset_version="1.0",
        cylinder_radius=RADIUS_MM, cylinder_height=HEIGHT_MM,
        left_paw_point="left_paw_tip", right_paw_point="right_paw_tip",
        wall_tolerance=5.0, max_outside_wall=5.0, contact_min_z=20.0, contact_max_z=280.0,
        min_contact_frames=3, max_interruption_frames=0, bilateral_window_frames=2,
        minimum_likelihood=0.9, maximum_error=None,
        only_during_rearing=True, rearing_point="nose_tip", rearing_min_z=140.0,
    )


def journal_figure(reconstructed: pd.DataFrame, result, destination: Path) -> None:
    """Make a clean, colour-blind-aware, 600 dpi two-panel figure."""
    plt.rcParams.update({"font.family": "Arial", "font.size": 8, "pdf.fonttype": 42, "ps.fonttype": 42})
    blue, red, gray, charcoal = "#0072B2", "#D55E00", "#B8B8B8", "#222222"
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2), constrained_layout=True)
    ax = axes[0]
    ax.add_patch(Circle((0, 0), RADIUS_MM, fill=False, linewidth=1.2, color=charcoal))
    ax.plot(reconstructed["left_paw_tip_reconstructed_x"], reconstructed["left_paw_tip_reconstructed_y"], color=blue, alpha=.35, linewidth=.55)
    ax.plot(reconstructed["right_paw_tip_reconstructed_x"], reconstructed["right_paw_tip_reconstructed_y"], color=red, alpha=.35, linewidth=.55)
    for _, event in result.events.iterrows():
        point = "left_paw_tip" if event["classification"] == "left" else "right_paw_tip"
        segment = reconstructed[(reconstructed["frame"] >= event["start_frame"]) & (reconstructed["frame"] <= event["end_frame"])]
        ax.scatter(segment[f"{point}_reconstructed_x"], segment[f"{point}_reconstructed_y"], color=blue if point.startswith("left") else red, s=9, zorder=3)
    ax.scatter(0, 0, marker="+", s=55, linewidth=1.1, color=charcoal, label="Cylinder centre")
    ax.set(xlim=(-115, 115), ylim=(-115, 115), xlabel="Reconstructed X (mm)", ylabel="Reconstructed Y (mm)", title="A  |  Paw trajectories and wall contacts")
    ax.set_aspect("equal"); ax.legend(frameon=False, loc="lower left", fontsize=7)
    ax.spines[["top", "right"]].set_visible(False)

    ax = axes[1]
    for start, end in REARING_EVENTS:
        ax.axvspan(start / FPS, end / FPS, color=gray, alpha=.35, linewidth=0)
    rows = {"left": 1, "right": 0}
    for _, event in result.events.iterrows():
        y = rows[event["classification"]]
        colour = blue if event["classification"] == "left" else red
        ax.plot([event["start_time_s"], event["end_time_s"]], [y, y], color=colour, linewidth=6, solid_capstyle="round")
    ax.set(xlim=(0, 10), ylim=(-.45, 1.45), yticks=[0, 1], yticklabels=["Right paw", "Left paw"], xlabel="Time (s)", title="B  |  Rearing epochs and effective touches")
    ax.spines[["top", "right"]].set_visible(False)
    ax.text(.02, .05, "Grey bands: rearing (n = 6)\nLeft: 3 events; Right: 1 event", transform=ax.transAxes, fontsize=7, va="bottom", color=charcoal)
    fig.savefig(destination.with_suffix(".png"), dpi=600, bbox_inches="tight", facecolor="white")
    fig.savefig(destination.with_suffix(".pdf"), bbox_inches="tight", facecolor="white")
    fig.savefig(destination.with_suffix(".svg"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


def animation_3d(reconstructed: pd.DataFrame, destination: Path) -> None:
    """Generate a 10 fps animated GIF with cylinder axes and an anatomical keypoint skeleton."""
    plt.rcParams.update({"font.family": "Arial", "font.size": 9})
    fig = plt.figure(figsize=(6.4, 6.0), facecolor="white")
    ax = fig.add_subplot(111, projection="3d")
    theta = np.linspace(0, 2 * np.pi, 64)
    ax.plot(RADIUS_MM * np.cos(theta), RADIUS_MM * np.sin(theta), np.zeros_like(theta), color="#303030", linewidth=1)
    ax.plot(RADIUS_MM * np.cos(theta), RADIUS_MM * np.sin(theta), np.full_like(theta, HEIGHT_MM), color="#303030", linewidth=.6, alpha=.45)
    for angle in np.linspace(0, 2 * np.pi, 8, endpoint=False):
        ax.plot([RADIUS_MM * math.cos(angle)] * 2, [RADIUS_MM * math.sin(angle)] * 2, [0, HEIGHT_MM], color="#B8B8B8", linewidth=.4, alpha=.4)
    ax.quiver(0, 0, 0, 45, 0, 0, color="#CC3311", arrow_length_ratio=.12, linewidth=1.4)
    ax.quiver(0, 0, 0, 0, 45, 0, color="#0072B2", arrow_length_ratio=.12, linewidth=1.4)
    ax.quiver(0, 0, 0, 0, 0, 65, color="#009E73", arrow_length_ratio=.12, linewidth=1.4)
    ax.text(48, 0, 0, "X", color="#CC3311"); ax.text(0, 48, 0, "Y", color="#0072B2"); ax.text(0, 0, 70, "Z", color="#009E73")
    points = {name: ax.plot([], [], [], marker="o", linestyle="", markersize=6, color=colour, label=label)[0] for name, colour, label in [
        ("left_paw_tip", "#0072B2", "Left paw"), ("right_paw_tip", "#D55E00", "Right paw"), ("nose_tip", "#CC79A7", "Nose"), ("trunk_center", "#303030", "Trunk"),
    ]}
    skeleton = [ax.plot([], [], [], color="#555555", linewidth=1.2)[0] for _ in range(3)]
    label = ax.text2D(.03, .94, "", transform=ax.transAxes, fontsize=10, weight="bold")
    ax.set(xlim=(-120, 120), ylim=(-120, 120), zlim=(0, HEIGHT_MM), xlabel="X (mm)", ylabel="Y (mm)", zlabel="Z (mm)")
    ax.view_init(elev=22, azim=-56); ax.set_box_aspect((1, 1, 1.2)); ax.legend(loc="upper right", frameon=False, fontsize=8)

    frame_indices = list(range(0, len(reconstructed), 3))
    def update(index: int):
        row = reconstructed.iloc[frame_indices[index]]
        coords = {}
        for name, artist in points.items():
            coord = np.array([row[f"{name}_reconstructed_x"], row[f"{name}_reconstructed_y"], row[f"{name}_reconstructed_z"]])
            coords[name] = coord; artist.set_data_3d([coord[0]], [coord[1]], [coord[2]])
        for line, pair in zip(skeleton, [("trunk_center", "nose_tip"), ("trunk_center", "left_paw_tip"), ("trunk_center", "right_paw_tip")]):
            a, b = coords[pair[0]], coords[pair[1]]; line.set_data_3d([a[0], b[0]], [a[1], b[1]], [a[2], b[2]])
        touch = row["simulated_touch_truth"]
        label.set_text(f"3D reconstructed keypoints | t = {row['time_s']:.1f} s | touch: {touch}")
        return [*points.values(), *skeleton, label]
    animation = FuncAnimation(fig, update, frames=len(frame_indices), interval=100, blit=False)
    animation.save(destination, writer=PillowWriter(fps=10), dpi=110)
    plt.close(fig)


def main() -> None:
    # 显式路径避免不同启动环境将 Path.home() 解释为非 Windows 用户目录。
    desktop = Path(r"C:\Users\33913\Desktop")
    csv_path = desktop / "Behavior3DAnalyzer_10s_Left3_Right1_Rearing6.csv"
    output = desktop / "Behavior3DAnalyzer_10s_demo_outputs"
    if output.exists():
        raise FileExistsError(f"拒绝覆盖已有输出目录：{output}")
    if not csv_path.exists():
        generate_csv(csv_path)
    output.mkdir()
    raw_df = pd.read_csv(csv_path)
    reconstructed, transform = reconstruction_from_environment_markers(raw_df, max_marker_drift=1.0)
    reconstructed_path = output / "reconstructed_10s_demo.csv"
    reconstructed.to_csv(reconstructed_path, index=False, encoding="utf-8")
    (output / "transform_record.json").write_text(json.dumps(transform, ensure_ascii=False, indent=2), encoding="utf-8")
    result = analyze_cylinder(reconstructed, settings())
    analysis_paths = write_cylinder_outputs(output, result)
    journal_figure(reconstructed, result, output / "Figure_1_Cylinder_behavior")
    animation_3d(reconstructed, output / "Video_1_3D_reconstructed_keypoints.gif")
    (output / "README.txt").write_text(
        "本目录由模拟数据自动生成；原始 CSV 位于桌面同级位置。\n"
        "预期真值：左爪 3 次、右爪 1 次、双侧 0 次、直立 6 次。\n"
        "Figure_1 为 600 dpi PNG，同时提供 PDF/SVG；Video_1 为 10 fps 动画 GIF。\n"
        f"分析汇总：{analysis_paths['summary'].name}\n", encoding="utf-8")
    print(json.dumps({"csv": str(csv_path), "output": str(output), "summary": result.summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
