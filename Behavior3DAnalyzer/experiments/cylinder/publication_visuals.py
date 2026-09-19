"""Cylinder 结果的投稿级静态图与三维关键点 MP4。

所有函数都由 GUI 传入用户已选择的结果目录；从不猜测或自行创建桌面输出路径。
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from .analysis import CylinderAnalysisResult


def _ensure_new(paths: list[Path]) -> None:
    exists = [str(path) for path in paths if path.exists()]
    if exists:
        raise FileExistsError("拒绝覆盖已有可视化文件：" + "；".join(exists))


def _xyz(data: pd.DataFrame, point: str) -> np.ndarray:
    columns = [f"{point}_reconstructed_{axis}" for axis in "xyz"]
    if not all(column in data.columns for column in columns):
        raise ValueError(f"无法绘制 {point}：缺少重建坐标列。")
    return data.loc[:, columns].apply(pd.to_numeric, errors="coerce").to_numpy(float)


def write_publication_figure(output_dir: str | Path, data: pd.DataFrame, result: CylinderAnalysisResult) -> dict[str, Path]:
    """输出 600 dpi PNG、矢量 PDF 和 SVG，适合后续排版编辑。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle

    directory = Path(output_dir)
    stem = directory / "figure1"
    targets = {"png": stem.with_suffix(".png"), "pdf": stem.with_suffix(".pdf"), "svg": stem.with_suffix(".svg")}
    _ensure_new(list(targets.values()))
    directory.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "Arial", "font.size": 8, "pdf.fonttype": 42, "ps.fonttype": 42})
    blue, orange, grey, black = "#0072B2", "#D55E00", "#D9D9D9", "#222222"
    left_name, right_name = result.config.left_paw_point, result.config.right_paw_point
    left, right = _xyz(data, left_name), _xyz(data, right_name)
    radius = float(result.config.cylinder_radius)
    figure, axes = plt.subplots(1, 2, figsize=(7.2, 3.25), constrained_layout=True)
    axis = axes[0]
    axis.add_patch(Circle((0, 0), radius, fill=False, linewidth=1.15, color=black))
    for points, color, label in ((left, blue, "Left paw"), (right, orange, "Right paw")):
        valid = np.isfinite(points[:, :2]).all(axis=1)
        axis.plot(points[valid, 0], points[valid, 1], color=color, alpha=.34, linewidth=.55, label=label)
    colors = {"left": blue, "right": orange, "bilateral": "#7A3DB8"}
    for _, event in result.events.iterrows():
        point = left if event["classification"] in {"left", "bilateral"} else right
        mask = (data["frame"].to_numpy() >= event["start_frame"]) & (data["frame"].to_numpy() <= event["end_frame"])
        axis.scatter(point[mask, 0], point[mask, 1], s=8, color=colors[str(event["classification"])], zorder=3)
    axis.scatter(0, 0, marker="+", s=55, linewidth=1.1, color=black, label="Cylinder centre")
    axis.set(xlim=(-radius * 1.16, radius * 1.16), ylim=(-radius * 1.16, radius * 1.16), xlabel="Reconstructed X (mm)", ylabel="Reconstructed Y (mm)", title="A  |  Paw trajectories and wall contacts")
    axis.set_aspect("equal"); axis.legend(frameon=False, loc="lower left", fontsize=7); axis.spines[["top", "right"]].set_visible(False)
    axis = axes[1]
    if result.config.only_during_rearing and result.config.rearing_point:
        z_column = f"{result.config.rearing_point}_reconstructed_z"
        if z_column in data.columns:
            active = pd.to_numeric(data[z_column], errors="coerce").to_numpy(float) >= float(result.config.rearing_min_z)
            starts = np.flatnonzero(active & np.r_[True, ~active[:-1]])
            ends = np.flatnonzero(active & np.r_[~active[1:], True])
            times = pd.to_numeric(data["time_s"], errors="coerce").to_numpy(float)
            for start, end in zip(starts, ends): axis.axvspan(times[start], times[end], color=grey, alpha=.6, linewidth=0)
    levels = {"left": 1, "right": 0, "bilateral": .5}
    for _, event in result.events.iterrows():
        label = str(event["classification"]); axis.plot([event["start_time_s"], event["end_time_s"]], [levels[label]] * 2, color=colors[label], linewidth=6, solid_capstyle="round")
    max_time = float(pd.to_numeric(data["time_s"], errors="coerce").max())
    axis.set(xlim=(0, max_time), ylim=(-.45, 1.45), yticks=[0, .5, 1], yticklabels=["Right paw", "Bilateral", "Left paw"], xlabel="Time (s)", title="B  |  Effective wall-touch events")
    axis.text(.02, .05, f"Left: {result.summary['left_touch_events']}  |  Right: {result.summary['right_touch_events']}  |  Bilateral: {result.summary['bilateral_touch_events']}", transform=axis.transAxes, fontsize=7, va="bottom", color=black)
    axis.spines[["top", "right"]].set_visible(False)
    figure.savefig(targets["png"], dpi=600, bbox_inches="tight", facecolor="white")
    figure.savefig(targets["pdf"], bbox_inches="tight", facecolor="white")
    figure.savefig(targets["svg"], bbox_inches="tight", facecolor="white")
    plt.close(figure)
    return targets


def write_3d_keypoint_video(output_dir: str | Path, data: pd.DataFrame, result: CylinderAnalysisResult, *, video_fps: int = 10) -> Path:
    """使用 Python 与 imageio-ffmpeg 输出 H.264 MP4；抽样以保持真实时间尺度。"""
    try:
        import imageio.v2 as imageio
    except ImportError as error:
        raise RuntimeError("三维 MP4 导出需要 imageio 与 imageio-ffmpeg。") from error
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    directory = Path(output_dir)
    target = directory / "keypoints_3d.mp4"
    _ensure_new([target]); directory.mkdir(parents=True, exist_ok=True)
    names = [result.config.left_paw_point, result.config.right_paw_point]
    for optional in ("nose_tip", "trunk_center"):
        if all(f"{optional}_reconstructed_{axis}" in data.columns for axis in "xyz"): names.append(optional)
    coordinates = {name: _xyz(data, name) for name in names}
    palette = {result.config.left_paw_point: "#0072B2", result.config.right_paw_point: "#D55E00", "nose_tip": "#CC79A7", "trunk_center": "#303030"}
    labels = {result.config.left_paw_point: "Left paw", result.config.right_paw_point: "Right paw", "nose_tip": "Nose", "trunk_center": "Trunk"}
    source_fps = float(pd.to_numeric(data["fps"], errors="coerce").iloc[0])
    step = max(1, math.ceil(source_fps / video_fps)); indices = range(0, len(data), step)
    radius, height = float(result.config.cylinder_radius), float(result.config.cylinder_height)
    plt.rcParams.update({"font.family": "Arial", "font.size": 8})
    figure = plt.figure(figsize=(6.4, 6.0), facecolor="white"); axis = figure.add_subplot(111, projection="3d")
    theta = np.linspace(0, 2 * np.pi, 72)
    axis.plot(radius * np.cos(theta), radius * np.sin(theta), np.zeros_like(theta), color="#303030", linewidth=1)
    axis.plot(radius * np.cos(theta), radius * np.sin(theta), np.full_like(theta, height), color="#303030", linewidth=.55, alpha=.45)
    for angle in np.linspace(0, 2 * np.pi, 8, endpoint=False): axis.plot([radius * math.cos(angle)] * 2, [radius * math.sin(angle)] * 2, [0, height], color="#B8B8B8", linewidth=.4, alpha=.45)
    for vector, color, text in (((45, 0, 0), "#CC3311", "X"), ((0, 45, 0), "#0072B2", "Y"), ((0, 0, 65), "#009E73", "Z")):
        axis.quiver(0, 0, 0, *vector, color=color, arrow_length_ratio=.12, linewidth=1.3)
        axis.text(*vector, text, color=color)
    artists = {name: axis.plot([], [], [], marker="o", linestyle="", markersize=5.7, color=palette.get(name, "#444444"), label=labels.get(name, name))[0] for name in names}
    skeleton = []
    if "trunk_center" in names:
        for name in [value for value in names if value != "trunk_center"]: skeleton.append((name, axis.plot([], [], [], color="#555555", linewidth=1.0)[0]))
    title = axis.text2D(.03, .94, "", transform=axis.transAxes, fontsize=9, weight="bold")
    axis.set(xlim=(-radius * 1.18, radius * 1.18), ylim=(-radius * 1.18, radius * 1.18), zlim=(0, height), xlabel="X (mm)", ylabel="Y (mm)", zlabel="Z (mm)")
    axis.set_box_aspect((1, 1, 1.2)); axis.view_init(elev=22, azim=-56); axis.legend(loc="upper right", frameon=False, fontsize=7)
    with imageio.get_writer(target, fps=video_fps, codec="libx264", quality=8, macro_block_size=1) as writer:
        for index in indices:
            current = {name: values[index] for name, values in coordinates.items()}
            for name, artist in artists.items():
                point = current[name]; artist.set_data_3d([point[0]], [point[1]], [point[2]])
            for name, line in skeleton:
                a, b = current["trunk_center"], current[name]; line.set_data_3d([a[0], b[0]], [a[1], b[1]], [a[2], b[2]])
            t = float(pd.to_numeric(data["time_s"], errors="coerce").iloc[index]); title.set_text(f"3D reconstructed keypoints | t = {t:.2f} s")
            figure.canvas.draw(); writer.append_data(np.asarray(figure.canvas.buffer_rgba())[:, :, :3])
    plt.close(figure)
    if not target.exists() or target.stat().st_size == 0: raise RuntimeError("三维 MP4 导出失败。")
    return target
