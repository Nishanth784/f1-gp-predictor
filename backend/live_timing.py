"""
live_timing.py — FastF1 session loader with in-memory cache.

Provides structured lap timing data, race control messages, and weather
for any historical race session. Cache prevents re-loading large sessions.
"""

import time
import threading
from typing import Dict, Any, Optional, List, Tuple

import fastf1
import pandas as pd
import numpy as np

# In-memory session cache: key = (year, gp_slug, session_type)
_SESSION_CACHE: Dict[Tuple, Dict[str, Any]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL = 3600  # seconds — 1 hour


def _cache_key(year: int, gp: str, session_type: str = "R") -> Tuple:
    return (year, gp.lower().strip(), session_type.upper())


def _is_cached(key: Tuple) -> bool:
    with _CACHE_LOCK:
        entry = _SESSION_CACHE.get(key)
        if entry is None:
            return False
        return (time.time() - entry["ts"]) < _CACHE_TTL


def _get_cached(key: Tuple) -> Optional[Dict[str, Any]]:
    with _CACHE_LOCK:
        entry = _SESSION_CACHE.get(key)
        if entry and (time.time() - entry["ts"]) < _CACHE_TTL:
            return entry["data"]
    return None


def _set_cached(key: Tuple, data: Dict[str, Any]) -> None:
    with _CACHE_LOCK:
        _SESSION_CACHE[key] = {"data": data, "ts": time.time()}


def _ms(timedelta) -> Optional[int]:
    """Convert pandas Timedelta to integer milliseconds, None if NaT."""
    try:
        if pd.isna(timedelta):
            return None
        return int(timedelta.total_seconds() * 1000)
    except Exception:
        return None


def _fmt_time(timedelta) -> Optional[str]:
    """Format lap time as mm:ss.mmm string."""
    try:
        if pd.isna(timedelta):
            return None
        total = timedelta.total_seconds()
        minutes = int(total // 60)
        seconds = total % 60
        return f"{minutes}:{seconds:06.3f}"
    except Exception:
        return None


def _load_session(year: int, gp: str, session_type: str = "R") -> Any:
    """Load a FastF1 session with laps. Raises on failure."""
    session = fastf1.get_session(year, gp, session_type)
    session.load(laps=True, telemetry=False, weather=True, messages=True)
    return session


def load_timing_data(year: int, gp: str, session_type: str = "R") -> Dict[str, Any]:
    """
    Load and cache structured timing data for a session.

    Returns dict with keys:
    - laps: list of lap records (all drivers, all laps)
    - race_control: list of race control messages
    - weather: list of weather snapshots
    - drivers: sorted driver list with team info
    - total_laps: int
    - session_type: str
    """
    key = _cache_key(year, gp, session_type)
    cached = _get_cached(key)
    if cached:
        return cached

    session = _load_session(year, gp, session_type)
    laps_df = session.laps

    # --- Build per-driver, per-lap records ---
    laps_out: List[Dict] = []

    if laps_df is not None and not laps_df.empty:
        # Add position column if available
        if "Position" not in laps_df.columns:
            laps_df = laps_df.copy()
            laps_df["Position"] = None

        # Per-driver personal best sector times (for colour coding)
        pb_s1: Dict[str, float] = {}
        pb_s2: Dict[str, float] = {}
        pb_s3: Dict[str, float] = {}
        pb_lap: Dict[str, float] = {}

        for _, row in laps_df.iterrows():
            drv = str(row.get("Driver", ""))
            s1 = _ms(row.get("Sector1Time"))
            s2 = _ms(row.get("Sector2Time"))
            s3 = _ms(row.get("Sector3Time"))
            lt = _ms(row.get("LapTime"))
            if s1 and (drv not in pb_s1 or s1 < pb_s1[drv]): pb_s1[drv] = s1
            if s2 and (drv not in pb_s2 or s2 < pb_s2[drv]): pb_s2[drv] = s2
            if s3 and (drv not in pb_s3 or s3 < pb_s3[drv]): pb_s3[drv] = s3
            if lt and (drv not in pb_lap or lt < pb_lap[drv]): pb_lap[drv] = lt

        # Overall session bests (for purple)
        best_s1 = min(pb_s1.values()) if pb_s1 else None
        best_s2 = min(pb_s2.values()) if pb_s2 else None
        best_s3 = min(pb_s3.values()) if pb_s3 else None

        def sector_colour(val, best_overall, personal_best):
            if val is None:
                return "grey"
            if best_overall and val <= best_overall:
                return "purple"
            if personal_best and val <= personal_best:
                return "green"
            return "yellow"

        for _, row in laps_df.iterrows():
            drv = str(row.get("Driver", ""))
            lt_ms = _ms(row.get("LapTime"))
            s1_ms = _ms(row.get("Sector1Time"))
            s2_ms = _ms(row.get("Sector2Time"))
            s3_ms = _ms(row.get("Sector3Time"))

            pit_in  = row.get("PitInTime")
            pit_out = row.get("PitOutTime")
            is_pit = (pit_in is not None and not pd.isna(pit_in)) or \
                     (pit_out is not None and not pd.isna(pit_out))

            position = row.get("Position")
            try:
                position = int(position) if position is not None and not pd.isna(position) else None
            except (ValueError, TypeError):
                position = None

            gap = row.get("GapToLeader")
            try:
                gap = float(gap) if gap is not None and not pd.isna(gap) else None
            except (ValueError, TypeError):
                gap = None

            laps_out.append({
                "driver":       drv,
                "team":         str(row.get("Team", "")),
                "lap_number":   int(row.get("LapNumber", 0)),
                "position":     position,
                "lap_time_ms":  lt_ms,
                "lap_time_fmt": _fmt_time(row.get("LapTime")),
                "sector1_ms":   s1_ms,
                "sector2_ms":   s2_ms,
                "sector3_ms":   s3_ms,
                "s1_colour":    sector_colour(s1_ms, best_s1, pb_s1.get(drv)),
                "s2_colour":    sector_colour(s2_ms, best_s2, pb_s2.get(drv)),
                "s3_colour":    sector_colour(s3_ms, best_s3, pb_s3.get(drv)),
                "compound":     str(row.get("Compound", "UNKNOWN")).upper(),
                "tyre_life":    int(row.get("TyreLife", 0)) if not pd.isna(row.get("TyreLife", 0)) else 0,
                "is_pit_lap":   is_pit,
                "gap_to_leader": round(gap, 3) if gap is not None else None,
                "is_accurate":  bool(row.get("IsAccurate", False)),
            })

    total_laps = int(laps_df["LapNumber"].max()) if not laps_df.empty else 0

    # --- Unique driver list ---
    drivers_out = []
    seen = set()
    for lap in sorted(laps_out, key=lambda x: x["lap_number"]):
        drv = lap["driver"]
        if drv not in seen:
            seen.add(drv)
            drivers_out.append({"driver": drv, "team": lap["team"]})

    # --- Race control messages ---
    rc_out: List[Dict] = []
    try:
        rc_df = session.race_control_messages
        if rc_df is not None and not rc_df.empty:
            for _, row in rc_df.iterrows():
                time_val = row.get("Time")
                time_s = None
                try:
                    if time_val is not None and not pd.isna(time_val):
                        time_s = round(float(time_val.total_seconds()), 1)
                except Exception:
                    pass
                rc_out.append({
                    "time_s":   time_s,
                    "lap":      int(row.get("Lap", 0)) if not pd.isna(row.get("Lap", 0)) else None,
                    "category": str(row.get("Category", "")),
                    "message":  str(row.get("Message", "")),
                    "flag":     str(row.get("Flag", "")),
                    "scope":    str(row.get("Scope", "")),
                    "driver":   str(row.get("RacingNumber", "")),
                })
    except Exception:
        pass

    # --- Weather ---
    weather_out: List[Dict] = []
    try:
        wx = session.weather_data
        if wx is not None and not wx.empty:
            # Downsample to ~30 points
            step = max(1, len(wx) // 30)
            for _, row in wx.iloc[::step].iterrows():
                time_val = row.get("Time")
                time_s = None
                try:
                    if time_val is not None and not pd.isna(time_val):
                        time_s = round(float(time_val.total_seconds()), 1)
                except Exception:
                    pass
                weather_out.append({
                    "time_s":         time_s,
                    "air_temp":       round(float(row.get("AirTemp", 0)), 1),
                    "track_temp":     round(float(row.get("TrackTemp", 0)), 1),
                    "wind_speed":     round(float(row.get("WindSpeed", 0)), 1),
                    "wind_direction": round(float(row.get("WindDirection", 0)), 0),
                    "humidity":       round(float(row.get("Humidity", 0)), 1),
                    "rainfall":       bool(row.get("Rainfall", False)),
                })
    except Exception:
        pass

    data = {
        "year":         year,
        "gp":           gp,
        "session_type": session_type.upper(),
        "total_laps":   total_laps,
        "drivers":      drivers_out,
        "laps":         laps_out,
        "race_control": rc_out,
        "weather":      weather_out,
    }

    _set_cached(key, data)
    return data


def get_lap_snapshot(timing_data: Dict, lap_number: int) -> List[Dict]:
    """
    Return each driver's state AT the given lap number:
    their most recent completed lap up to lap_number.
    Sorted by position (or cumulative time if no position).
    """
    all_laps = timing_data.get("laps", [])
    by_driver: Dict[str, Dict] = {}
    for lap in all_laps:
        if lap["lap_number"] > lap_number:
            continue
        drv = lap["driver"]
        prev = by_driver.get(drv)
        if prev is None or lap["lap_number"] > prev["lap_number"]:
            by_driver[drv] = lap
    snapshot = list(by_driver.values())
    snapshot.sort(key=lambda x: (x.get("position") or 99, x.get("driver", "")))
    return snapshot
