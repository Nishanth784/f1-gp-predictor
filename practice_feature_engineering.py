"""
practice_feature_engineering.py

Derives race-pace and telemetry signals from raw practice data (from practice_data_ingestion.py).

Key outputs per driver:
  Race pace analysis (FP2 long runs, falling back to FP3 / FP1):
    - AvgPace, BestPace, PaceConsistency (std dev) per tyre compound
    - DegradationSlope per compound (reuses race_aggregation.calculate_degradation_slope)
    - Normalized pace gap vs field average per compound

  Telemetry signals (cross-session best/avg):
    - MaxTrapSpeed, AvgTrapSpeed
    - FullThrottlePct, BrakingPct, DRSDeploymentPct
    - BrakePointDelta (vs field mean — positive = brakes later = more grip confidence)

  Weather:
    - AvgAirTemp, AvgTrackTemp, AvgWindSpeed, AvgWindDirection
    - TrackTempDeltaFP1toFP3 (track evolution signal)

All features are returned as a single DataFrame (one row per driver)
ready to be merged into winner_feature_engineering.engineer_winner_features().
"""

import warnings
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import fastf1

from race_aggregation import calculate_degradation_slope
from practice_data_ingestion import _enable_cache, load_practice_features

MIN_LONG_RUN_LAPS = 4  # minimum consecutive same-set laps to qualify as a race sim run


# ---------------------------------------------------------------------------
# Long run detection
# ---------------------------------------------------------------------------

def _detect_long_runs(laps: pd.DataFrame, driver: str) -> Dict[str, List[pd.DataFrame]]:
    """
    Find "long runs" for a driver: 4+ consecutive laps on the same tyre set,
    excluding in-laps and out-laps. These are the FP2 race simulation stints.

    Returns dict keyed by compound (e.g. "SOFT") → list of DataFrames,
    each DataFrame being one detected stint.
    """
    if laps is None or laps.empty or "Driver" not in laps.columns:
        return {}

    drv = laps[laps["Driver"] == driver].copy()
    if drv.empty:
        return {}

    # Exclude in/out laps
    for flag_col in ["IsInlap", "IsOutlap"]:
        if flag_col in drv.columns:
            drv = drv[~drv[flag_col].fillna(False)]

    # Require valid lap time
    if "LapTime" not in drv.columns:
        return {}
    lt = pd.to_timedelta(drv["LapTime"], errors="coerce").dt.total_seconds()
    drv = drv.copy()
    drv["LapTime_s"] = lt
    drv = drv[drv["LapTime_s"].notna() & (drv["LapTime_s"] > 60) & (drv["LapTime_s"] < 300)]
    if drv.empty:
        return {}

    if "LapNumber" in drv.columns:
        drv = drv.sort_values("LapNumber").reset_index(drop=True)

    if "Compound" not in drv.columns or "TyreLife" not in drv.columns:
        return {}

    # Identify stint boundaries: TyreLife goes back to 1 or 2 → new set
    drv["TyreLife_n"] = pd.to_numeric(drv["TyreLife"], errors="coerce")
    drv["NewStint"] = (
        drv["TyreLife_n"].isna() |
        (drv["TyreLife_n"] == 1) |
        (drv["TyreLife_n"].diff() <= 0)
    )
    drv["StintID"] = drv["NewStint"].cumsum()

    long_runs: Dict[str, List[pd.DataFrame]] = {}

    for _, stint in drv.groupby("StintID"):
        valid = stint[stint["LapTime_s"].notna()]
        if len(valid) < MIN_LONG_RUN_LAPS:
            continue

        compound_vals = valid["Compound"].dropna().astype(str).str.upper()
        if compound_vals.empty:
            continue
        compound = compound_vals.mode().iloc[0]

        long_runs.setdefault(compound, []).append(valid.copy())

    return long_runs


# ---------------------------------------------------------------------------
# Race pace features from a session
# ---------------------------------------------------------------------------

def _race_pace_from_session(session, drivers: List[str]) -> Dict[str, Dict[str, float]]:
    """
    Extract race pace features from long runs in one session (ideally FP2).

    Returns dict: driver → {feature_name: value}
    """
    result: Dict[str, Dict[str, float]] = {}
    if session is None:
        return result

    laps = session.laps

    for driver in drivers:
        feats: Dict[str, float] = {}
        long_runs = _detect_long_runs(laps, driver)

        for compound, runs in long_runs.items():
            all_laps = pd.concat(runs, ignore_index=True)
            lt = all_laps["LapTime_s"].dropna()
            if len(lt) == 0:
                continue

            pfx = f"RacePace_{compound}"
            feats[f"{pfx}_AvgPace"] = float(lt.mean())
            feats[f"{pfx}_BestPace"] = float(lt.min())
            feats[f"{pfx}_Consistency"] = float(lt.std()) if len(lt) > 1 else 0.0
            feats[f"{pfx}_LapCount"] = float(len(lt))

            # Degradation slope — seconds gained/lost per lap on same set
            if "LapNumber" in all_laps.columns and len(lt) >= 2:
                lap_nums = pd.to_numeric(all_laps["LapNumber"], errors="coerce")
                aligned_lt = lt.reindex(lap_nums.index)
                mask = aligned_lt.notna() & lap_nums.notna()
                if mask.sum() >= 2:
                    feats[f"{pfx}_DegradationSlope"] = float(
                        calculate_degradation_slope(aligned_lt[mask], lap_nums[mask])
                    )

        result[driver] = feats

    return result


def _add_pace_gaps(pace_by_driver: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    """
    For each AvgPace / BestPace feature, add a _Gap column = driver value − field average.
    Negative gap = faster than average (better).
    """
    # Collect all values per feature key
    all_vals: Dict[str, List[float]] = {}
    for feats in pace_by_driver.values():
        for k, v in feats.items():
            if "AvgPace" in k or "BestPace" in k:
                all_vals.setdefault(k, []).append(v)

    field_avg = {k: float(np.mean(v)) for k, v in all_vals.items() if v}

    enriched: Dict[str, Dict[str, float]] = {}
    for driver, feats in pace_by_driver.items():
        new_feats = dict(feats)
        for k, v in feats.items():
            if k in field_avg:
                new_feats[f"{k}_Gap"] = float(v - field_avg[k])
        enriched[driver] = new_feats

    return enriched


# ---------------------------------------------------------------------------
# Main entry point: build the practice feature DataFrame
# ---------------------------------------------------------------------------

def build_practice_feature_df(
    year: int,
    gp_name: str,
    raw_df: Optional[pd.DataFrame] = None,
    sessions_override: Optional[Dict] = None,
) -> pd.DataFrame:
    """
    Build a single-row-per-driver DataFrame of all practice-derived features.

    Args:
        year: Season year
        gp_name: Grand Prix name (as returned by FastF1 schedule)
        raw_df: If provided, use this pre-loaded raw practice DataFrame instead of
                re-loading from FastF1 (e.g. loaded from cache via load_practice_features())
        sessions_override: If provided, use these {name: session} objects (for testing)

    Returns:
        DataFrame with one row per driver, all numeric.
    """
    _enable_cache()
    warnings.filterwarnings("ignore")

    # ── 1. Load sessions ────────────────────────────────────────────────────
    if sessions_override is not None:
        sessions = sessions_override
    else:
        sessions: Dict = {}
        for name in ["FP1", "FP2", "FP3"]:
            try:
                s = fastf1.get_session(year, gp_name, name)
                s.load(laps=True, telemetry=True, weather=True, messages=False)
                sessions[name] = s
                print(f"  Loaded {name}")
            except Exception as e:
                print(f"  Skip {name}: {e}")

    if not sessions:
        # Fall back to raw_df if sessions unavailable
        if raw_df is not None and not raw_df.empty:
            return raw_df
        return pd.DataFrame()

    # All drivers across sessions
    all_drivers: set = set()
    for s in sessions.values():
        if hasattr(s, "laps") and s.laps is not None and "Driver" in s.laps.columns:
            all_drivers.update(s.laps["Driver"].dropna().unique())
    drivers = sorted(all_drivers)

    # ── 2. Race pace: FP2 first, then FP3, then FP1 ────────────────────────
    # FP2 is most representative for race pace (teams run long race sims)
    pace_feats: Dict[str, Dict[str, float]] = {d: {} for d in drivers}

    for sess_name in ["FP2", "FP3", "FP1"]:
        if sess_name not in sessions:
            continue
        sess_pace = _race_pace_from_session(sessions[sess_name], drivers)
        for driver, feats in sess_pace.items():
            for k, v in feats.items():
                # Prefix with session name so FP2 and FP3 features coexist
                pace_feats[driver][f"{sess_name}_{k}"] = v

    # Normalized pace gaps (within each session)
    if "FP2" in sessions:
        fp2_raw_pace = _race_pace_from_session(sessions["FP2"], drivers)
        fp2_gapped = _add_pace_gaps(fp2_raw_pace)
        for driver, feats in fp2_gapped.items():
            for k, v in feats.items():
                pace_feats[driver][f"FP2_{k}"] = v

    # ── 3. Merge with raw telemetry / weather from raw_df (or recompute) ───
    # Use raw_df if provided (from cache), otherwise extract inline
    if raw_df is not None and not raw_df.empty and "Driver" in raw_df.columns:
        base_df = raw_df.copy()
    else:
        # Inline extraction of telemetry/weather (already done in practice_data_ingestion)
        # Collect only the cross-session aggregate columns we need
        from practice_data_ingestion import (
            _extract_lap_features,
            _extract_telemetry_features,
            _compute_brake_point_deltas,
            _extract_weather,
        )
        rows = []
        for driver in drivers:
            row: Dict = {"Driver": driver}
            trap_speeds, full_tp, braking_p, drs_p, bd_vals = [], [], [], [], []
            weather_list = []

            for sess_name, s in sessions.items():
                lf = _extract_lap_features(s.laps, driver)
                for k, v in lf.items():
                    row[f"{sess_name}_{k}"] = v
                tf = _extract_telemetry_features(s, driver)
                for k, v in tf.items():
                    row[f"{sess_name}_{k}"] = v
                if "MaxTrapSpeed" in tf:
                    trap_speeds.append(tf["MaxTrapSpeed"])
                if "FullThrottlePct" in tf:
                    full_tp.append(tf["FullThrottlePct"])
                if "BrakingPct" in tf:
                    braking_p.append(tf["BrakingPct"])
                if "DRSDeploymentPct" in tf:
                    drs_p.append(tf["DRSDeploymentPct"])
                weather_list.append(_extract_weather(s))

            # Compute brake deltas for all sessions combined
            all_bd = {}
            for sess_name, s in sessions.items():
                bds = _compute_brake_point_deltas(s, drivers)
                all_bd[driver] = all_bd.get(driver, 0.0) + bds.get(driver, 0.0)
            row["BrakePointDelta"] = all_bd.get(driver, 0.0) / max(len(sessions), 1)

            if trap_speeds:
                row["MaxTrapSpeed"] = float(max(trap_speeds))
                row["AvgTrapSpeed"] = float(np.mean(trap_speeds))
            if full_tp:
                row["FullThrottlePct"] = float(np.mean(full_tp))
            if braking_p:
                row["BrakingPct"] = float(np.mean(braking_p))
            if drs_p:
                row["DRSDeploymentPct"] = float(np.mean(drs_p))

            for wkey in ["AvgAirTemp", "AvgTrackTemp", "AvgHumidity", "AvgWindSpeed", "AvgWindDirection"]:
                vals = [w[wkey] for w in weather_list if not np.isnan(w.get(wkey, float("nan")))]
                row[wkey] = float(np.mean(vals)) if vals else 0.0

            row["TrackTempDeltaFP1toFP3"] = 0.0
            if weather_list:
                fp1_tt = weather_list[0].get("AvgTrackTemp", float("nan")) if len(weather_list) > 0 else float("nan")
                fp3_tt = weather_list[-1].get("AvgTrackTemp", float("nan")) if len(weather_list) > 2 else float("nan")
                if not np.isnan(fp1_tt) and not np.isnan(fp3_tt):
                    row["TrackTempDeltaFP1toFP3"] = float(fp3_tt - fp1_tt)
            rows.append(row)

        base_df = pd.DataFrame(rows)

    # ── 4. Merge pace features into base_df ─────────────────────────────────
    pace_rows = []
    for driver in drivers:
        r = {"Driver": driver}
        r.update(pace_feats.get(driver, {}))
        pace_rows.append(r)

    pace_df = pd.DataFrame(pace_rows)

    if "Driver" in base_df.columns and "Driver" in pace_df.columns:
        final_df = pd.merge(base_df, pace_df, on="Driver", how="outer")
    else:
        final_df = base_df

    # Clean up
    numeric_cols = final_df.select_dtypes(include=[np.number]).columns
    final_df[numeric_cols] = (
        final_df[numeric_cols]
        .replace([float("inf"), float("-inf")], float("nan"))
        .fillna(0.0)
    )

    print(f"  Practice features: {len(final_df)} drivers, {len(final_df.columns)} columns")
    return final_df


# ---------------------------------------------------------------------------
# Convenience: load from cache and build features
# ---------------------------------------------------------------------------

def get_practice_features_cached(year: int, gp_name: str) -> Optional[pd.DataFrame]:
    """
    Try to load pre-computed practice features from cache.
    Returns None if not available (practice data not yet run for this GP).
    """
    df = load_practice_features(year, gp_name)
    if df is None or df.empty:
        return None
    return df
