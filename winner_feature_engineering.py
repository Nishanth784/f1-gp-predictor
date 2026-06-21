from typing import Tuple, List, Optional
import warnings

import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder

from data_ingestion import get_winner_prediction_data, get_event_schedule


# ---------------------------------------------------------------------------
# Historical driver / team stats (existing logic, unchanged)
# ---------------------------------------------------------------------------

def calculate_driver_stats(driver: str, year: int, current_gp: str) -> dict:
    """Historical stats for a driver up to (not including) current GP."""
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    warnings.filterwarnings("ignore", category=UserWarning)

    stats = {"win_rate": 0.0, "avg_position": 20.0, "total_wins": 0, "total_races": 0}

    try:
        schedule = get_event_schedule(year)
        if schedule.empty or "EventName" not in schedule.columns:
            return stats

        all_gps = schedule["EventName"].dropna().tolist()
        if current_gp not in all_gps:
            return stats

        current_idx = all_gps.index(current_gp)
        previous_gps = all_gps[:current_idx]
        wins, positions = 0, []

        for gp in previous_gps:
            try:
                race_results = get_winner_prediction_data(year, gp)
                if not race_results.empty and "Driver" in race_results.columns:
                    driver_data = race_results[race_results["Driver"] == driver]
                    if not driver_data.empty:
                        if "IsWinner" in driver_data.columns:
                            wins += int(driver_data["IsWinner"].iloc[0])
                        if "Position" in driver_data.columns:
                            pos = driver_data["Position"].iloc[0]
                            if pd.notna(pos):
                                positions.append(float(pos))
            except Exception:
                continue

        stats["total_races"] = len(previous_gps)
        stats["total_wins"] = wins
        if previous_gps:
            stats["win_rate"] = wins / len(previous_gps)
        if positions:
            stats["avg_position"] = np.mean(positions)
    except Exception:
        pass

    return stats


def calculate_team_stats(team: str, year: int, current_gp: str) -> dict:
    """Historical stats for a team up to (not including) current GP."""
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    warnings.filterwarnings("ignore", category=UserWarning)

    stats = {"win_rate": 0.0, "avg_position": 20.0, "total_wins": 0, "total_races": 0}

    try:
        schedule = get_event_schedule(year)
        if schedule.empty or "EventName" not in schedule.columns:
            return stats

        all_gps = schedule["EventName"].dropna().tolist()
        if current_gp not in all_gps:
            return stats

        current_idx = all_gps.index(current_gp)
        previous_gps = all_gps[:current_idx]
        wins, positions = 0, []

        for gp in previous_gps:
            try:
                race_results = get_winner_prediction_data(year, gp)
                if not race_results.empty and "Team" in race_results.columns:
                    team_data = race_results[race_results["Team"] == team]
                    if not team_data.empty:
                        if "IsWinner" in team_data.columns:
                            if team_data["IsWinner"].sum() > 0:
                                wins += 1
                        if "Position" in team_data.columns:
                            best_pos = team_data["Position"].min()
                            if pd.notna(best_pos):
                                positions.append(float(best_pos))
            except Exception:
                continue

        stats["total_races"] = len(previous_gps)
        stats["total_wins"] = wins
        if previous_gps:
            stats["win_rate"] = wins / len(previous_gps)
        if positions:
            stats["avg_position"] = np.mean(positions)
    except Exception:
        pass

    return stats


# ---------------------------------------------------------------------------
# Practice feature merging
# ---------------------------------------------------------------------------

def _merge_practice_features(work: pd.DataFrame, year: int, gp_name: str) -> pd.DataFrame:
    """
    Attempt to load pre-computed practice features from cache and left-join
    onto the current DataFrame by Driver.

    If cache is not available (practice job hasn't run yet), returns work unchanged.
    Practice features that can't be found for a driver are filled with 0.0.
    """
    try:
        from practice_data_ingestion import load_practice_features
        practice_df = load_practice_features(year, gp_name)
        if practice_df is None or practice_df.empty or "Driver" not in practice_df.columns:
            return work

        # Drop columns that already exist in work (avoid _x/_y conflicts)
        overlap = [c for c in practice_df.columns if c in work.columns and c != "Driver"]
        practice_df = practice_df.drop(columns=overlap, errors="ignore")

        merged = pd.merge(work, practice_df, on="Driver", how="left")

        # Fill missing practice features (driver not in cache) with 0
        new_cols = [c for c in practice_df.columns if c != "Driver"]
        for col in new_cols:
            if col in merged.columns:
                merged[col] = merged[col].fillna(0.0)

        return merged
    except Exception:
        # Practice data unavailable or import failed — continue without it
        return work


# ---------------------------------------------------------------------------
# Chaos features
# ---------------------------------------------------------------------------

def _add_chaos_features(work: pd.DataFrame, year: int, gp_name: str,
                        qualifying_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    Add chaos-related features (safety car rate, grid spread, chaos index)
    as scalar columns (same value for every driver in the race).
    """
    try:
        from chaos_matrix import compute_chaos_index, get_circuit_sc_rate, _compute_grid_spread

        sc_rate = get_circuit_sc_rate(gp_name, use_fastf1=False)
        grid_spread = _compute_grid_spread(qualifying_df)

        # Wind speed from practice cache if available (cross-session avg)
        wind_speed = 0.0
        try:
            from practice_data_ingestion import load_practice_features
            pf = load_practice_features(year, gp_name)
            if pf is not None and "AvgWindSpeed" in pf.columns:
                wind_speed = float(pf["AvgWindSpeed"].mean())
        except Exception:
            pass

        chaos_index = compute_chaos_index(
            gp_name,
            qualifying_df=qualifying_df,
            weather_wind_speed=wind_speed,
            sc_rate_override=sc_rate,
        )

        work = work.copy()
        work["CircuitSCRate"] = sc_rate
        work["GridSpread"] = grid_spread
        work["AvgWindSpeed_chaos"] = wind_speed
        work["ChaosIndex"] = chaos_index

    except Exception:
        # chaos_matrix not available — add zeros
        work = work.copy()
        work["CircuitSCRate"] = 0.0
        work["GridSpread"] = 0.5
        work["AvgWindSpeed_chaos"] = 0.0
        work["ChaosIndex"] = 0.3

    return work


# ---------------------------------------------------------------------------
# Main feature engineering function
# ---------------------------------------------------------------------------

def engineer_winner_features(
    df: pd.DataFrame,
    year: int,
    gp_name: str,
    include_historical: bool = True,
    include_practice: bool = True,
    qualifying_df: Optional[pd.DataFrame] = None,
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Engineer features for winner prediction.

    Feature groups:
      1. Qualifying / grid (always available)
      2. Season-so-far driver & team stats (optional, slower)
      3. Practice telemetry + race pace (optional, from cache)
      4. Chaos features: SC rate, grid spread, chaos index

    Args:
        df: DataFrame from get_winner_prediction_data()
        year: Season year
        gp_name: Grand Prix name
        include_historical: Include season-so-far driver/team stats
        include_practice: Merge practice cache features if available
        qualifying_df: Optional qualifying results for grid spread calculation

    Returns:
        (X, y) — feature DataFrame and IsWinner labels
    """
    if df is None or df.empty:
        return pd.DataFrame(), pd.Series(dtype=int)

    work = df.copy()

    # ── Target label ─────────────────────────────────────────────────────────
    if "IsWinner" not in work.columns:
        if "Position" in work.columns:
            work["IsWinner"] = (work["Position"] == 1).astype(int)
        else:
            work["IsWinner"] = 0

    # ── 1. Grid position ──────────────────────────────────────────────────────
    if "GridPosition" in work.columns:
        work["GridPosition"] = pd.to_numeric(work["GridPosition"], errors="coerce").fillna(20.0)
    else:
        work["GridPosition"] = 20.0
    work["GridPositionNorm"] = work["GridPosition"] / 20.0

    # ── 2. Qualifying times ───────────────────────────────────────────────────
    for q_col in ["Q1", "Q2", "Q3"]:
        if q_col in work.columns:
            try:
                work[f"{q_col}_Seconds"] = (
                    pd.to_timedelta(work[q_col], errors="coerce").dt.total_seconds()
                )
            except Exception:
                work[f"{q_col}_Seconds"] = np.nan

    q_secs_cols = [c for c in work.columns if c.endswith("_Seconds")]
    if q_secs_cols:
        work["BestQualiTime"] = work[q_secs_cols].min(axis=1, skipna=True)
        if work["BestQualiTime"].notna().any():
            fastest = work["BestQualiTime"].min()
            work["QualiTimeGap"] = (work["BestQualiTime"] - fastest).fillna(10.0)
        else:
            work["QualiTimeGap"] = 10.0
    else:
        work["BestQualiTime"] = np.nan
        work["QualiTimeGap"] = 10.0

    # ── 3. Historical driver / team stats ─────────────────────────────────────
    if include_historical:
        # Batch-load previous GPs once (avoids N×M redundant loads)
        try:
            schedule = get_event_schedule(year)
            all_gps = (
                schedule["EventName"].dropna().tolist()
                if not schedule.empty and "EventName" in schedule.columns
                else []
            )
        except Exception:
            all_gps = []

        previous_gps = all_gps[:all_gps.index(gp_name)] if gp_name in all_gps else []

        historical_frames: dict = {}
        for prev_gp in previous_gps:
            try:
                prev_data = get_winner_prediction_data(year, prev_gp)
                if not prev_data.empty:
                    historical_frames[prev_gp] = prev_data
            except Exception:
                continue

        n_prev = len(previous_gps)

        # Driver stats
        unique_drivers = (
            work["Driver"].dropna().unique().tolist() if "Driver" in work.columns else []
        )
        driver_stats_map: dict = {}
        for driver in unique_drivers:
            wins, positions = 0, []
            for gp_df in historical_frames.values():
                if "Driver" not in gp_df.columns:
                    continue
                d_row = gp_df[gp_df["Driver"] == driver]
                if d_row.empty:
                    continue
                if "IsWinner" in d_row.columns:
                    wins += int(d_row["IsWinner"].iloc[0])
                if "Position" in d_row.columns:
                    pos = d_row["Position"].iloc[0]
                    if pd.notna(pos):
                        positions.append(float(pos))
            driver_stats_map[driver] = {
                "win_rate": wins / n_prev if n_prev > 0 else 0.0,
                "avg_position": float(np.mean(positions)) if positions else 20.0,
                "total_wins": wins,
            }

        # Team stats
        unique_teams = (
            work["Team"].dropna().unique().tolist() if "Team" in work.columns else []
        )
        team_stats_map: dict = {}
        for team in unique_teams:
            wins, positions = 0, []
            for gp_df in historical_frames.values():
                if "Team" not in gp_df.columns:
                    continue
                t_rows = gp_df[gp_df["Team"] == team]
                if t_rows.empty:
                    continue
                if "IsWinner" in t_rows.columns and t_rows["IsWinner"].sum() > 0:
                    wins += 1
                if "Position" in t_rows.columns:
                    best_pos = t_rows["Position"].min()
                    if pd.notna(best_pos):
                        positions.append(float(best_pos))
            team_stats_map[team] = {
                "win_rate": wins / n_prev if n_prev > 0 else 0.0,
                "avg_position": float(np.mean(positions)) if positions else 20.0,
                "total_wins": wins,
            }

        def _ds(d: str, key: str) -> float:
            return driver_stats_map.get(d, {}).get(key, 0.0)

        def _ts(t: str, key: str) -> float:
            return team_stats_map.get(t, {}).get(key, 0.0)

        work["DriverWinRate"]    = work.get("Driver", pd.Series()).map(lambda d: _ds(str(d), "win_rate"))
        work["DriverAvgPosition"]= work.get("Driver", pd.Series()).map(lambda d: _ds(str(d), "avg_position"))
        work["DriverTotalWins"]  = work.get("Driver", pd.Series()).map(lambda d: _ds(str(d), "total_wins"))
        work["TeamWinRate"]      = work.get("Team",   pd.Series()).map(lambda t: _ts(str(t), "win_rate"))
        work["TeamAvgPosition"]  = work.get("Team",   pd.Series()).map(lambda t: _ts(str(t), "avg_position"))
        work["TeamTotalWins"]    = work.get("Team",   pd.Series()).map(lambda t: _ts(str(t), "total_wins"))
    else:
        work["DriverWinRate"]     = 0.0
        work["DriverAvgPosition"] = 20.0
        work["DriverTotalWins"]   = 0
        work["TeamWinRate"]       = 0.0
        work["TeamAvgPosition"]   = 20.0
        work["TeamTotalWins"]     = 0

    # ── 4. Practice features (from cache, optional) ───────────────────────────
    if include_practice:
        work = _merge_practice_features(work, year, gp_name)

    # ── 5. Chaos features ─────────────────────────────────────────────────────
    work = _add_chaos_features(work, year, gp_name, qualifying_df=qualifying_df)

    # ── 6. Categorical encoding ───────────────────────────────────────────────
    categorical_cols: List[str] = [c for c in ["Driver", "Team"] if c in work.columns]
    if categorical_cols:
        enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        encoded = enc.fit_transform(work[categorical_cols].fillna("Unknown"))
        encoded_cols = enc.get_feature_names_out(categorical_cols)
        encoded_df = pd.DataFrame(encoded, columns=encoded_cols, index=work.index)
        work = pd.concat(
            [work.drop(columns=categorical_cols, errors="ignore"), encoded_df], axis=1
        )

    # ── 7. Select final feature columns ──────────────────────────────────────
    exclude_cols = [
        "IsWinner", "Position", "Points", "Status", "Time", "DriverNumber", "FullName",
        "Q1", "Q2", "Q3", "GridPosition_Quali", "GridPosition_Race", "Position_Race",
    ]
    feature_cols = [
        c for c in work.columns
        if c not in exclude_cols
        and (not c.startswith("Position") or c == "GridPosition")
    ]

    X = work[feature_cols].select_dtypes(include=[np.number]).fillna(0.0)
    y = work["IsWinner"].astype(int)

    return X, y
