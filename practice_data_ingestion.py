"""
practice_data_ingestion.py

Loads FP1 / FP2 / FP3 practice session data from FastF1.

Designed to run as a STANDALONE BATCH JOB after FP3 ends (Saturday morning).
Do NOT call this inline from an API request — telemetry loading takes 10-45 min.

Per driver, extracts:
  Lap data   : lap times, sector times, tyre compound, tyre age, in/out lap flags
  Telemetry  : max trap speed, throttle distribution, brake point delta, DRS deployment %
               (MaxRPM intentionally excluded — too noisy across fuel loads)
  Weather    : air temp, track temp, wind speed, wind direction (session averages)
               + track temp delta FP1→FP3 (track evolution signal)

Usage:
  python practice_data_ingestion.py 2025 "Spanish Grand Prix"
  # → writes cache/2025_spanish_grand_prix_practice.json
"""

import os
import json
import warnings
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import fastf1


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _enable_cache() -> None:
    cache_dir = os.path.join(os.getcwd(), "fastf1_cache")
    os.makedirs(cache_dir, exist_ok=True)
    fastf1.Cache.enable_cache(cache_dir)


def _cache_path(year: int, gp_name: str, cache_dir: str = "cache") -> str:
    safe = gp_name.replace(" ", "_").lower()
    return os.path.join(cache_dir, f"{year}_{safe}_practice.json")


def save_practice_features(df: pd.DataFrame, year: int, gp_name: str,
                           cache_dir: str = "cache") -> str:
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(year, gp_name, cache_dir)
    df.to_json(path, orient="records", indent=2)
    print(f"  Saved → {path}")
    return path


def load_practice_features(year: int, gp_name: str,
                           cache_dir: str = "cache") -> Optional[pd.DataFrame]:
    """Return cached practice features, or None if not yet computed."""
    path = _cache_path(year, gp_name, cache_dir)
    if not os.path.exists(path):
        return None
    try:
        return pd.read_json(path, orient="records")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Session loader
# ---------------------------------------------------------------------------

def _load_session(year: int, gp_name: str, session_name: str):
    """Load a single session; returns None on failure (missing/future session)."""
    _enable_cache()
    warnings.filterwarnings("ignore")
    try:
        s = fastf1.get_session(year, gp_name, session_name)
        s.load(laps=True, telemetry=True, weather=True, messages=False)
        print(f"  Loaded {year} {gp_name} {session_name}")
        return s
    except Exception as e:
        print(f"  Skip {session_name}: {e}")
        return None


# ---------------------------------------------------------------------------
# Weather extraction
# ---------------------------------------------------------------------------

def _extract_weather(session) -> Dict[str, float]:
    defaults: Dict[str, float] = {
        "AvgAirTemp": float("nan"),
        "AvgTrackTemp": float("nan"),
        "AvgHumidity": float("nan"),
        "AvgWindSpeed": float("nan"),
        "AvgWindDirection": float("nan"),
    }
    try:
        w = session.weather_data
        if w is None or w.empty:
            return defaults
        mapping = {
            "AvgAirTemp": "AirTemp",
            "AvgTrackTemp": "TrackTemp",
            "AvgHumidity": "Humidity",
            "AvgWindSpeed": "WindSpeed",
            "AvgWindDirection": "WindDirection",
        }
        result: Dict[str, float] = {}
        for out_col, src_col in mapping.items():
            if src_col in w.columns:
                vals = pd.to_numeric(w[src_col], errors="coerce").dropna()
                result[out_col] = float(vals.mean()) if len(vals) > 0 else float("nan")
            else:
                result[out_col] = float("nan")
        return result
    except Exception:
        return defaults


# ---------------------------------------------------------------------------
# Lap feature extraction (per driver, per session)
# ---------------------------------------------------------------------------

def _extract_lap_features(laps: pd.DataFrame, driver: str) -> Dict[str, float]:
    feats: Dict[str, float] = {}
    if laps is None or laps.empty or "Driver" not in laps.columns:
        return feats

    drv = laps[laps["Driver"] == driver].copy()
    if drv.empty:
        return feats

    # Lap time in seconds
    if "LapTime" in drv.columns:
        lt = pd.to_timedelta(drv["LapTime"], errors="coerce").dt.total_seconds()
        valid = lt.dropna()
        valid = valid[(valid > 60) & (valid < 300)]  # sanity filter
        if len(valid) > 0:
            feats["AvgLapTime"] = float(valid.mean())
            feats["BestLapTime"] = float(valid.min())
            feats["LapTimeStd"] = float(valid.std()) if len(valid) > 1 else 0.0
            feats["LapCount"] = float(len(valid))

    # Sector times
    for s_col in ["Sector1Time", "Sector2Time", "Sector3Time"]:
        if s_col in drv.columns:
            st = pd.to_timedelta(drv[s_col], errors="coerce").dt.total_seconds()
            valid_st = st.dropna()
            if len(valid_st) > 0:
                feats[f"Best{s_col}"] = float(valid_st.min())
                feats[f"Avg{s_col}"] = float(valid_st.mean())

    # Tyre compound lap counts
    if "Compound" in drv.columns:
        compounds = drv["Compound"].dropna().astype(str).str.upper()
        for compound in ["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"]:
            feats[f"Laps_{compound}"] = float((compounds == compound).sum())

    # Tyre age
    if "TyreLife" in drv.columns:
        tl = pd.to_numeric(drv["TyreLife"], errors="coerce").dropna()
        if len(tl) > 0:
            feats["MaxTyreAge"] = float(tl.max())
            feats["AvgTyreAge"] = float(tl.mean())

    return feats


# ---------------------------------------------------------------------------
# Telemetry feature extraction (per driver, fastest lap only)
# ---------------------------------------------------------------------------

def _extract_telemetry_features(session, driver: str) -> Dict[str, float]:
    """
    Extracts telemetry from the driver's fastest lap in the session.
    Uses fastest lap for clean signal (not a fuel-heavy outlap or cool-down).
    MaxRPM excluded — not a reliable signal across varying fuel loads.
    """
    feats: Dict[str, float] = {}
    try:
        drv_laps = session.laps.pick_driver(driver)
        if drv_laps is None or len(drv_laps) == 0:
            return feats
        fastest = drv_laps.pick_fastest()
        if fastest is None:
            return feats
        tel = fastest.get_telemetry()
        if tel is None or tel.empty:
            return feats

        # Max trap speed (km/h) — proxy for aero config + engine
        if "Speed" in tel.columns:
            speeds = pd.to_numeric(tel["Speed"], errors="coerce").dropna()
            if len(speeds) > 0:
                feats["MaxTrapSpeed"] = float(speeds.max())
                feats["AvgSpeed"] = float(speeds.mean())

        # Throttle distribution
        if "Throttle" in tel.columns:
            throttle = pd.to_numeric(tel["Throttle"], errors="coerce").dropna()
            if len(throttle) > 0:
                feats["AvgThrottle"] = float(throttle.mean())
                feats["FullThrottlePct"] = float((throttle >= 99).sum() / len(throttle))

        # Braking
        if "Brake" in tel.columns:
            brake = pd.to_numeric(tel["Brake"], errors="coerce").dropna()
            if len(brake) > 0:
                feats["BrakingPct"] = float((brake > 0).sum() / len(brake))

        # DRS deployment — values >= 10 mean DRS open in FastF1
        if "DRS" in tel.columns:
            drs = pd.to_numeric(tel["DRS"], errors="coerce").dropna()
            if len(drs) > 0:
                feats["DRSDeploymentPct"] = float((drs >= 10).sum() / len(drs))

    except Exception:
        pass

    return feats


# ---------------------------------------------------------------------------
# Brake point delta (field-relative, computed across all drivers)
# ---------------------------------------------------------------------------

def _compute_brake_point_deltas(session, drivers: List[str]) -> Dict[str, float]:
    """
    For each driver, find the distance at which they first apply brakes on their
    fastest lap. Delta = (field average first-brake distance) − (driver's).
    Positive delta → driver brakes later than average (more grip confidence).
    """
    first_brake_dist: Dict[str, float] = {}

    for driver in drivers:
        try:
            drv_laps = session.laps.pick_driver(driver)
            if drv_laps is None or len(drv_laps) == 0:
                continue
            fastest = drv_laps.pick_fastest()
            if fastest is None:
                continue
            tel = fastest.get_telemetry()
            if tel is None or tel.empty:
                continue
            if "Brake" not in tel.columns or "Distance" not in tel.columns:
                continue

            brake = pd.to_numeric(tel["Brake"], errors="coerce")
            dist = pd.to_numeric(tel["Distance"], errors="coerce")
            braking_dists = dist[brake > 0].dropna()
            if len(braking_dists) > 0:
                first_brake_dist[driver] = float(braking_dists.iloc[0])
        except Exception:
            continue

    if not first_brake_dist:
        return {d: 0.0 for d in drivers}

    avg = float(np.mean(list(first_brake_dist.values())))
    # Positive = brakes later = more confident
    return {d: float(first_brake_dist.get(d, avg) - avg) for d in drivers}


# ---------------------------------------------------------------------------
# Main extraction pipeline
# ---------------------------------------------------------------------------

def extract_practice_features(year: int, gp_name: str) -> pd.DataFrame:
    """
    Load FP1 / FP2 / FP3 and return a DataFrame with one row per driver
    containing all practice features.

    This is SLOW (10-45 min). Call save_practice_features() afterwards
    so the API can serve from cache.
    """
    print(f"\n{'='*60}")
    print(f"Practice feature extraction: {year} {gp_name}")
    print(f"{'='*60}")

    sessions = {}
    for name in ["FP1", "FP2", "FP3"]:
        s = _load_session(year, gp_name, name)
        if s is not None:
            sessions[name] = s

    if not sessions:
        print("  No practice sessions available.")
        return pd.DataFrame()

    # All drivers seen across any session
    all_drivers: set = set()
    for s in sessions.values():
        if hasattr(s, "laps") and s.laps is not None and "Driver" in s.laps.columns:
            all_drivers.update(s.laps["Driver"].dropna().unique())
    drivers = sorted(all_drivers)
    print(f"  {len(drivers)} drivers across {len(sessions)} sessions")

    # Per-session weather (need FP1 and FP3 for delta)
    weather_by_sess: Dict[str, Dict[str, float]] = {
        name: _extract_weather(s) for name, s in sessions.items()
    }

    # Per-session brake point deltas
    brake_deltas_by_sess: Dict[str, Dict[str, float]] = {
        name: _compute_brake_point_deltas(s, drivers) for name, s in sessions.items()
    }

    rows = []
    for driver in drivers:
        row: Dict[str, float] = {"Driver": driver}

        # Collect per-session values for cross-session aggregates
        trap_speeds, full_throttle_pcts, braking_pcts, drs_pcts, brake_delta_vals = [], [], [], [], []

        for sess_name, s in sessions.items():
            # Lap features — prefixed by session
            lf = _extract_lap_features(s.laps, driver)
            for k, v in lf.items():
                row[f"{sess_name}_{k}"] = v

            # Telemetry features — prefixed by session
            tf = _extract_telemetry_features(s, driver)
            for k, v in tf.items():
                row[f"{sess_name}_{k}"] = v

            # Collect for cross-session aggregates
            if "MaxTrapSpeed" in tf:
                trap_speeds.append(tf["MaxTrapSpeed"])
            if "FullThrottlePct" in tf:
                full_throttle_pcts.append(tf["FullThrottlePct"])
            if "BrakingPct" in tf:
                braking_pcts.append(tf["BrakingPct"])
            if "DRSDeploymentPct" in tf:
                drs_pcts.append(tf["DRSDeploymentPct"])

            bd = brake_deltas_by_sess.get(sess_name, {}).get(driver, 0.0)
            brake_delta_vals.append(bd)

        # Cross-session aggregates (best/avg across FP1/FP2/FP3)
        if trap_speeds:
            row["MaxTrapSpeed"] = float(max(trap_speeds))
            row["AvgTrapSpeed"] = float(np.mean(trap_speeds))
        if full_throttle_pcts:
            row["FullThrottlePct"] = float(np.mean(full_throttle_pcts))
        if braking_pcts:
            row["BrakingPct"] = float(np.mean(braking_pcts))
        if drs_pcts:
            row["DRSDeploymentPct"] = float(np.mean(drs_pcts))
        if brake_delta_vals:
            row["BrakePointDelta"] = float(np.mean(brake_delta_vals))

        # Weather aggregates across all sessions
        for key in ["AvgAirTemp", "AvgTrackTemp", "AvgHumidity", "AvgWindSpeed", "AvgWindDirection"]:
            vals = [weather_by_sess[n][key] for n in sessions if not np.isnan(weather_by_sess[n].get(key, float("nan")))]
            row[key] = float(np.mean(vals)) if vals else float("nan")

        # Track temp evolution: FP1 → FP3 delta
        fp1_tt = weather_by_sess.get("FP1", {}).get("AvgTrackTemp", float("nan"))
        fp3_tt = weather_by_sess.get("FP3", {}).get("AvgTrackTemp", float("nan"))
        if not np.isnan(fp1_tt) and not np.isnan(fp3_tt):
            row["TrackTempDeltaFP1toFP3"] = float(fp3_tt - fp1_tt)
        else:
            row["TrackTempDeltaFP1toFP3"] = 0.0

        rows.append(row)

    df = pd.DataFrame(rows)
    # Replace inf / -inf with NaN, then fill NaN with 0
    df = df.replace([float("inf"), float("-inf")], float("nan"))
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].fillna(0.0)

    print(f"  Done: {len(df)} drivers, {len(df.columns)} raw columns")
    return df


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3:
        year_arg = int(sys.argv[1])
        gp_arg = " ".join(sys.argv[2:])
    else:
        year_arg = 2025
        gp_arg = "Spanish Grand Prix"

    df = extract_practice_features(year_arg, gp_arg)
    if not df.empty:
        path = save_practice_features(df, year_arg, gp_arg)
        print(f"\nDone. {len(df)} drivers × {len(df.columns)} features → {path}")
    else:
        print("No data extracted.")
