"""规范宽表 CSV 的非破坏性验证。"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from .errors import DataContractError

REQUIRED_TRIAL_COLUMNS = (
    "trial_id",
    "animal_id",
    "frame",
    "time_s",
    "fps",
    "coordinate_unit",
)


def discover_points(columns: Iterable[str]) -> list[str]:
    """返回同时拥有 x/y/z 三列的点名前缀。"""
    column_set = set(columns)
    prefixes = {name[:-2] for name in column_set if name.endswith("_x")}
    return sorted(
        prefix
        for prefix in prefixes
        if {f"{prefix}_x", f"{prefix}_y", f"{prefix}_z"}.issubset(column_set)
    )


def validate_wide_csv(df: pd.DataFrame, required_points: Iterable[str] = ()) -> dict:
    """验证一期宽表的最小可分析条件；不修改 DataFrame。"""
    missing = [column for column in REQUIRED_TRIAL_COLUMNS if column not in df.columns]
    if missing:
        raise DataContractError("CSV 缺少必需列：" + "、".join(missing))
    if df.empty:
        raise DataContractError("CSV 没有数据行。")

    if df["trial_id"].isna().any() or df["animal_id"].isna().any():
        raise DataContractError("trial_id 和 animal_id 不得为空。")
    if df["trial_id"].nunique(dropna=True) != 1:
        raise DataContractError("一期每个 CSV 只允许一个 trial_id；请拆分多 trial 文件。")
    units = df["coordinate_unit"].dropna().astype(str).str.strip().unique()
    if len(units) != 1 or not units[0]:
        raise DataContractError("coordinate_unit 必须在整个 trial 中填写同一种非空单位。")
    fps = pd.to_numeric(df["fps"], errors="coerce")
    if fps.isna().any() or (fps <= 0).any() or fps.nunique() != 1:
        raise DataContractError("fps 必须是整个 trial 中一致的正数。")
    frames = pd.to_numeric(df["frame"], errors="coerce")
    times = pd.to_numeric(df["time_s"], errors="coerce")
    if frames.isna().any() or times.isna().any():
        raise DataContractError("frame 和 time_s 必须为数值，且不得缺失。")
    if not frames.is_monotonic_increasing or not times.is_monotonic_increasing:
        raise DataContractError("frame 与 time_s 必须按时间非递减排序。")

    points = discover_points(df.columns)
    absent = [point for point in required_points if point not in points]
    if absent:
        raise DataContractError("缺少完整 XYZ 坐标列的点：" + "、".join(absent))
    if not points:
        raise DataContractError("未发现任何完整的 {point}_x/y/z 坐标组。")
    return {"point_names": points, "coordinate_unit": units[0], "fps": float(fps.iloc[0])}


def require_xyz(df: pd.DataFrame, point_name: str) -> np.ndarray:
    """安全提取一个点的 N×3 坐标，不填补缺失值。"""
    columns = [f"{point_name}_{axis}" for axis in "xyz"]
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise DataContractError(f"参考点 {point_name} 缺少列：" + "、".join(missing))
    return df.loc[:, columns].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
