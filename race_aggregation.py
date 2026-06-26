from typing import Optional, Dict, List
import warnings

import numpy as np
import pandas as pd


def calculate_degradation_slope(lap_times: pd.Series, lap_numbers: pd.Series) -> float:
	"""Calculate degradation slope using linear regression of lap time vs lap number.
	
	Args:
		lap_times: Series of lap times (in seconds)
		lap_numbers: Series of lap numbers
	
	Returns:
		Slope coefficient (positive = getting slower, negative = getting faster)
	"""
	if len(lap_times) < 2 or len(lap_numbers) < 2:
		return 0.0
	
	# Remove NaN values
	mask = lap_times.notna() & lap_numbers.notna()
	if mask.sum() < 2:
		return 0.0
	
	lap_times_clean = lap_times[mask]
	lap_numbers_clean = lap_numbers[mask]
	
	if len(lap_times_clean) < 2:
		return 0.0
	
	# Simple linear regression: y = mx + b
	# m = slope = (n*sum(xy) - sum(x)*sum(y)) / (n*sum(x^2) - sum(x)^2)
	x = lap_numbers_clean.values
	y = lap_times_clean.values
	
	n = len(x)
	sum_x = np.sum(x)
	sum_y = np.sum(y)
	sum_xy = np.sum(x * y)
	sum_x2 = np.sum(x * x)
	
	denominator = n * sum_x2 - sum_x * sum_x
	if abs(denominator) < 1e-10:
		return 0.0
	
	slope = (n * sum_xy - sum_x * sum_y) / denominator
	return float(slope)


def aggregate_laps_to_race(df_laps: pd.DataFrame, 
                           predicted_lap_time_col: str = "PredictedLapTime",
                           driver_col: str = "Driver",
                           lap_number_col: str = "LapNumber",
                           tyre_col: str = "Compound",
                           track_temp_col: Optional[str] = "TrackTemp",
                           air_temp_col: Optional[str] = "AirTemp") -> pd.DataFrame:
	"""Aggregate lap-level predictions and features into race-level driver summaries.
	
	This function takes lap-level data (one row per lap per driver) and aggregates it
	into race-level summaries (one row per driver per race).
	
	Args:
		df_laps: DataFrame with lap-level data. Must contain:
			- Driver column (driver identifier)
			- LapNumber column (lap number)
			- PredictedLapTime column (predicted lap time in seconds)
			- Optional: Compound (tyre compound), TrackTemp, AirTemp
		predicted_lap_time_col: Name of column containing predicted lap times
		driver_col: Name of column containing driver identifiers
		lap_number_col: Name of column containing lap numbers
		tyre_col: Name of column containing tyre compounds
		track_temp_col: Name of column containing track temperature (None to skip)
		air_temp_col: Name of column containing air temperature (None to skip)
	
	Returns:
		DataFrame with one row per driver, containing aggregated features:
		- Driver: Driver identifier
		- mean_predicted_lap: Mean predicted lap time
		- median_predicted_lap: Median predicted lap time
		- best_predicted_lap: Best (minimum) predicted lap time
		- lap_time_std: Standard deviation of predicted lap times
		- consistency_index: 1 / (1 + std) - higher = more consistent
		- degradation_slope: Linear regression slope of lap time vs lap number
		- tyre_SOFT_count: Count of laps on SOFT compound
		- tyre_MEDIUM_count: Count of laps on MEDIUM compound
		- tyre_HARD_count: Count of laps on HARD compound
		- average_track_temp: Average track temperature (if available)
		- average_air_temp: Average air temperature (if available)
		- total_laps: Total number of laps completed
	
	Raises:
		ValueError: If required columns are missing
	"""
	if df_laps is None or df_laps.empty:
		return pd.DataFrame()
	
	# Validate required columns
	required_cols = [driver_col, lap_number_col, predicted_lap_time_col]
	missing_cols = [col for col in required_cols if col not in df_laps.columns]
	if missing_cols:
		raise ValueError(f"Missing required columns: {missing_cols}")
	
	# Group by driver
	grouped = df_laps.groupby(driver_col, dropna=False)
	
	results = []
	
	for driver, group in grouped:
		if pd.isna(driver):
			continue
		
		# Get predicted lap times (remove NaN)
		predicted_laps = group[predicted_lap_time_col].dropna()
		
		if len(predicted_laps) == 0:
			# Skip drivers with no valid predictions
			continue
		
		# Basic statistics
		mean_pred = float(predicted_laps.mean())
		median_pred = float(predicted_laps.median())
		best_pred = float(predicted_laps.min())
		std_pred = float(predicted_laps.std())
		
		# Consistency index: 1 / (1 + std)
		# Higher values = more consistent (lower std)
		consistency_index = 1.0 / (1.0 + std_pred) if std_pred >= 0 else 1.0
		
		# Degradation slope
		if len(predicted_laps) >= 2:
			# Get lap numbers for the same indices as predicted_laps
			# Use reindex to align indices safely
			lap_numbers_for_predicted = group[lap_number_col].reindex(predicted_laps.index)
			
			# Create aligned series (both should have same index now)
			aligned_lap_times = predicted_laps.copy()
			aligned_lap_numbers = lap_numbers_for_predicted.copy()
			
			# Remove rows where either is NaN
			mask = aligned_lap_times.notna() & aligned_lap_numbers.notna()
			if mask.sum() >= 2:
				degradation_slope = calculate_degradation_slope(
					aligned_lap_times[mask],
					aligned_lap_numbers[mask]
				)
			else:
				degradation_slope = 0.0
		else:
			degradation_slope = 0.0
		
		# Tyre compound counts
		tyre_counts = {"SOFT": 0, "MEDIUM": 0, "HARD": 0}
		if tyre_col in group.columns:
			tyres = group[tyre_col].dropna().astype(str).str.upper()
			for compound in ["SOFT", "MEDIUM", "HARD"]:
				tyre_counts[compound] = int((tyres == compound).sum())
		
		# Temperature averages
		avg_track_temp = np.nan
		if track_temp_col and track_temp_col in group.columns:
			track_temps = group[track_temp_col].dropna()
			if len(track_temps) > 0:
				avg_track_temp = float(track_temps.mean())
		
		avg_air_temp = np.nan
		if air_temp_col and air_temp_col in group.columns:
			air_temps = group[air_temp_col].dropna()
			if len(air_temps) > 0:
				avg_air_temp = float(air_temps.mean())
		
		# Total laps
		total_laps = len(group)
		
		results.append({
			driver_col: driver,
			"mean_predicted_lap": mean_pred,
			"median_predicted_lap": median_pred,
			"best_predicted_lap": best_pred,
			"lap_time_std": std_pred,
			"consistency_index": consistency_index,
			"degradation_slope": degradation_slope,
			"tyre_SOFT_count": tyre_counts["SOFT"],
			"tyre_MEDIUM_count": tyre_counts["MEDIUM"],
			"tyre_HARD_count": tyre_counts["HARD"],
			"average_track_temp": avg_track_temp,
			"average_air_temp": avg_air_temp,
			"total_laps": total_laps,
		})
	
	if not results:
		return pd.DataFrame()
	
	result_df = pd.DataFrame(results)
	return result_df


def aggregate_with_actual_results(df_laps: pd.DataFrame,
                                  df_results: Optional[pd.DataFrame] = None,
                                  predicted_lap_time_col: str = "PredictedLapTime",
                                  driver_col: str = "Driver",
                                  lap_number_col: str = "LapNumber",
                                  results_driver_col: Optional[str] = None,
                                  results_position_col: Optional[str] = None) -> pd.DataFrame:
	"""Aggregate lap-level data and optionally merge with race results.
	
	This is a convenience function that aggregates lap data and optionally merges
	with race results (e.g., final position, points).
	
	Args:
		df_laps: Lap-level DataFrame (see aggregate_laps_to_race)
		df_results: Optional DataFrame with race results (one row per driver)
		predicted_lap_time_col: Name of predicted lap time column
		driver_col: Name of driver column in df_laps
		lap_number_col: Name of lap number column
		results_driver_col: Name of driver column in df_results (default: same as driver_col)
		results_position_col: Name of position column in df_results (e.g., "Position")
	
	Returns:
		DataFrame with aggregated features plus any columns from df_results
	"""
	aggregated = aggregate_laps_to_race(
		df_laps,
		predicted_lap_time_col=predicted_lap_time_col,
		driver_col=driver_col,
		lap_number_col=lap_number_col
	)
	
	if df_results is None or df_results.empty or aggregated.empty:
		return aggregated
	
	# Merge with results
	results_driver = results_driver_col or driver_col
	
	if results_driver not in df_results.columns:
		return aggregated
	
	merged = pd.merge(
		aggregated,
		df_results,
		left_on=driver_col,
		right_on=results_driver,
		how="left"
	)
	
	return merged

