import os
import warnings
from typing import List, Optional

import pandas as pd

import fastf1


def _enable_cache() -> str:
	cache_dir = os.path.join(os.getcwd(), "fastf1_cache")
	os.makedirs(cache_dir, exist_ok=True)
	fastf1.Cache.enable_cache(cache_dir)
	return cache_dir


def get_event_schedule(year: int) -> pd.DataFrame:
	_enable_cache()
	try:
		return fastf1.get_event_schedule(year, include_testing=False)
	except Exception:
		return pd.DataFrame()


def load_session_with_weather(year: int, gp_name: str, session_code: str) -> pd.DataFrame:
	"""Load a FastF1 session and merge nearest weather snapshot per lap start time.
	Returns a cleaned DataFrame with key lap columns and weather columns when present.
	"""
	_enable_cache()
	warnings.filterwarnings("ignore", category=RuntimeWarning)
	warnings.filterwarnings("ignore", category=UserWarning)

	s = fastf1.get_session(year, gp_name, session_code)
	s.load(telemetry=False, weather=True, messages=False)

	laps: pd.DataFrame = s.laps
	if laps is None or laps.empty:
		return pd.DataFrame()

	weather: pd.DataFrame = getattr(s, "weather_data", pd.DataFrame())
	weather = weather.copy()
	if not weather.empty:
		keep_weather_cols = [c for c in ["Time", "TrackTemp", "AirTemp", "Humidity"] if c in weather.columns]
		weather = weather[keep_weather_cols].sort_values("Time").reset_index(drop=True)

	if "LapStartTime" not in laps.columns and "Time" in laps.columns:
		laps["LapStartTime"] = laps["Time"]

	selected_lap_cols = [
		"Driver", "Team", "LapNumber", "LapTime", "Sector1Time", "Sector2Time", "Sector3Time",
		"Compound", "TyreLife", "LapStartTime"
	]
	available_lap_cols = [c for c in selected_lap_cols if c in laps.columns]
	laps_sel = laps[available_lap_cols].copy().sort_values("LapStartTime").reset_index(drop=True)

	if not weather.empty and "Time" in weather.columns:
		joined = pd.merge_asof(
			laps_sel, weather, left_on="LapStartTime", right_on="Time", direction="nearest"
		)
		if "Time" in joined.columns:
			joined = joined.drop(columns=["Time"])
	else:
		joined = laps_sel

	return joined


def get_session_data(year: int, gp_name: str, session_type: str, include_sprint: bool = False) -> pd.DataFrame:
	"""Get session data for a given event.

	- session_type: typical values 'Q' (Quali) or 'R' (Race). For sprints, also 'SQ' (Sprint Quali) and 'SS' (Sprint Shootout/Race) depending on year nomenclature.
	- include_sprint: if True and session_type is 'Q' or 'R', will additionally try to fetch sprint-related sessions and append with a column SessionPhase.
	"""
	base = load_session_with_weather(year, gp_name, session_type)
	if base.empty or not include_sprint:
		if not base.empty:
			base["SessionPhase"] = session_type
		return base

	# Attempt to load sprint sessions where applicable; names vary by season.
	sprint_codes: List[str] = ["SQ", "SS", "SR", "S"]
	frames: List[pd.DataFrame] = []
	for code in sprint_codes:
		try:
			df = load_session_with_weather(year, gp_name, code)
			if not df.empty:
				df = df.copy()
				df["SessionPhase"] = code
				frames.append(df)
		except Exception:
			pass

	base = base.copy()
	base["SessionPhase"] = session_type
	frames.insert(0, base)

	if frames:
		return pd.concat(frames, ignore_index=True, sort=False)
	return base


def get_race_results(year: int, gp_name: str) -> pd.DataFrame:
	"""Load race results (final positions) for a given Grand Prix.
	Returns a DataFrame with Driver, Team, Position, Points, and other race result columns.
	"""
	_enable_cache()
	warnings.filterwarnings("ignore", category=RuntimeWarning)
	warnings.filterwarnings("ignore", category=UserWarning)

	try:
		s = fastf1.get_session(year, gp_name, "R")
		s.load(telemetry=False, weather=False, messages=False)
		
		results: pd.DataFrame = s.results
		if results is None or results.empty:
			return pd.DataFrame()
		
		# Select key columns
		selected_cols = [
			"DriverNumber", "Abbreviation", "FullName", "TeamName", "Position", "Points",
			"GridPosition", "Status", "Time"
		]
		available_cols = [c for c in selected_cols if c in results.columns]
		results_sel = results[available_cols].copy()
		
		# Rename for consistency
		if "Abbreviation" in results_sel.columns:
			results_sel = results_sel.rename(columns={"Abbreviation": "Driver"})
		if "TeamName" in results_sel.columns:
			results_sel = results_sel.rename(columns={"TeamName": "Team"})
		
		# Mark winner (Position == 1)
		results_sel["IsWinner"] = (results_sel["Position"] == 1).astype(int)
		
		return results_sel
	except Exception:
		return pd.DataFrame()


def get_qualifying_results(year: int, gp_name: str) -> pd.DataFrame:
	"""Load qualifying results (grid positions) for a given Grand Prix.
	Returns a DataFrame with Driver, Team, Position, Q1/Q2/Q3 times.
	"""
	_enable_cache()
	warnings.filterwarnings("ignore", category=RuntimeWarning)
	warnings.filterwarnings("ignore", category=UserWarning)

	try:
		s = fastf1.get_session(year, gp_name, "Q")
		s.load(telemetry=False, weather=False, messages=False)
		
		results: pd.DataFrame = s.results
		if results is None or results.empty:
			return pd.DataFrame()
		
		# Select key columns
		selected_cols = [
			"DriverNumber", "Abbreviation", "FullName", "TeamName", "Position",
			"Q1", "Q2", "Q3"
		]
		available_cols = [c for c in selected_cols if c in results.columns]
		results_sel = results[available_cols].copy()
		
		# Rename for consistency
		if "Abbreviation" in results_sel.columns:
			results_sel = results_sel.rename(columns={"Abbreviation": "Driver"})
		if "TeamName" in results_sel.columns:
			results_sel = results_sel.rename(columns={"TeamName": "Team"})
		if "Position" in results_sel.columns:
			results_sel = results_sel.rename(columns={"Position": "GridPosition"})
		
		return results_sel
	except Exception:
		return pd.DataFrame()


def get_winner_prediction_data(year: int, gp_name: str) -> pd.DataFrame:
	"""Get combined data for winner prediction: qualifying results + race results.
	Returns a DataFrame with one row per driver, combining qualifying and race data.
	"""
	qualifying = get_qualifying_results(year, gp_name)
	race_results = get_race_results(year, gp_name)
	
	if qualifying.empty and race_results.empty:
		return pd.DataFrame()
	
	# Merge qualifying and race results on Driver
	if not qualifying.empty and not race_results.empty:
		merged = pd.merge(
			qualifying, race_results,
			on="Driver", how="outer", suffixes=("_Quali", "_Race")
		)
		# Fill missing values
		if "GridPosition" not in merged.columns and "GridPosition_Quali" in merged.columns:
			merged["GridPosition"] = merged["GridPosition_Quali"].fillna(merged.get("GridPosition_Race", pd.Series()))
		if "Position" not in merged.columns and "Position_Race" in merged.columns:
			merged["Position"] = merged["Position_Race"]
		if "IsWinner" not in merged.columns:
			merged["IsWinner"] = (merged.get("Position", pd.Series()) == 1).astype(int)
		if "Team" not in merged.columns:
			team_cols = [c for c in merged.columns if "Team" in c]
			if team_cols:
				merged["Team"] = merged[team_cols[0]]
		return merged
	elif not race_results.empty:
		return race_results
	else:
		return qualifying
