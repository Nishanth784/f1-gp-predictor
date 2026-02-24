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
	if include_historical:
		driver_stats_list = []
		team_stats_list = []
		
		for idx, row in work.iterrows():
			driver = str(row.get("Driver", ""))
			team = str(row.get("Team", ""))
			
			if driver:
				driver_stats = calculate_driver_stats(driver, year, gp_name)
				driver_stats_list.append(driver_stats)
			else:
				driver_stats_list.append({"win_rate": 0.0, "avg_position": 20.0, "total_wins": 0, "total_races": 0})
			
			if team:
				team_stats = calculate_team_stats(team, year, gp_name)
				team_stats_list.append(team_stats)
			else:
				team_stats_list.append({"win_rate": 0.0, "avg_position": 20.0, "total_wins": 0, "total_races": 0})
		
		driver_df = pd.DataFrame(driver_stats_list, index=work.index)
		team_df = pd.DataFrame(team_stats_list, index=work.index)
		
		work["DriverWinRate"] = driver_df["win_rate"]
		work["DriverAvgPosition"] = driver_df["avg_position"]
		work["DriverTotalWins"] = driver_df["total_wins"]
		work["TeamWinRate"] = team_df["win_rate"]
		work["TeamAvgPosition"] = team_df["avg_position"]
		work["TeamTotalWins"] = team_df["total_wins"]
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

