from typing import Tuple, List, Optional
import warnings

import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder

from data_ingestion import get_winner_prediction_data, get_event_schedule


def calculate_driver_stats(driver: str, year: int, current_gp: str) -> dict:
	"""Calculate historical statistics for a driver up to (but not including) the current GP.
	Returns dict with win_rate, avg_position, total_wins, total_races.
	"""
	warnings.filterwarnings("ignore", category=RuntimeWarning)
	warnings.filterwarnings("ignore", category=UserWarning)
	
	stats = {"win_rate": 0.0, "avg_position": 20.0, "total_wins": 0, "total_races": 0}
	
	try:
		schedule = get_event_schedule(year)
		if schedule.empty or "EventName" not in schedule.columns:
			return stats
		
		# Get all GPs before current GP
		all_gps = schedule["EventName"].dropna().tolist()
		if current_gp not in all_gps:
			return stats
		
		current_idx = all_gps.index(current_gp)
		previous_gps = all_gps[:current_idx]
		
		wins = 0
		positions = []
		
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
		if len(previous_gps) > 0:
			stats["win_rate"] = wins / len(previous_gps)
		if positions:
			stats["avg_position"] = np.mean(positions)
	except Exception:
		pass
	
	return stats


def calculate_team_stats(team: str, year: int, current_gp: str) -> dict:
	"""Calculate historical statistics for a team up to (but not including) the current GP.
	Returns dict with win_rate, avg_position, total_wins, total_races.
	"""
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
		
		wins = 0
		positions = []
		
		for gp in previous_gps:
			try:
				race_results = get_winner_prediction_data(year, gp)
				if not race_results.empty and "Team" in race_results.columns:
					team_data = race_results[race_results["Team"] == team]
					if not team_data.empty:
						# Check if any driver from this team won
						if "IsWinner" in team_data.columns:
							if team_data["IsWinner"].sum() > 0:
								wins += 1
						# Average position of team's best driver
						if "Position" in team_data.columns:
							best_pos = team_data["Position"].min()
							if pd.notna(best_pos):
								positions.append(float(best_pos))
			except Exception:
				continue
		
		stats["total_races"] = len(previous_gps)
		stats["total_wins"] = wins
		if len(previous_gps) > 0:
			stats["win_rate"] = wins / len(previous_gps)
		if positions:
			stats["avg_position"] = np.mean(positions)
	except Exception:
		pass
	
	return stats


def engineer_winner_features(df: pd.DataFrame, year: int, gp_name: str, include_historical: bool = True) -> Tuple[pd.DataFrame, pd.Series]:
	"""Engineer features for winner prediction.
	
	Args:
		df: DataFrame with race/qualifying results (from get_winner_prediction_data)
		year: Year of the race
		gp_name: Name of the Grand Prix
		include_historical: Whether to include historical driver/team stats (slower but more accurate)
	
	Returns:
		Tuple of (X: DataFrame with features, y: Series with IsWinner labels)
	"""
	if df is None or df.empty:
		return pd.DataFrame(), pd.Series(dtype=int)
	
	work = df.copy()
	
	# Ensure IsWinner column exists
	if "IsWinner" not in work.columns:
		if "Position" in work.columns:
			work["IsWinner"] = (work["Position"] == 1).astype(int)
		else:
			work["IsWinner"] = 0
	
	# Grid position (qualifying position) - key feature
	if "GridPosition" in work.columns:
		work["GridPosition"] = pd.to_numeric(work["GridPosition"], errors="coerce").fillna(20.0)
	else:
		work["GridPosition"] = 20.0
	
	# Normalize grid position (1 = pole, higher = worse)
	work["GridPositionNorm"] = work["GridPosition"] / 20.0  # Normalize to 0-1 scale
	
	# Qualifying times (if available)
	for q_col in ["Q1", "Q2", "Q3"]:
		if q_col in work.columns:
			# Convert timedelta to seconds
			try:
				work[f"{q_col}_Seconds"] = pd.to_timedelta(work[q_col], errors="coerce").dt.total_seconds()
			except Exception:
				work[f"{q_col}_Seconds"] = np.nan
	
	# Best qualifying time
	q_cols = [c for c in work.columns if c.endswith("_Seconds")]
	if q_cols:
		work["BestQualiTime"] = work[q_cols].min(axis=1, skipna=True)
		# Normalize best quali time (relative to fastest)
		if work["BestQualiTime"].notna().any():
			fastest = work["BestQualiTime"].min()
			work["QualiTimeGap"] = (work["BestQualiTime"] - fastest).fillna(10.0)
		else:
			work["QualiTimeGap"] = 10.0
	else:
		work["BestQualiTime"] = np.nan
		work["QualiTimeGap"] = 10.0
	
	# Historical driver and team stats (if enabled)
	# Optimized: pre-load each historical GP once, then batch-compute all driver/team stats.
	# This avoids the original O(drivers × prev_gps) load pattern (was 30× redundant).
	if include_historical:
		# 1. Find all GPs that happened before this one
		try:
			schedule = get_event_schedule(year)
			all_gps = schedule["EventName"].dropna().tolist() if not schedule.empty and "EventName" in schedule.columns else []
		except Exception:
			all_gps = []

		if gp_name in all_gps:
			previous_gps = all_gps[:all_gps.index(gp_name)]
		else:
			previous_gps = []

		# 2. Load each previous GP exactly once
		historical_frames: dict = {}
		for prev_gp in previous_gps:
			try:
				prev_data = get_winner_prediction_data(year, prev_gp)
				if not prev_data.empty:
					historical_frames[prev_gp] = prev_data
			except Exception:
				continue

		n_prev = len(previous_gps)

		# 3. Batch-compute driver stats
		unique_drivers = work["Driver"].dropna().unique().tolist() if "Driver" in work.columns else []
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
				"total_races": n_prev,
			}

		# 4. Batch-compute team stats
		unique_teams = work["Team"].dropna().unique().tolist() if "Team" in work.columns else []
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
				"total_races": n_prev,
			}

		# 5. Apply to dataframe
		_def_d = {"win_rate": 0.0, "avg_position": 20.0, "total_wins": 0}
		_def_t = {"win_rate": 0.0, "avg_position": 20.0, "total_wins": 0}

		def _dstat(d: str, key: str):
			return driver_stats_map.get(d, _def_d).get(key, _def_d.get(key, 0))

		def _tstat(t: str, key: str):
			return team_stats_map.get(t, _def_t).get(key, _def_t.get(key, 0))

		work["DriverWinRate"] = work.get("Driver", pd.Series()).map(lambda d: _dstat(str(d), "win_rate"))
		work["DriverAvgPosition"] = work.get("Driver", pd.Series()).map(lambda d: _dstat(str(d), "avg_position"))
		work["DriverTotalWins"] = work.get("Driver", pd.Series()).map(lambda d: _dstat(str(d), "total_wins"))
		work["TeamWinRate"] = work.get("Team", pd.Series()).map(lambda t: _tstat(str(t), "win_rate"))
		work["TeamAvgPosition"] = work.get("Team", pd.Series()).map(lambda t: _tstat(str(t), "avg_position"))
		work["TeamTotalWins"] = work.get("Team", pd.Series()).map(lambda t: _tstat(str(t), "total_wins"))
	else:
		work["DriverWinRate"] = 0.0
		work["DriverAvgPosition"] = 20.0
		work["DriverTotalWins"] = 0
		work["TeamWinRate"] = 0.0
		work["TeamAvgPosition"] = 20.0
		work["TeamTotalWins"] = 0
	
	# Categorical encoding
	categorical_cols: List[str] = [c for c in ["Driver", "Team"] if c in work.columns]
	if categorical_cols:
		enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
		encoded = enc.fit_transform(work[categorical_cols].fillna("Unknown"))
		encoded_cols = enc.get_feature_names_out(categorical_cols)
		encoded_df = pd.DataFrame(encoded, columns=encoded_cols, index=work.index)
		work = pd.concat([work.drop(columns=categorical_cols, errors="ignore"), encoded_df], axis=1)
	
	# Select feature columns (exclude target and metadata)
	exclude_cols = [
		"IsWinner", "Position", "Points", "Status", "Time", "DriverNumber", "FullName",
		"Q1", "Q2", "Q3", "GridPosition_Quali", "GridPosition_Race", "Position_Race"
	]
	feature_cols = [
		c for c in work.columns
		if c not in exclude_cols and not c.startswith("Position") or c == "GridPosition"
	]
	
	X = work[feature_cols].select_dtypes(include=[np.number]).fillna(0.0)
	y = work["IsWinner"].astype(int)
	
	return X, y

