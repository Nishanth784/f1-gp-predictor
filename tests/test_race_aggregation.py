import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np

from race_aggregation import aggregate_laps_to_race


def test_aggregation_produces_one_row_per_driver():
	"""Test that aggregation produces exactly one row per driver."""
	# Create lap-level data with multiple laps per driver
	data = {
		"Driver": ["VER", "VER", "VER", "HAM", "HAM", "NOR", "NOR"],
		"LapNumber": [1, 2, 3, 1, 2, 1, 2],
		"PredictedLapTime": [89.5, 89.8, 90.2, 90.0, 90.5, 91.0, 91.2],
		"Compound": ["SOFT", "SOFT", "MEDIUM", "SOFT", "SOFT", "MEDIUM", "MEDIUM"],
		"TrackTemp": [35.0, 36.0, 37.0, 35.0, 36.0, 35.0, 36.0],
		"AirTemp": [25.0, 25.5, 26.0, 25.0, 25.5, 25.0, 25.5],
	}
	df_laps = pd.DataFrame(data)
	
	result = aggregate_laps_to_race(
		df_laps,
		predicted_lap_time_col="PredictedLapTime",
		driver_col="Driver",
		lap_number_col="LapNumber",
		tyre_col="Compound",
		track_temp_col="TrackTemp",
		air_temp_col="AirTemp"
	)
	
	# Should have exactly 3 rows (one per driver)
	assert len(result) == 3, f"Expected 3 drivers, got {len(result)}"
	assert set(result["Driver"].tolist()) == {"VER", "HAM", "NOR"}, "Driver names should match"
	
	# Each driver should appear exactly once
	assert result["Driver"].value_counts().max() == 1, "Each driver should appear exactly once"


def test_aggregation_required_columns():
	"""Test that aggregation requires Driver, LapNumber, and PredictedLapTime columns."""
	# Missing PredictedLapTime
	data = {
		"Driver": ["VER"],
		"LapNumber": [1],
	}
	df_laps = pd.DataFrame(data)
	
	try:
		result = aggregate_laps_to_race(df_laps)
		assert False, "Should raise ValueError for missing PredictedLapTime"
	except ValueError:
		pass  # Expected


def test_aggregation_statistics():
	"""Test that aggregated statistics are calculated correctly."""
	data = {
		"Driver": ["VER", "VER", "VER"],
		"LapNumber": [1, 2, 3],
		"PredictedLapTime": [89.0, 89.5, 90.0],
	}
	df_laps = pd.DataFrame(data)
	
	result = aggregate_laps_to_race(
		df_laps,
		predicted_lap_time_col="PredictedLapTime",
		driver_col="Driver",
		lap_number_col="LapNumber"
	)
	
	assert len(result) == 1
	row = result.iloc[0]
	
	# Check statistics
	assert abs(row["mean_predicted_lap"] - 89.5) < 0.01, "Mean should be 89.5"
	assert abs(row["median_predicted_lap"] - 89.5) < 0.01, "Median should be 89.5"
	assert abs(row["best_predicted_lap"] - 89.0) < 0.01, "Best should be 89.0"
	assert row["lap_time_std"] > 0, "Std should be positive"
	assert row["consistency_index"] > 0 and row["consistency_index"] <= 1, "Consistency index should be in [0, 1]"
	assert row["total_laps"] == 3, "Total laps should be 3"


def test_aggregation_tyre_counts():
	"""Test that tyre compound counts are calculated correctly."""
	data = {
		"Driver": ["VER", "VER", "VER", "VER"],
		"LapNumber": [1, 2, 3, 4],
		"PredictedLapTime": [89.0, 89.5, 90.0, 90.5],
		"Compound": ["SOFT", "SOFT", "MEDIUM", "HARD"],
	}
	df_laps = pd.DataFrame(data)
	
	result = aggregate_laps_to_race(
		df_laps,
		predicted_lap_time_col="PredictedLapTime",
		driver_col="Driver",
		lap_number_col="LapNumber",
		tyre_col="Compound"
	)
	
	assert len(result) == 1
	row = result.iloc[0]
	
	assert row["tyre_SOFT_count"] == 2, "Should have 2 SOFT laps"
	assert row["tyre_MEDIUM_count"] == 1, "Should have 1 MEDIUM lap"
	assert row["tyre_HARD_count"] == 1, "Should have 1 HARD lap"


def test_aggregation_temperature_averages():
	"""Test that temperature averages are calculated correctly."""
	data = {
		"Driver": ["VER", "VER", "VER"],
		"LapNumber": [1, 2, 3],
		"PredictedLapTime": [89.0, 89.5, 90.0],
		"TrackTemp": [35.0, 36.0, 37.0],
		"AirTemp": [25.0, 26.0, 27.0],
	}
	df_laps = pd.DataFrame(data)
	
	result = aggregate_laps_to_race(
		df_laps,
		predicted_lap_time_col="PredictedLapTime",
		driver_col="Driver",
		lap_number_col="LapNumber",
		track_temp_col="TrackTemp",
		air_temp_col="AirTemp"
	)
	
	assert len(result) == 1
	row = result.iloc[0]
	
	assert abs(row["average_track_temp"] - 36.0) < 0.01, "Average track temp should be 36.0"
	assert abs(row["average_air_temp"] - 26.0) < 0.01, "Average air temp should be 26.0"


def test_aggregation_degradation_slope():
	"""Test that degradation slope is calculated correctly."""
	data = {
		"Driver": ["VER", "VER", "VER", "VER", "VER"],
		"LapNumber": [1, 2, 3, 4, 5],
		"PredictedLapTime": [89.0, 89.2, 89.4, 89.6, 89.8],  # Linear degradation
	}
	df_laps = pd.DataFrame(data)
	
	result = aggregate_laps_to_race(
		df_laps,
		predicted_lap_time_col="PredictedLapTime",
		driver_col="Driver",
		lap_number_col="LapNumber"
	)
	
	assert len(result) == 1
	row = result.iloc[0]
	
	# Degradation slope should be positive (getting slower)
	assert row["degradation_slope"] > 0, "Degradation slope should be positive for increasing lap times"


def test_aggregation_empty_input():
	"""Test that empty input returns empty DataFrame."""
	result = aggregate_laps_to_race(pd.DataFrame())
	assert result.empty, "Empty input should return empty DataFrame"


def test_aggregation_missing_optional_columns():
	"""Test that aggregation works when optional columns are missing."""
	data = {
		"Driver": ["VER", "VER"],
		"LapNumber": [1, 2],
		"PredictedLapTime": [89.0, 89.5],
		# No Compound, TrackTemp, AirTemp
	}
	df_laps = pd.DataFrame(data)
	
	result = aggregate_laps_to_race(
		df_laps,
		predicted_lap_time_col="PredictedLapTime",
		driver_col="Driver",
		lap_number_col="LapNumber",
		tyre_col="Compound",  # Will be missing
		track_temp_col=None,  # Explicitly None
		air_temp_col=None  # Explicitly None
	)
	
	assert len(result) == 1, "Should still produce one row per driver"
	assert result["tyre_SOFT_count"].iloc[0] == 0, "Should default to 0 when Compound missing"

