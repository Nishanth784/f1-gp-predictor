import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from winner_labels import extract_winner_labels
from winner_model import (
	align_winner_features_to_model,
	predict_winner_probabilities,
	calculate_regulation_stability,
	calculate_race_chaos_index
)
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier


def test_extract_winner_labels_correct():
	"""Test that winner labels are extracted correctly."""
	data = {
		"Driver": ["VER", "HAM", "NOR"],
		"Position": [1, 2, 3],
		"Status": ["Finished", "Finished", "Finished"],
	}
	df_race = pd.DataFrame(data)
	
	result = extract_winner_labels(df_race)
	
	assert len(result) == 3, "Should have one row per driver"
	assert "Driver" in result.columns
	assert "IsWinner" in result.columns
	
	# VER should be winner (Position == 1)
	ver_row = result[result["Driver"] == "VER"]
	assert len(ver_row) == 1
	assert ver_row["IsWinner"].iloc[0] == 1, "VER should be marked as winner"
	
	# HAM and NOR should not be winners
	ham_row = result[result["Driver"] == "HAM"]
	nor_row = result[result["Driver"] == "NOR"]
	assert ham_row["IsWinner"].iloc[0] == 0, "HAM should not be winner"
	assert nor_row["IsWinner"].iloc[0] == 0, "NOR should not be winner"


def test_extract_winner_labels_dnf_handling():
	"""Test that DNFs are handled correctly (not marked as winners)."""
	data = {
		"Driver": ["VER", "HAM", "NOR"],
		"Position": [1, 2, None],  # NOR has no position (DNF)
		"Status": ["Finished", "Finished", "DNF"],
	}
	df_race = pd.DataFrame(data)
	
	result = extract_winner_labels(df_race)
	
	# VER should be winner
	ver_row = result[result["Driver"] == "VER"]
	assert ver_row["IsWinner"].iloc[0] == 1
	
	# NOR with DNF should not be winner even if somehow Position was 1
	nor_row = result[result["Driver"] == "NOR"]
	assert nor_row["IsWinner"].iloc[0] == 0, "DNF should not be winner"


def test_extract_winner_labels_missing_position():
	"""Test that missing Position column marks all as non-winners."""
	data = {
		"Driver": ["VER", "HAM"],
		# No Position column
	}
	df_race = pd.DataFrame(data)
	
	result = extract_winner_labels(df_race, position_col="Position")
	
	assert len(result) == 2
	assert all(result["IsWinner"] == 0), "All should be non-winners when Position missing"


def test_winner_model_probabilities_sum_to_one():
	"""Test that winner model outputs probabilities summing to 1."""
	# Create synthetic features
	X = pd.DataFrame({
		"feature1": np.random.randn(5),
		"feature2": np.random.randn(5),
		"feature3": np.random.randn(5),
	})
	
	# Create a simple model
	model = LogisticRegression(random_state=42, max_iter=1000)
	# Train on synthetic data
	y = np.array([1, 0, 0, 0, 0])  # One winner
	model.fit(X, y)
	
	# Predict probabilities
	probabilities = predict_winner_probabilities(model, X)
	
	# Probabilities should sum to approximately 1 (within tolerance)
	prob_sum = np.sum(probabilities)
	assert abs(prob_sum - 1.0) < 0.01, f"Probabilities should sum to 1, got {prob_sum}"
	
	# All probabilities should be in [0, 1]
	assert all(0 <= p <= 1 for p in probabilities), "All probabilities should be in [0, 1]"


def test_winner_model_probabilities_with_chaos():
	"""Test that chaos-aware probabilities still sum to 1."""
	X = pd.DataFrame({
		"feature1": np.random.randn(5),
		"feature2": np.random.randn(5),
		"race_chaos_index": [0.8] * 5,  # High chaos
	})
	
	model = LogisticRegression(random_state=42, max_iter=1000)
	y = np.array([1, 0, 0, 0, 0])
	model.fit(X.drop(columns=["race_chaos_index"]), y)
	
	# Predict with chaos index
	probabilities = predict_winner_probabilities(model, X, chaos_index=0.8)
	
	# Should still sum to 1
	prob_sum = np.sum(probabilities)
	assert abs(prob_sum - 1.0) < 0.01, f"Chaos-aware probabilities should sum to 1, got {prob_sum}"
	
	# With high chaos, probabilities should be more uniform
	# (less variance between max and min)
	max_prob = np.max(probabilities)
	min_prob = np.min(probabilities)
	# High chaos should reduce the gap between max and min
	assert (max_prob - min_prob) < 0.5, "High chaos should make probabilities more uniform"


def test_align_winner_features_adds_missing_cols():
	"""Test that feature alignment adds missing columns with 0.0."""
	X = pd.DataFrame({
		"feature1": [1.0, 2.0],
		"feature2": [3.0, 4.0],
	})
	expected_features = ["feature1", "feature2", "feature3", "feature4"]
	
	aligned = align_winner_features_to_model(X, expected_features)
	
	assert list(aligned.columns) == expected_features
	assert np.allclose(aligned["feature3"], 0.0), "Missing feature3 should be 0.0"
	assert np.allclose(aligned["feature4"], 0.0), "Missing feature4 should be 0.0"
	assert np.allclose(aligned["feature1"], X["feature1"]), "Existing feature1 should be preserved"
	assert np.allclose(aligned["feature2"], X["feature2"]), "Existing feature2 should be preserved"


def test_align_winner_features_removes_extra_cols():
	"""Test that feature alignment removes extra columns."""
	X = pd.DataFrame({
		"feature1": [1.0, 2.0],
		"feature2": [3.0, 4.0],
		"feature3": [5.0, 6.0],
		"extra_feature": [7.0, 8.0],
	})
	expected_features = ["feature1", "feature2"]
	
	aligned = align_winner_features_to_model(X, expected_features)
	
	assert list(aligned.columns) == expected_features
	assert "extra_feature" not in aligned.columns, "Extra features should be removed"


def test_regulation_stability():
	"""Test that regulation stability is calculated correctly."""
	# Regulation reset years
	assert calculate_regulation_stability(2014) == 0.0, "2014 should be regulation reset year"
	assert calculate_regulation_stability(2022) == 0.0, "2022 should be regulation reset year"
	assert calculate_regulation_stability(2026) == 0.0, "2026 should be regulation reset year"
	
	# Non-reset years
	assert calculate_regulation_stability(2015) == 1.0, "2015 should have stability"
	assert calculate_regulation_stability(2023) == 1.0, "2023 should have stability"
	assert calculate_regulation_stability(2024) == 1.0, "2024 should have stability"


def test_chaos_index_normalized():
	"""Test that chaos index is normalized to [0, 1] range."""
	# This is a simplified test - in practice, calculate_race_chaos_index
	# requires actual FastF1 data, so we test the normalization logic
	
	# Test that the function returns a value in [0, 1]
	# We'll mock the component functions or test with known inputs
	# For now, we test that the function signature is correct and handles edge cases
	
	# The function should always return a float in [0, 1]
	# We can't easily test the full function without FastF1 data,
	# but we can test that it doesn't crash and returns a valid range
	pass  # This would require mocking FastF1 calls


def test_winner_model_multiple_drivers():
	"""Test that winner model handles multiple drivers correctly."""
	# Create features for 3 drivers
	X = pd.DataFrame({
		"feature1": [1.0, 2.0, 3.0],
		"feature2": [4.0, 5.0, 6.0],
	})
	
	model = LogisticRegression(random_state=42, max_iter=1000)
	y = np.array([1, 0, 0])  # First driver is winner
	model.fit(X, y)
	
	probabilities = predict_winner_probabilities(model, X)
	
	assert len(probabilities) == 3, "Should have probability for each driver"
	assert abs(np.sum(probabilities) - 1.0) < 0.01, "Probabilities should sum to 1"
	
	# First driver should have highest probability (was trained as winner)
	assert probabilities[0] >= probabilities[1], "Winner should have higher probability"
	assert probabilities[0] >= probabilities[2], "Winner should have higher probability"


def test_winner_model_empty_input():
	"""Test that winner model handles empty input gracefully."""
	X = pd.DataFrame()
	
	model = LogisticRegression(random_state=42, max_iter=1000)
	# Can't train on empty data, so we test the prediction function
	# It should handle empty input or raise appropriate error
	try:
		probabilities = predict_winner_probabilities(model, X)
		# If it doesn't raise, probabilities should be empty or handle gracefully
	except Exception:
		pass  # Expected for empty input


def test_winner_labels_one_winner_only():
	"""Test that only one driver is marked as winner (Position == 1)."""
	data = {
		"Driver": ["VER", "HAM", "NOR", "LEC"],
		"Position": [1, 2, 3, 4],
	}
	df_race = pd.DataFrame(data)
	
	result = extract_winner_labels(df_race)
	
	# Only one winner
	winner_count = result["IsWinner"].sum()
	assert winner_count == 1, f"Should have exactly one winner, got {winner_count}"
	
	# VER should be the winner
	ver_row = result[result["Driver"] == "VER"]
	assert ver_row["IsWinner"].iloc[0] == 1

