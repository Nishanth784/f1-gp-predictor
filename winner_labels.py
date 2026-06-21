from typing import Optional
import warnings

import pandas as pd

from data_ingestion import get_race_results


def extract_winner_labels(df_race: pd.DataFrame, 
                         driver_col: str = "Driver",
                         position_col: str = "Position",
                         status_col: Optional[str] = "Status") -> pd.DataFrame:
	"""Extract winner labels from raw race session DataFrame.
	
	This function takes a race session DataFrame (from data_ingestion) and generates
	winner labels based on final race positions. The winner is the driver classified
	as P1 (Position == 1) in the race results.
	
	Args:
		df_race: Raw race session DataFrame from data_ingestion. Should contain:
			- Driver column (driver abbreviation/code)
			- Position column (final race position, 1 = winner)
			- Optional: Status column (to filter DNFs)
		driver_col: Name of column containing driver identifiers
		position_col: Name of column containing final race positions
		status_col: Name of column containing race status (None to skip DNF filtering)
	
	Returns:
		DataFrame with columns:
		- Driver: Driver identifier (abbreviation/code)
		- IsWinner: 1 if driver finished P1 (winner), 0 otherwise
	
	Notes:
		- DNFs (Did Not Finish) are handled safely: drivers with invalid positions
		  or DNF status are marked as IsWinner=0
		- Driver codes are preserved as-is from the input DataFrame to ensure
		  consistency with existing feature encoding
		- If Position column is missing, all drivers are marked as IsWinner=0
	"""
	if df_race is None or df_race.empty:
		return pd.DataFrame(columns=[driver_col, "IsWinner"])
	
	# Validate required columns
	if driver_col not in df_race.columns:
		raise ValueError(f"Missing required column: {driver_col}")
	
	if position_col not in df_race.columns:
		# If no position column, return all drivers with IsWinner=0
		warnings.warn(f"Position column '{position_col}' not found. All drivers marked as non-winners.")
		drivers = df_race[driver_col].dropna().unique()
		return pd.DataFrame({
			driver_col: drivers,
			"IsWinner": [0] * len(drivers)
		})
	
	# Get unique drivers (one row per driver)
	# If multiple rows per driver, take the one with valid position
	results = []
	
	for driver in df_race[driver_col].dropna().unique():
		driver_data = df_race[df_race[driver_col] == driver]
		
		# Get position for this driver
		positions = driver_data[position_col].dropna()
		
		if len(positions) == 0:
			# No valid position, mark as non-winner
			results.append({driver_col: driver, "IsWinner": 0})
			continue
		
		# Take the first valid position (should be only one per driver in race results)
		position = positions.iloc[0]
		
		# Check for DNF status if status column exists
		is_dnf = False
		if status_col and status_col in driver_data.columns:
			statuses = driver_data[status_col].dropna().astype(str).str.upper()
			# Common DNF indicators
			dnf_indicators = ["DNF", "DSQ", "DNS", "NC", "NOT CLASSIFIED", "DISQUALIFIED", "DID NOT START"]
			for status in statuses:
				if any(ind in status for ind in dnf_indicators):
					is_dnf = True
					break
		
		# Winner is P1 and not DNF
		if pd.notna(position) and float(position) == 1.0 and not is_dnf:
			is_winner = 1
		else:
			is_winner = 0
		
		results.append({driver_col: driver, "IsWinner": is_winner})
	
	if not results:
		return pd.DataFrame(columns=[driver_col, "IsWinner"])
	
	return pd.DataFrame(results)


def get_winner_for_race(year: int, gp_name: str) -> str:
	"""Get the winner driver code for a specific race.
	
	This helper function retrieves the race results and returns the driver code
	(abbreviation) of the race winner (P1 finisher).
	
	Args:
		year: Year of the race (e.g., 2023)
		gp_name: Name of the Grand Prix (e.g., "Monaco")
	
	Returns:
		Driver code (abbreviation) of the race winner, or empty string if not found
	
	Examples:
		>>> get_winner_for_race(2023, "Monaco")
		'VER'
		>>> get_winner_for_race(2023, "Bahrain")
		'VER'
	"""
	warnings.filterwarnings("ignore", category=RuntimeWarning)
	warnings.filterwarnings("ignore", category=UserWarning)
	
	try:
		# Get race results
		race_results = get_race_results(year, gp_name)
		
		if race_results.empty:
			return ""
		
		# Check if we have Position and Driver columns
		if "Position" not in race_results.columns or "Driver" not in race_results.columns:
			return ""
		
		# Find P1 (winner)
		winner_row = race_results[race_results["Position"] == 1]
		
		if winner_row.empty:
			return ""
		
		# Get driver code
		driver = winner_row["Driver"].iloc[0]
		
		if pd.isna(driver):
			return ""
		
		return str(driver)
	except Exception:
		return ""


def get_winner_labels_from_session(year: int, gp_name: str,
                                   session_type: str = "R") -> pd.DataFrame:
	"""Get winner labels for a race using race results.

	Args:
		year: Year of the race
		gp_name: Name of the Grand Prix
		session_type: Ignored (kept for API compatibility) — always uses race results

	Returns:
		DataFrame with Driver and IsWinner columns
	"""
	try:
		race_results = get_race_results(year, gp_name)
		if race_results.empty:
			return pd.DataFrame(columns=["Driver", "IsWinner"])
		return extract_winner_labels(race_results)
	except Exception:
		return pd.DataFrame(columns=["Driver", "IsWinner"])

