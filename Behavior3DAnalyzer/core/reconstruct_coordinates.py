"""以圆桶固定参考建立右手坐标系；绝不由动物位置猜测圆桶位置。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .errors import DataContractError, ReconstructionError
from .input_validation import discover_points, require_xyz, validate_wide_csv

SOFTWARE_VERSION = "0.1.0-stage1"
EPSILON = 1e-10


def _vector(value: Any, label: str) -> np.ndarray:
    vector = np.asarray(value, dtype=float)
    if vector.shape != (3,) or not np.isfinite(vector).all():
        raise ReconstructionError(f"{label} 必须是三个有限数值组成的 [x, y, z]。")
    return vector


def _normalize(vector: np.ndarray, label: str) -> np.ndarray:
    length = float(np.linalg.norm(vector))
    if not np.isfinite(length) or length < EPSILON:
        raise ReconstructionError(f"{label} 长度过小，无法定义方向。")
    return vector / length


def build_right_handed_transform(
    bottom_center_raw: Any,
    vertical_reference_raw: Any,
    x_reference_raw: Any,
    *,
    vertical_reference_is_point: bool = False,
    x_reference_is_point: bool = False,
    flip_x: bool = False,
    flip_y: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """按项目数学定义建立 new = (raw - origin) @ rotation.T。

    翻转 X 时也翻转 Y，保持右手系；单独翻转 Y 等价于同时翻转 X/Y。
    """
    origin = _vector(bottom_center_raw, "bottom_center_raw")
    vertical = _vector(vertical_reference_raw, "vertical_reference_raw")
    x_reference = _vector(x_reference_raw, "x_reference_raw")
    if vertical_reference_is_point:
        vertical = vertical - origin
    if x_reference_is_point:
        x_reference = x_reference - origin

    z_hat = _normalize(vertical, "Z 参考向量")
    x_projected = x_reference - float(np.dot(x_reference, z_hat)) * z_hat
    if float(np.linalg.norm(x_projected)) < EPSILON:
        raise ReconstructionError("X 参考方向与 Z 轴近似平行，无法建立坐标系。")
    x_hat = _normalize(x_projected, "投影后的 X 参考向量")
    y_hat = _normalize(np.cross(z_hat, x_hat), "右手 Y 轴")

    # 任何一个用户方向翻转均改变底面两个轴，仍使 X × Y = Z。
    if flip_x ^ flip_y:
        x_hat = -x_hat
        y_hat = -y_hat
    rotation = np.vstack((x_hat, y_hat, z_hat))
    return origin, rotation


def reconstruct_coordinates(
    df: pd.DataFrame,
    *,
    bottom_center_raw: Any,
    vertical_reference_raw: Any,
    x_reference_raw: Any,
    reference_source: str,
    vertical_reference_is_point: bool = False,
    x_reference_is_point: bool = False,
    flip_x: bool = False,
    flip_y: bool = False,
    quality_control: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """转换所有完整 XYZ 点，原有列（含质量列）逐列保留且不伪造缺失。"""
    contract = validate_wide_csv(df)
    origin, rotation = build_right_handed_transform(
        bottom_center_raw,
        vertical_reference_raw,
        x_reference_raw,
        vertical_reference_is_point=vertical_reference_is_point,
        x_reference_is_point=x_reference_is_point,
        flip_x=flip_x,
        flip_y=flip_y,
    )
    output = df.copy(deep=True)
    for point in discover_points(df.columns):
        raw = require_xyz(df, point)
        transformed = (raw - origin) @ rotation.T
        output[f"{point}_reconstructed_x"] = transformed[:, 0]
        output[f"{point}_reconstructed_y"] = transformed[:, 1]
        output[f"{point}_reconstructed_z"] = transformed[:, 2]

    record = {
        "schema_version": "1.0",
        "software_version": SOFTWARE_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "transform_type": "session-level",
        "reference_source": reference_source,
        "coordinate_unit": contract["coordinate_unit"],
        "trial_id": str(df["trial_id"].iloc[0]),
        "animal_id": str(df["animal_id"].iloc[0]),
        "translation_origin_raw": origin.tolist(),
        "rotation_matrix_raw_to_reconstructed": rotation.tolist(),
        "axis_definition": "new = [dot(p-c,x_hat), dot(p-c,y_hat), dot(p-c,z_hat)]",
        "flip_x": flip_x,
        "flip_y": flip_y,
        "points_transformed": discover_points(df.columns),
        "quality_control": quality_control or {},
    }
    return output, record


def reconstruction_from_metadata(df: pd.DataFrame, metadata: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """方式 A：从显式 metadata 读取圆心、Z 与 X 参考。"""
    for key in ("bottom_center_raw", "x_reference_raw"):
        if key not in metadata:
            raise ReconstructionError(f"metadata 缺少 {key}，不能重建。")
    if "vertical_reference_raw" in metadata:
        vertical = metadata["vertical_reference_raw"]
        vertical_is_point = bool(metadata.get("vertical_reference_is_point", False))
    elif "top_center_raw" in metadata:
        vertical = metadata["top_center_raw"]
        vertical_is_point = True
    else:
        raise ReconstructionError("metadata 必须提供 vertical_reference_raw 或 top_center_raw。")
    return reconstruct_coordinates(
        df,
        bottom_center_raw=metadata["bottom_center_raw"],
        vertical_reference_raw=vertical,
        x_reference_raw=metadata["x_reference_raw"],
        reference_source="metadata_direct",
        vertical_reference_is_point=vertical_is_point,
        x_reference_is_point=bool(metadata.get("x_reference_is_point", False)),
        flip_x=bool(metadata.get("flip_x", False)),
        flip_y=bool(metadata.get("flip_y", False)),
        quality_control={"status": "passed", "method": "metadata_direct"},
    )


def _stationary_marker(df: pd.DataFrame, name: str, max_drift: float) -> tuple[np.ndarray, dict[str, float]]:
    values = require_xyz(df, name)
    valid = values[np.isfinite(values).all(axis=1)]
    if not len(valid):
        raise ReconstructionError(f"固定标记点 {name} 没有任何完整坐标。")
    median = np.median(valid, axis=0)
    max_observed_drift = float(np.max(np.linalg.norm(valid - median, axis=1)))
    if max_observed_drift > max_drift:
        raise ReconstructionError(
            f"固定标记点 {name} 漂移 {max_observed_drift:.6g}，超过允许值 {max_drift:.6g}；"
            "请检查标记质量或改用 frame-level 变换。"
        )
    return median, {"valid_frames": int(len(valid)), "max_drift": max_observed_drift}


def reconstruction_from_environment_markers(
    df: pd.DataFrame,
    *,
    bottom_center_marker: str = "cylinder_bottom_center",
    top_center_marker: str = "cylinder_top_center",
    x_axis_marker: str = "x_axis_marker",
    max_marker_drift: float = 1.0,
    flip_x: bool = False,
    flip_y: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """方式 B：固定环境标记的 session-level 变换；逐帧漂移超限即停止。"""
    if max_marker_drift < 0:
        raise ReconstructionError("max_marker_drift 不得为负数。")
    bottom, bottom_qc = _stationary_marker(df, bottom_center_marker, max_marker_drift)
    top, top_qc = _stationary_marker(df, top_center_marker, max_marker_drift)
    x_marker, x_qc = _stationary_marker(df, x_axis_marker, max_marker_drift)
    return reconstruct_coordinates(
        df,
        bottom_center_raw=bottom,
        vertical_reference_raw=top,
        x_reference_raw=x_marker,
        reference_source="environment_markers_session_level",
        vertical_reference_is_point=True,
        x_reference_is_point=True,
        flip_x=flip_x,
        flip_y=flip_y,
        quality_control={
            "status": "passed",
            "method": "environment_markers_session_level",
            "max_allowed_marker_drift": max_marker_drift,
            "markers": {bottom_center_marker: bottom_qc, top_center_marker: top_qc, x_axis_marker: x_qc},
        },
    )


def reconstruction_from_perimeter_points(
    df: pd.DataFrame,
    *,
    perimeter_markers: Iterable[str],
    x_axis_marker: str,
    vertical_reference_raw: Any,
    expected_radius: float,
    max_plane_residual: float,
    max_circle_residual: float,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """方式 C：拟合底面平面与圆；至少三个不共线底面圆周固定点。"""
    names = list(perimeter_markers)
    if len(names) < 3:
        raise ReconstructionError("多点拟合至少需要三个不共线的底面圆周固定点。")
    if expected_radius <= 0:
        raise ReconstructionError("expected_radius 必须为正数。")
    marker_positions = []
    for name in names:
        position, _ = _stationary_marker(df, name, float("inf"))
        marker_positions.append(position)
    points = np.asarray(marker_positions)
    centroid = points.mean(axis=0)
    _, singular, vh = np.linalg.svd(points - centroid, full_matrices=False)
    if len(singular) < 3 or singular[-2] < EPSILON:
        raise ReconstructionError("底面圆周点共线或几何退化，无法拟合底面平面。")
    z_hat = _normalize(vh[-1], "拟合底面法向量")
    vertical_hint = _normalize(_vector(vertical_reference_raw, "vertical_reference_raw"), "Z 方向参考")
    # 底面平面法向量有正负二义性；必须依赖明确的向上参考来选定 +Z。
    if abs(float(np.dot(z_hat, vertical_hint))) < 0.95:
        raise ReconstructionError("提供的 Z 方向参考不垂直于拟合底面，无法确认圆桶 +Z 方向。")
    if float(np.dot(z_hat, vertical_hint)) < 0:
        z_hat = -z_hat
    plane_residual = float(np.max(np.abs((points - centroid) @ z_hat)))
    if plane_residual > max_plane_residual:
        raise ReconstructionError(f"底面平面拟合残差 {plane_residual:.6g} 超过门槛 {max_plane_residual:.6g}。")

    # 在拟合平面内用线性最小二乘拟合圆心。
    e1 = _normalize(points[1] - points[0], "圆周点方向")
    e1 = _normalize(e1 - np.dot(e1, z_hat) * z_hat, "底面平面方向")
    e2 = np.cross(z_hat, e1)
    planar = np.column_stack(((points - centroid) @ e1, (points - centroid) @ e2))
    system = np.column_stack((2 * planar[:, 0], 2 * planar[:, 1], np.ones(len(planar))))
    rhs = np.sum(planar**2, axis=1)
    solution, _, rank, _ = np.linalg.lstsq(system, rhs, rcond=None)
    if rank < 3:
        raise ReconstructionError("圆周点不足以稳定拟合圆心。")
    center_2d = solution[:2]
    fitted_radius = float(np.sqrt(solution[2] + np.dot(center_2d, center_2d)))
    center = centroid + center_2d[0] * e1 + center_2d[1] * e2
    circle_residual = float(np.max(np.abs(np.linalg.norm(planar - center_2d, axis=1) - fitted_radius)))
    if circle_residual > max_circle_residual:
        raise ReconstructionError(f"圆拟合残差 {circle_residual:.6g} 超过门槛 {max_circle_residual:.6g}。")
    if abs(fitted_radius - expected_radius) > max_circle_residual:
        raise ReconstructionError(
            f"拟合半径 {fitted_radius:.6g} 与声明半径 {expected_radius:.6g} 不一致，超过门槛 {max_circle_residual:.6g}。"
        )
    x_marker, _ = _stationary_marker(df, x_axis_marker, float("inf"))
    output, record = reconstruct_coordinates(
        df,
        bottom_center_raw=center,
        vertical_reference_raw=z_hat,
        x_reference_raw=x_marker,
        reference_source="perimeter_points_fit",
        x_reference_is_point=True,
        quality_control={
            "status": "passed",
            "method": "perimeter_points_fit",
            "plane_residual": plane_residual,
            "circle_residual": circle_residual,
            "fitted_radius": fitted_radius,
            "expected_radius": expected_radius,
        },
    )
    return output, record


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_reconstruction_outputs(
    input_csv: str | Path,
    output_csv: str | Path,
    transformed: pd.DataFrame,
    transform_record: dict[str, Any],
    *,
    record_path: str | Path | None = None,
) -> tuple[Path, Path]:
    """写入新的 CSV/JSON；明确拒绝覆盖原始输入。"""
    source = Path(input_csv).resolve()
    destination = Path(output_csv).resolve()
    if source == destination:
        raise DataContractError("拒绝覆盖原始 CSV：输出路径必须与输入路径不同。")
    if destination.exists():
        raise FileExistsError(f"输出文件已存在，拒绝覆盖：{destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    transformed.to_csv(destination, index=False, encoding="utf-8")
    record_path = Path(record_path).resolve() if record_path is not None else destination.with_name(destination.stem + "_transform_record.json")
    if record_path.exists():
        raise FileExistsError(f"变换记录已存在，拒绝覆盖：{record_path}")
    record = dict(transform_record)
    record["input_csv"] = str(source)
    record["input_sha256"] = _sha256(source)
    record["output_csv"] = str(destination)
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination, record_path
