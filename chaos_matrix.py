"""
chaos_matrix.py

Safety car & chaos probability layer — applied AFTER the base model prediction.

Two data sources for safety car rates:
  1. FastF1 track_status detection (real SC periods, status codes 4=SC, 6=VSC)
     Used to build/update the lookup table from historical race data.
  2. Static lookup table of known per-circuit rates (used when FastF1 data
     is unavailable or as a prior for circuits with < 3 historical races).

Track status codes (FastF1):
  1 = All Clear
  2 = Yellow Flag
  4 = Safety Car (full SC)
  5 = Red Flag
  6 = Virtual Safety Car (VSC)
  7 = VSC Ending

Output per driver:
  best_case    — win probability if race runs clean (no SC)
  likely       — base model output adjusted by chaos index
  worst_case   — win probability in high-chaos scenario (max SC smoothing)
"""

import os
import json
import warnings
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import fastf1

from practice_data_ingestion import _enable_cache


# ---------------------------------------------------------------------------
# Static safety car rate lookup table
# Built from historical knowledge + updated by compute_circuit_sc_rate().
# SC rate = fraction of races at this circuit that had at least one SC/VSC period.
# ---------------------------------------------------------------------------

CIRCUIT_SC_RATES: Dict[str, float] = {
    # Street circuits / high-incident tracks
    "Monaco Grand Prix":           0.85,
    "Azerbaijan Grand Prix":       0.80,
    "Singapore Grand Prix":        0.75,
    "Las Vegas Grand Prix":        0.70,
    "Saudi Arabian Grand Prix":    0.65,
    "Miami Grand Prix":            0.60,
    "Australian Grand Prix":       0.60,
    "Canadian Grand Prix":         0.55,
    "Hungarian Grand Prix":        0.50,
    "Belgian Grand Prix":          0.50,
    "Japanese Grand Prix":         0.45,
    "United States Grand Prix":    0.45,
    "Mexico City Grand Prix":      0.40,
    "São Paulo Grand Prix":        0.60,   # Interlagos historically chaotic
    "British Grand Prix":          0.45,
    "Austrian Grand Prix":         0.45,
    "Dutch Grand Prix":            0.40,
    "Spanish Grand Prix":          0.30,
    "French Grand Prix":           0.35,
    "Italian Grand Prix":          0.35,   # Monza — fast but low incident rate
    "Abu Dhabi Grand Prix":        0.30,
    "Bahrain Grand Prix":          0.35,
    "Chinese Grand Prix":          0.45,
    "Qatar Grand Prix":            0.55,
    "Emilia Romagna Grand Prix":   0.40,
    "Miami Grand Prix":            0.60,
    "Portuguese Grand Prix":       0.30,
    "Turkish Grand Prix":          0.40,
    "Russian Grand Prix":          0.45,
    "Styrian Grand Prix":          0.40,
}

# Default for circuits not in the lookup
DEFAULT_SC_RATE = 0.40


# ---------------------------------------------------------------------------
# Real SC detection from FastF1 track_status
# ---------------------------------------------------------------------------

def _session_had_sc(session) -> Tuple[bool, bool]:
    """
    Check whether a race session had a Safety Car or VSC period.
    Returns (had_sc: bool, had_vsc: bool).
    """
    try:
        ts = session.track_status
        if ts is None or ts.empty or "Status" not in ts.columns:
            return False, False
        statuses = ts["Status"].astype(str).str.strip()
        had_sc = (statuses == "4").any()
        had_vsc = (statuses == "6").any()
        return bool(had_sc), bool(had_vsc)
    except Exception:
        return False, False


def compute_circuit_sc_rate(
    gp_name: str,
    years: Optional[List[int]] = None,
    include_vsc: bool = True,
) -> Dict[str, float]:
    """
    Compute real SC/VSC rate for a circuit from FastF1 track status data.

    Args:
        gp_name: Grand Prix name (e.g. "Monaco Grand Prix")
        years: List of years to check (default: 2018-2025)
        include_vsc: If True, count VSC periods as chaos events too

    Returns:
        {
          "sc_rate": fraction of races with SC,
          "vsc_rate": fraction of races with VSC,
          "combined_rate": fraction with SC or VSC,
          "races_checked": N,
        }
    """
    _enable_cache()
    warnings.filterwarnings("ignore")

    if years is None:
        years = list(range(2018, 2026))

    sc_count = 0
    vsc_count = 0
    total = 0

    for year in years:
        try:
            s = fastf1.get_session(year, gp_name, "R")
            s.load(laps=False, telemetry=False, weather=False, messages=False)
            had_sc, had_vsc = _session_had_sc(s)
            sc_count += int(had_sc)
            vsc_count += int(had_vsc)
            total += 1
        except Exception:
            continue

    if total == 0:
        fallback = CIRCUIT_SC_RATES.get(gp_name, DEFAULT_SC_RATE)
        return {
            "sc_rate": fallback,
            "vsc_rate": fallback * 0.5,
            "combined_rate": fallback,
            "races_checked": 0,
        }

    sc_rate = sc_count / total
    vsc_rate = vsc_count / total
    combined_rate = sum(1 for y in years if True) / total  # recomputed below
    # Recount combined
    combined_count = 0
    for year in years:
        try:
            s = fastf1.get_session(year, gp_name, "R")
            s.load(laps=False, telemetry=False, weather=False, messages=False)
            had_sc, had_vsc = _session_had_sc(s)
            if had_sc or (include_vsc and had_vsc):
                combined_count += 1
        except Exception:
            continue

    return {
        "sc_rate": sc_rate,
        "vsc_rate": vsc_rate,
        "combined_rate": combined_count / total if total > 0 else DEFAULT_SC_RATE,
        "races_checked": total,
    }


def get_circuit_sc_rate(gp_name: str, use_fastf1: bool = False,
                        years: Optional[List[int]] = None) -> float:
    """
    Get the safety car probability for a circuit.

    By default uses the static lookup table (fast, no network).
    Set use_fastf1=True to compute from real race data (slow but accurate).
    """
    if use_fastf1:
        result = compute_circuit_sc_rate(gp_name, years=years)
        if result["races_checked"] >= 3:
            return result["combined_rate"]
        # Blend with static lookup if few races checked
        static = CIRCUIT_SC_RATES.get(gp_name, DEFAULT_SC_RATE)
        weight = result["races_checked"] / 5.0  # trust FastF1 more with more data
        return weight * result["combined_rate"] + (1 - weight) * static

    # Fast path: static lookup with fuzzy match
    # Try exact match first
    if gp_name in CIRCUIT_SC_RATES:
        return CIRCUIT_SC_RATES[gp_name]

    # Fuzzy match: check if gp_name is a substring of any key
    gp_lower = gp_name.lower()
    for key, rate in CIRCUIT_SC_RATES.items():
        if gp_lower in key.lower() or key.lower() in gp_lower:
            return rate

    return DEFAULT_SC_RATE


# ---------------------------------------------------------------------------
# Grid spread (qualifying tightness → overtaking / chaos potential)
# ---------------------------------------------------------------------------

def _compute_grid_spread(qualifying_df: Optional[pd.DataFrame]) -> float:
    """
    Compute normalized grid spread: gap between P1 and P10 in qualifying.
    Tighter grid → more potential for chaos (overtaking, strategy variation).
    Returns value in [0, 1]: 1 = very tight (chaotic), 0 = spread out (processional).
    """
    if qualifying_df is None or qualifying_df.empty:
        return 0.5

    q_times = []
    for q_col in ["Q3", "Q2", "Q1"]:
        if q_col in qualifying_df.columns:
            times = pd.to_timedelta(qualifying_df[q_col], errors="coerce").dt.total_seconds()
            valid = times.dropna().tolist()
            if valid:
                q_times = valid
                break

    if len(q_times) < 10:
        return 0.5

    sorted_times = sorted(q_times)
    p1 = sorted_times[0]
    p10 = sorted_times[9]
    gap = p10 - p1  # seconds

    # Typical gaps: Monaco ~1.0s (tight), Monza ~2.5s (spread)
    # Normalize: gap < 1.0 = tight (return 1.0), gap > 2.5 = spread (return 0.0)
    if gap < 1.0:
        return 1.0
    elif gap > 2.5:
        return 0.0
    else:
        return float(1.0 - (gap - 1.0) / 1.5)


# ---------------------------------------------------------------------------
# Chaos index
# ---------------------------------------------------------------------------

def compute_chaos_index(
    gp_name: str,
    qualifying_df: Optional[pd.DataFrame] = None,
    weather_wind_speed: float = 0.0,
    sc_rate_override: Optional[float] = None,
) -> float:
    """
    Compute overall race chaos index [0, 1].

    Components (equally weighted):
      - SC probability for this circuit (historical)
      - Grid spread (tight grid = more chaos)
      - Wind speed factor (high wind = more incidents, especially in qualifying)

    Args:
        gp_name: Grand Prix name
        qualifying_df: Optional qualifying results (for grid spread)
        weather_wind_speed: Average wind speed (km/h) from practice weather
        sc_rate_override: Override the SC rate lookup (e.g. from precomputed FastF1 data)

    Returns:
        Chaos index in [0.0, 1.0]
    """
    sc_rate = sc_rate_override if sc_rate_override is not None else get_circuit_sc_rate(gp_name)
    grid_spread = _compute_grid_spread(qualifying_df)

    # Wind factor: > 40 km/h meaningfully affects car balance at high-speed circuits
    wind_factor = float(np.clip(weather_wind_speed / 80.0, 0.0, 1.0))

    chaos = (sc_rate + grid_spread + wind_factor) / 3.0
    return float(np.clip(chaos, 0.0, 1.0))


# ---------------------------------------------------------------------------
# Chaos-adjusted probability function
# ---------------------------------------------------------------------------

def apply_chaos_adjustment(
    base_probabilities: np.ndarray,
    chaos_index: float,
) -> np.ndarray:
    """
    Smooth win probabilities based on chaos index.

    At low chaos (< 0.2): probabilities unchanged — model is confident.
    At high chaos (> 0.7): probabilities pulled toward uniform — don't let
    model be overconfident when anything can happen (e.g. Monaco rain).

    Formula: adjusted = (1 - chaos) * raw + chaos * uniform
    Then renormalize so sum = 1.
    """
    if len(base_probabilities) == 0:
        return base_probabilities

    n = len(base_probabilities)
    uniform = np.ones(n) / n

    # Only apply meaningful smoothing above threshold
    if chaos_index <= 0.2:
        return base_probabilities

    smoothed = (1.0 - chaos_index) * base_probabilities + chaos_index * uniform
    total = smoothed.sum()
    if total > 0:
        smoothed = smoothed / total

    return smoothed


# ---------------------------------------------------------------------------
# Scenario range computation
# ---------------------------------------------------------------------------

def compute_scenario_ranges(
    base_probabilities: np.ndarray,
    chaos_index: float,
) -> Dict[str, np.ndarray]:
    """
    Produce three scenario probability arrays per driver:
      best_case   — clean race, no SC; model probabilities at minimum chaos
      likely      — base model output adjusted by actual chaos index
      worst_case  — maximum SC / chaos scenario (heavy smoothing toward uniform)

    Args:
        base_probabilities: Raw model win probabilities (one per driver)
        chaos_index: Overall chaos index [0, 1] for this race

    Returns:
        Dict with keys "best_case", "likely", "worst_case"
        Each value is a np.ndarray of the same length as base_probabilities.
    """
    if len(base_probabilities) == 0:
        return {"best_case": base_probabilities,
                "likely": base_probabilities,
                "worst_case": base_probabilities}

    n = len(base_probabilities)
    uniform = np.ones(n) / n

    # Best case: clean race — minimal chaos adjustment (5% blend only)
    best = (0.95 * base_probabilities + 0.05 * uniform)
    best = best / best.sum()

    # Likely: actual chaos index applied
    likely = apply_chaos_adjustment(base_probabilities, chaos_index)

    # Worst case: heavy chaos (safety car + weather + incident) — 80% of chaos or 0.9 min
    worst_chaos = float(min(0.9, chaos_index * 1.5))
    worst = (1.0 - worst_chaos) * base_probabilities + worst_chaos * uniform
    worst = worst / worst.sum()

    return {
        "best_case": best.astype(float),
        "likely": likely.astype(float),
        "worst_case": worst.astype(float),
    }


# ---------------------------------------------------------------------------
# High-level function: compute everything for one GP
# ---------------------------------------------------------------------------

def get_chaos_adjusted_predictions(
    gp_name: str,
    base_probabilities: np.ndarray,
    qualifying_df: Optional[pd.DataFrame] = None,
    weather_wind_speed: float = 0.0,
    use_fastf1_sc: bool = False,
) -> Dict[str, object]:
    """
    Full chaos pipeline for one race.

    Returns:
        {
          "chaos_index": float,
          "sc_rate": float,
          "grid_spread": float,
          "scenarios": {
              "best_case": np.ndarray,
              "likely": np.ndarray,
              "worst_case": np.ndarray,
          }
        }
    """
    sc_rate = get_circuit_sc_rate(gp_name, use_fastf1=use_fastf1_sc)
    grid_spread = _compute_grid_spread(qualifying_df)
    wind_factor = float(np.clip(weather_wind_speed / 80.0, 0.0, 1.0))
    chaos_index = float(np.clip((sc_rate + grid_spread + wind_factor) / 3.0, 0.0, 1.0))

    scenarios = compute_scenario_ranges(base_probabilities, chaos_index)

    return {
        "chaos_index": chaos_index,
        "sc_rate": sc_rate,
        "grid_spread": grid_spread,
        "wind_factor": wind_factor,
        "scenarios": scenarios,
    }


# ---------------------------------------------------------------------------
# CLI: compute and print SC rates for a circuit
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    gp = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Monaco Grand Prix"
    print(f"Computing SC rate for: {gp}")
    print("  Static lookup:", get_circuit_sc_rate(gp))
    print("  FastF1 (2018-2025):", end=" ", flush=True)
    result = compute_circuit_sc_rate(gp)
    print(result)
