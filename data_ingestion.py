import os
import warnings
from typing import List

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


def get_race_results(year: int, gp_name: str) -> pd.DataFrame:
	"""Load race results (final positions) for a given Grand Prix."""
	_enable_cache()
	warnings.filterwarnings("ignore", category=RuntimeWarning)
	warnings.filterwarnings("ignore", category=UserWarning)

	try:
		s = fastf1.get_session(year, gp_name, "R")
		s.load(laps=False, telemetry=False, weather=False, messages=False)

		results: pd.DataFrame = s.results
		if results is None or results.empty:
			return pd.DataFrame()

		selected_cols = [
			"DriverNumber", "Abbreviation", "FullName", "TeamName", "Position", "Points",
			"GridPosition", "Status", "Time"
		]
		available_cols = [c for c in selected_cols if c in results.columns]
		results_sel = results[available_cols].copy()

		if "Abbreviation" in results_sel.columns:
			results_sel = results_sel.rename(columns={"Abbreviation": "Driver"})
		if "TeamName" in results_sel.columns:
			results_sel = results_sel.rename(columns={"TeamName": "Team"})

		results_sel["IsWinner"] = (results_sel["Position"] == 1).astype(int)
		return results_sel
	except Exception:
		return pd.DataFrame()


def get_qualifying_results(year: int, gp_name: str) -> pd.DataFrame:
	"""Load qualifying results (grid positions) for a given Grand Prix."""
	_enable_cache()
	warnings.filterwarnings("ignore", category=RuntimeWarning)
	warnings.filterwarnings("ignore", category=UserWarning)

	try:
		s = fastf1.get_session(year, gp_name, "Q")
		s.load(laps=False, telemetry=False, weather=False, messages=False)

		results: pd.DataFrame = s.results
		if results is None or results.empty:
			return pd.DataFrame()

		selected_cols = [
			"DriverNumber", "Abbreviation", "FullName", "TeamName", "Position",
			"Q1", "Q2", "Q3"
		]
		available_cols = [c for c in selected_cols if c in results.columns]
		results_sel = results[available_cols].copy()

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
	"""Get combined data for winner prediction: qualifying results + race results."""
	qualifying = get_qualifying_results(year, gp_name)
	race_results = get_race_results(year, gp_name)

	if qualifying.empty and race_results.empty:
		return pd.DataFrame()

	if not qualifying.empty and not race_results.empty:
		merged = pd.merge(
			qualifying, race_results,
			on="Driver", how="outer", suffixes=("_Quali", "_Race")
		)
		if "GridPosition" not in merged.columns and "GridPosition_Quali" in merged.columns:
			merged["GridPosition"] = merged["GridPosition_Quali"].fillna(
				merged.get("GridPosition_Race", pd.Series())
			)
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
