"""Cylinder test 的可审计事件分析；只接受重建后的坐标。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from core.errors import DataContractError

ANALYSIS_VERSION = "0.2.0-stage3"


@dataclass(frozen=True)
class CylinderConfig:
    preset_name: str
    preset_version: str
    cylinder_radius: float
    cylinder_height: float
    left_paw_point: str
    right_paw_point: str
    wall_tolerance: float
    max_outside_wall: float
    contact_min_z: float
    contact_max_z: float
    min_contact_frames: int
    max_interruption_frames: int
    bilateral_window_frames: int
    minimum_likelihood: float | None = None
    maximum_error: float | None = None
    only_during_rearing: bool = False
    rearing_point: str | None = None
    rearing_min_z: float | None = None
    max_analysis_duration_s: float | None = None
    max_effective_events: int | None = None
    bilateral_weight_per_side: float = 0.5
    laterality_formula: str = "(right_weighted-left_weighted)/(right_weighted+left_weighted)"

    @classmethod
    def from_mapping(cls, values: dict[str, Any]) -> "CylinderConfig":
        allowed = cls.__dataclass_fields__
        return cls(**{key: value for key, value in values.items() if key in allowed})

    def validate(self) -> None:
        if self.cylinder_radius <= 0 or self.cylinder_height <= 0:
            raise DataContractError("圆桶半径和高度必须为正数。")
        if self.wall_tolerance < 0 or self.max_outside_wall < 0:
            raise DataContractError("触壁距离门槛不得为负数。")
        if self.contact_min_z < 0 or self.contact_max_z <= self.contact_min_z:
            raise DataContractError("触壁高度范围无效。")
        if self.min_contact_frames < 1 or self.max_interruption_frames < 0 or self.bilateral_window_frames < 0:
            raise DataContractError("事件帧数参数无效。")
        if not 0 <= self.bilateral_weight_per_side <= 1:
            raise DataContractError("双侧触壁的单侧权重必须介于 0 和 1。")
        if self.only_during_rearing and (not self.rearing_point or self.rearing_min_z is None):
            raise DataContractError("仅计入 rearing 时，必须指定 rearing_point 和 rearing_min_z。")


@dataclass
class CylinderAnalysisResult:
    summary: dict[str, Any]
    events: pd.DataFrame
    event_audit: pd.DataFrame
    frame_quality: pd.DataFrame
    config: CylinderConfig


def load_literature_common_preset() -> CylinderConfig:
    path = Path(__file__).resolve().parents[2] / "presets" / "cylinder_literature_common_v1.json"
    return CylinderConfig.from_mapping(json.loads(path.read_text(encoding="utf-8")))


def _columns(point: str) -> list[str]:
    return [f"{point}_reconstructed_{axis}" for axis in "xyz"]


def _validate(df: pd.DataFrame, config: CylinderConfig) -> tuple[float, pd.DataFrame]:
    base = ["trial_id", "animal_id", "frame", "time_s", "fps", "coordinate_unit"]
    missing = [column for column in base if column not in df.columns]
    if missing: raise DataContractError("重建坐标 CSV 缺少列：" + "、".join(missing))
    if df.empty or df["trial_id"].nunique(dropna=True) != 1: raise DataContractError("一次 cylinder 分析只接受一个非空 trial。")
    fps = pd.to_numeric(df["fps"], errors="coerce")
    if fps.isna().any() or (fps <= 0).any() or fps.nunique() != 1: raise DataContractError("fps 必须为整个 trial 一致的正数。")
    for point in [config.left_paw_point, config.right_paw_point] + ([str(config.rearing_point)] if config.only_during_rearing else []):
        missing = [column for column in _columns(point) if column not in df.columns]
        if missing: raise DataContractError(f"{point} 缺少重建坐标列：" + "、".join(missing))
    return float(fps.iloc[0]), df.copy(deep=True)


def _frame_quality(df: pd.DataFrame, point: str, cfg: CylinderConfig, rearing: np.ndarray) -> pd.DataFrame:
    xyz = df.loc[:, _columns(point)].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    radial = np.hypot(xyz[:, 0], xyz[:, 1]); reasons = np.full(len(df), "", dtype=object)
    valid = np.isfinite(xyz).all(axis=1); reasons[~valid] = "missing_coordinate"
    likelihood_col = f"{point}_likelihood"
    if cfg.minimum_likelihood is not None and likelihood_col in df.columns:
        likelihood = pd.to_numeric(df[likelihood_col], errors="coerce").to_numpy(float); bad = ~np.isfinite(likelihood) | (likelihood < cfg.minimum_likelihood)
        reasons[bad] = np.where(reasons[bad] == "", "low_likelihood", reasons[bad] + ";low_likelihood"); valid &= ~bad
    error_col = f"{point}_error"
    if cfg.maximum_error is not None and error_col in df.columns:
        error = pd.to_numeric(df[error_col], errors="coerce").to_numpy(float); bad = ~np.isfinite(error) | (error > cfg.maximum_error)
        reasons[bad] = np.where(reasons[bad] == "", "high_or_missing_error", reasons[bad] + ";high_or_missing_error"); valid &= ~bad
    height = (xyz[:, 2] >= cfg.contact_min_z) & (xyz[:, 2] <= cfg.contact_max_z)
    wall_band = (radial >= cfg.cylinder_radius - cfg.wall_tolerance) & (radial <= cfg.cylinder_radius + cfg.max_outside_wall)
    candidate = valid & height & wall_band & rearing
    return pd.DataFrame({"frame": df["frame"].to_numpy(), "time_s": df["time_s"].to_numpy(), "point": point, "x": xyz[:, 0], "y": xyz[:, 1], "z": xyz[:, 2], "radial_distance": radial, "wall_distance_signed": cfg.cylinder_radius-radial, "coordinate_quality_pass": valid, "height_pass": height, "rearing_pass": rearing, "candidate_touch": candidate, "quality_reason": reasons})


def _segments(candidate: np.ndarray, quality: np.ndarray, max_gap: int) -> list[tuple[int, int, int]]:
    results = []; index = 0
    while index < len(candidate):
        if not candidate[index]: index += 1; continue
        start = end = index; gaps = 0
        while end + 1 < len(candidate):
            next_index = end + 1
            if candidate[next_index]: end = next_index; continue
            gap_end = next_index
            while gap_end < len(candidate) and not candidate[gap_end] and quality[gap_end] and gap_end-next_index < max_gap: gap_end += 1
            if gap_end < len(candidate) and candidate[gap_end] and gap_end-next_index <= max_gap:
                gaps += gap_end-next_index; end = gap_end; continue
            break
        results.append((start, end, gaps)); index = end+1
    return results


def _event(qc: pd.DataFrame, start: int, end: int, gaps: int, fps: float, minimum: int) -> dict[str, Any]:
    segment = qc.iloc[start:end+1]; included = len(segment) >= minimum
    return {"point": str(segment["point"].iloc[0]), "start_index": start, "end_index": end, "start_frame": int(segment["frame"].iloc[0]), "end_frame": int(segment["frame"].iloc[-1]), "start_time_s": float(segment["time_s"].iloc[0]), "end_time_s": float(segment["time_s"].iloc[-1]), "duration_s": float(segment["time_s"].iloc[-1]-segment["time_s"].iloc[0]+1/fps), "duration_frames": int(len(segment)), "gap_filled_frames": gaps, "start_x": float(segment["x"].iloc[0]), "start_y": float(segment["y"].iloc[0]), "start_z": float(segment["z"].iloc[0]), "end_x": float(segment["x"].iloc[-1]), "end_y": float(segment["y"].iloc[-1]), "end_z": float(segment["z"].iloc[-1]), "mean_radial_distance": float(segment["radial_distance"].mean()), "mean_wall_distance_signed": float(segment["wall_distance_signed"].mean()), "quality_flag": "passed" if gaps == 0 else "short_valid_interruption_merged", "included": included, "exclusion_reason": "" if included else "shorter_than_min_contact_frames"}


def _single(event: dict[str, Any], side: str) -> dict[str, Any]:
    row = dict(event); row.update({"classification": side, "left_point": event["point"] if side == "left" else "", "right_point": event["point"] if side == "right" else ""}); return row


def _paired(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    start_frame, end_frame = min(left["start_frame"], right["start_frame"]), max(left["end_frame"], right["end_frame"])
    return {"classification": "bilateral", "left_point": left["point"], "right_point": right["point"], "point": "both", "start_index": min(left["start_index"], right["start_index"]), "end_index": max(left["end_index"], right["end_index"]), "start_frame": start_frame, "end_frame": end_frame, "start_time_s": min(left["start_time_s"], right["start_time_s"]), "end_time_s": max(left["end_time_s"], right["end_time_s"]), "duration_s": max(left["end_time_s"], right["end_time_s"])-min(left["start_time_s"], right["start_time_s"]), "duration_frames": end_frame-start_frame+1, "gap_filled_frames": left["gap_filled_frames"]+right["gap_filled_frames"], "mean_radial_distance": (left["mean_radial_distance"]+right["mean_radial_distance"])/2, "mean_wall_distance_signed": (left["mean_wall_distance_signed"]+right["mean_wall_distance_signed"])/2, "quality_flag": "passed" if not left["gap_filled_frames"]+right["gap_filled_frames"] else "short_valid_interruption_merged", "exclusion_reason": "", "left_start_x": left["start_x"], "left_start_y": left["start_y"], "left_start_z": left["start_z"], "left_end_x": left["end_x"], "left_end_y": left["end_y"], "left_end_z": left["end_z"], "right_start_x": right["start_x"], "right_start_y": right["start_y"], "right_start_z": right["start_z"], "right_end_x": right["end_x"], "right_end_y": right["end_y"], "right_end_z": right["end_z"]}


def _combine(left: list[dict[str, Any]], right: list[dict[str, Any]], window: int) -> list[dict[str, Any]]:
    results = []; used = set()
    for left_event in left:
        choices = [(abs(left_event["start_index"]-right_event["start_index"]), index, right_event) for index, right_event in enumerate(right) if index not in used and left_event["start_index"] <= right_event["end_index"]+window and right_event["start_index"] <= left_event["end_index"]+window]
        if choices:
            _, index, right_event = min(choices); used.add(index); results.append(_paired(left_event, right_event))
        else: results.append(_single(left_event, "left"))
    results.extend(_single(event, "right") for index, event in enumerate(right) if index not in used)
    return sorted(results, key=lambda event: (event["start_frame"], event["classification"]))


def analyze_cylinder(df: pd.DataFrame, config: CylinderConfig) -> CylinderAnalysisResult:
    config.validate(); fps, data = _validate(df, config)
    if config.max_analysis_duration_s is not None: data = data.loc[pd.to_numeric(data["time_s"], errors="coerce") <= config.max_analysis_duration_s].copy()
    if data.empty: raise DataContractError("最大分析时长筛选后没有帧。")
    if config.only_during_rearing:
        z = pd.to_numeric(data[f"{config.rearing_point}_reconstructed_z"], errors="coerce").to_numpy(float); rearing = np.isfinite(z) & (z >= float(config.rearing_min_z))
    else: rearing = np.ones(len(data), bool)
    qcs = {"left": _frame_quality(data, config.left_paw_point, config, rearing), "right": _frame_quality(data, config.right_paw_point, config, rearing)}
    accepted: dict[str, list[dict[str, Any]]] = {}; audit = []
    for side, qc in qcs.items():
        events = [_event(qc, start, end, gaps, fps, config.min_contact_frames) for start, end, gaps in _segments(qc["candidate_touch"].to_numpy(bool), qc["coordinate_quality_pass"].to_numpy(bool), config.max_interruption_frames)]
        for event in events: event["side"] = side
        audit.extend(events); accepted[side] = [event for event in events if event["included"]]
    events = _combine(accepted["left"], accepted["right"], config.bilateral_window_frames)
    if config.max_effective_events is not None: events = events[:config.max_effective_events]
    for index, event in enumerate(events, 1): event.update({"event_id": f"event_{index:04d}", "trial_id": str(data["trial_id"].iloc[0]), "animal_id": str(data["animal_id"].iloc[0])})
    events_df = pd.DataFrame(events); counts = events_df["classification"].value_counts().to_dict() if not events_df.empty else {}
    left, right, both = int(counts.get("left", 0)), int(counts.get("right", 0)), int(counts.get("bilateral", 0)); left_w = left+config.bilateral_weight_per_side*both; right_w = right+config.bilateral_weight_per_side*both; denominator = left_w+right_w
    summary = {"analysis_version": ANALYSIS_VERSION, "preset_name": config.preset_name, "preset_version": config.preset_version, "trial_id": str(data["trial_id"].iloc[0]), "animal_id": str(data["animal_id"].iloc[0]), "coordinate_unit": str(data["coordinate_unit"].iloc[0]), "fps": fps, "frames_analyzed": len(data), "left_touch_events": left, "right_touch_events": right, "bilateral_touch_events": both, "total_effective_events": len(events_df), "left_weighted_use": left_w, "right_weighted_use": right_w, "left_usage_proportion": left_w/denominator if denominator else None, "right_usage_proportion": right_w/denominator if denominator else None, "laterality_index": (right_w-left_w)/denominator if denominator else None, "laterality_formula": config.laterality_formula, "event_audit_rows": len(audit), "created_at_utc": datetime.now(timezone.utc).isoformat(), "config": asdict(config)}
    return CylinderAnalysisResult(summary, events_df, pd.DataFrame(audit), pd.concat(list(qcs.values()), ignore_index=True), config)


def write_cylinder_outputs(output_dir: str | Path, result: CylinderAnalysisResult, *, concise_names: bool = False) -> dict[str, Path]:
    directory = Path(output_dir); directory.mkdir(parents=True, exist_ok=True); trial = str(result.summary["trial_id"])
    paths = ({"events": directory/"events.csv", "event_audit": directory/"event_audit.csv", "frame_quality": directory/"frame_quality.csv", "summary": directory/"summary.json"}
             if concise_names else
             {"events": directory/f"events_{trial}.csv", "event_audit": directory/f"event_audit_{trial}.csv", "frame_quality": directory/f"frame_quality_{trial}.csv", "summary": directory/f"summary_{trial}.json"})
    existing = [str(path) for path in paths.values() if path.exists()]
    if existing: raise FileExistsError("拒绝覆盖已有分析输出："+"；".join(existing))
    result.events.to_csv(paths["events"], index=False, encoding="utf-8"); result.event_audit.to_csv(paths["event_audit"], index=False, encoding="utf-8"); result.frame_quality.to_csv(paths["frame_quality"], index=False, encoding="utf-8"); paths["summary"].write_text(json.dumps(result.summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return paths
