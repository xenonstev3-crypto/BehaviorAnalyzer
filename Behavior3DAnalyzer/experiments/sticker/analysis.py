"""Auditable 3D sticker test analysis."""
from __future__ import annotations
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from core.errors import DataContractError
from core.input_validation import validate_wide_csv

@dataclass(frozen=True)
class StickerConfig:
    target_point: str = "nose_tip"
    effector_points: tuple[str, ...] = ("left_paw_tip", "right_paw_tip")
    contact_distance: float = 15.0
    min_contact_frames: int = 3
    smoothing_frames: int = 9
    cessation_drop_ratio: float = .3
    cessation_sustain_frames: int = 30
    minimum_likelihood: float | None = .9

@dataclass
class StickerAnalysisResult:
    summary: dict[str, Any]
    events: pd.DataFrame
    frame_quality: pd.DataFrame
    config: StickerConfig

def _cols(p): return [f"{p}_{a}" for a in "xyz"]
def _runs(v):
    return list(zip(np.flatnonzero(v & np.r_[True,~v[:-1]]),np.flatnonzero(v & np.r_[~v[1:],True])))
def analyze_sticker(df: pd.DataFrame, cfg: StickerConfig) -> StickerAnalysisResult:
    validate_wide_csv(df)
    if cfg.contact_distance<=0 or cfg.min_contact_frames<1 or not cfg.effector_points or cfg.target_point in cfg.effector_points: raise DataContractError("贴纸分析参数无效。")
    missing=[f"{p}_{a}" for p in (cfg.target_point,*cfg.effector_points) for a in "xyz" if f"{p}_{a}" not in df]
    if missing: raise DataContractError("缺少坐标列："+"、".join(missing))
    if df.trial_id.nunique()!=1: raise DataContractError("一次贴纸分析只接受一个 trial。")
    target=df[_cols(cfg.target_point)].apply(pd.to_numeric,errors="coerce").to_numpy(float); ds=[]; quality=np.isfinite(target).all(1)
    for p in cfg.effector_points:
        xyz=df[_cols(p)].apply(pd.to_numeric,errors="coerce").to_numpy(float); ds.append(np.linalg.norm(xyz-target,axis=1)); quality &= np.isfinite(xyz).all(1)
        if cfg.minimum_likelihood is not None and f"{p}_likelihood" in df: quality &= pd.to_numeric(df[f"{p}_likelihood"],errors="coerce").to_numpy(float)>=cfg.minimum_likelihood
    mat = np.column_stack(ds)
    # A frame may have every effector missing. Keep it as a failed-quality frame
    # rather than letting np.nanargmin raise and abort the complete trial.
    has_distance = np.isfinite(mat).any(axis=1)
    minimum = np.full(len(df), np.nan, dtype=float)
    minimum[has_distance] = np.nanmin(mat[has_distance], axis=1)
    nearest = np.full(len(df), None, dtype=object)
    nearest[has_distance] = np.asarray(cfg.effector_points, dtype=object)[
        np.nanargmin(mat[has_distance], axis=1)
    ]
    quality &= has_distance
    candidate = quality & (minimum <= cfg.contact_distance)
    fps=float(df.fps.iloc[0]); events=[]
    for n,(s,e) in enumerate(_runs(candidate),1):
        ok=e-s+1>=cfg.min_contact_frames; events.append({"event_id":f"contact_{n:03d}","start_frame":int(df.frame.iloc[s]),"end_frame":int(df.frame.iloc[e]),"start_time_s":float(df.time_s.iloc[s]),"end_time_s":float(df.time_s.iloc[e]),"duration_s":(e-s+1)/fps,"effector":str(nearest[s]),"min_distance":float(np.nanmin(minimum[s:e+1])),"included":ok,"exclusion_reason":"" if ok else "shorter_than_min_contact_frames"})
    accepted=[e for e in events if e["included"]]; contact=None if not accepted else int(np.where(df.frame.to_numpy()==accepted[0]["start_frame"])[0][0]); intensity=1/np.maximum(minimum,1e-6); smooth=pd.Series(intensity).rolling(cfg.smoothing_frames,center=True,min_periods=1).mean().to_numpy(); cessation=None
    if contact is not None:
        peak=int(np.argmax(smooth[contact:])+contact); low=smooth<smooth[peak]*cfg.cessation_drop_ratio
        for s,e in _runs(low):
            if s>=peak and e-s+1>=cfg.cessation_sustain_frames: cessation=s; break
    frames=pd.DataFrame({"frame":df.frame,"time_s":df.time_s,"minimum_distance":minimum,"nearest_effector":nearest,"quality_pass":quality,"candidate_contact":candidate,"interaction_intensity":intensity,"smoothed_intensity":smooth})
    summary={"analysis_version":"0.2.0","trial_id":str(df.trial_id.iloc[0]),"fps":fps,"contact_events":len(accepted),"first_contact_frame":None if contact is None else int(df.frame.iloc[contact]),"first_contact_time_s":None if contact is None else float(df.time_s.iloc[contact]),"cessation_candidate_frame":None if cessation is None else int(df.frame.iloc[cessation]),"cessation_candidate_time_s":None if cessation is None else float(df.time_s.iloc[cessation]),"removal_interpretation":"candidate_only_requires_video_review","created_at_utc":datetime.now(timezone.utc).isoformat(),"config":asdict(cfg)}
    return StickerAnalysisResult(summary,pd.DataFrame(events),frames,cfg)

def write_sticker_outputs(folder, result):
    root=Path(folder); root.mkdir(parents=True,exist_ok=True); paths={"events":root/"events.csv","frames":root/"frame_quality.csv","summary":root/"summary.json"}
    if any(p.exists() for p in paths.values()): raise FileExistsError("拒绝覆盖已有贴纸结果。")
    result.events.to_csv(paths["events"],index=False,encoding="utf-8"); result.frame_quality.to_csv(paths["frames"],index=False,encoding="utf-8"); paths["summary"].write_text(json.dumps(result.summary,ensure_ascii=False,indent=2),encoding="utf-8"); return paths
