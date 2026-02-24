import os
from typing import Dict, Optional, List, Tuple
import warnings

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import log_loss, roc_auc_score, accuracy_score
from sklearn.model_selection import train_test_split
import joblib

from data_ingestion import get_session_data, get_event_schedule, get_race_results, get_qualifying_results
from model import load_best_model, align_features_to_model
from feature_engineering import engineer_features
from race_aggregation import aggregate_laps_to_race
from winner_labels import extract_winner_labels, get_winner_labels_from_session


MODELS_DIR = "models"
WINNER_MODEL_PATH = os.path.join(MODELS_DIR, "winner_model.joblib")


def calculate_top3_accuracy(y_true: np.ndarray, y_pred_proba: np.ndarray) -> float:
	"""Calculate top-3 accuracy: percentage of races where winner is in top 3 predicted probabilities.
	
	This is a simplified version that assumes all samples are from the same race.
	For multi-race evaluation, use calculate_top3_accuracy_by_race instead.
	
	Args:
		y_true: True labels (1 for winner, 0 otherwise) - shape (n_samples,)
		y_pred_proba: Predicted probabilities for class 1 (winner) - shape (n_samples,)
	
	Returns:
		Top-3 accuracy (0.0 to 1.0)
	"""
	if len(y_true) == 0 or len(y_pred_proba) == 0:
		return 0.0
	
	winners = np.where(y_true == 1)[0]
	if len(winners) == 0:
		return 0.0
	
	# Get top 3 indices by probability (descending order)
	top3_indices = np.argsort(y_pred_proba)[-3:]
	
	# Check if any winner is in top 3
	correct = sum(1 for w in winners if w in top3_indices)
	return float(correct / len(winners)) if len(winners) > 0 else 0.0


def calculate_top3_accuracy_by_race(df_results: pd.DataFrame, 
                                    proba_col: str = "win_probability",
                                    label_col: str = "IsWinner",
                                    driver_col: str = "Driver") -> float:
	"""Calculate top-3 accuracy grouped by race.
	
	For each race, checks if the winner (IsWinner=1) is in the top 3 drivers by probability.
	
	Args:
		df_results: DataFrame with race results, probabilities, and labels
		proba_col: Name of probability column
		label_col: Name of label column (IsWinner)
		driver_col: Name of driver column
	
	Returns:
		Top-3 accuracy across all races
	"""
	if df_results.empty or proba_col not in df_results.columns or label_col not in df_results.columns:
		return 0.0
	
	# Group by race if there's a race identifier, otherwise treat as single race
	# For now, assume all rows are from the same race or we need to add a race_id column
	# This is a simplified version - in practice you'd group by race_id
	
	# Get winners
	winners = df_results[df_results[label_col] == 1]
	if len(winners) == 0:
		return 0.0
	
	# Sort by probability descending
	sorted_df = df_results.sort_values(proba_col, ascending=False)
	
	# Get top 3 drivers
	top3_drivers = sorted_df.head(3)[driver_col].tolist()
	
	# Check if any winner is in top 3
	winner_drivers = winners[driver_col].tolist()
	correct = sum(1 for w in winner_drivers if w in top3_drivers)
	
	return float(correct / len(winners)) if len(winners) > 0 else 0.0


def calculate_regulation_stability(year: int) -> float:
	"""Calculate regulation stability feature.
	
	Regulation stability is 0 if the season is the first year of new regulations,
	otherwise 1. This indicates whether teams have had time to optimize under current rules.
	
	Regulation reset years: 2014, 2022, 2026
	
	Args:
		year: Year of the race
	
	Returns:
		0.0 if first year of new regulations, 1.0 otherwise
	"""
	regulation_reset_years = [2014, 2022, 2026]
	
	if year in regulation_reset_years:
		return 0.0
	else:
		return 1.0


def calculate_early_season_variance(driver: str, team: str, year: int, current_gp: str) -> float:
	"""Calculate early season variance (std of finishing positions in first 3 races).
	
	This measures consistency of performance in the early part of the season.
	Lower variance indicates more consistent performance.
	
	Args:
		driver: Driver code/abbreviation
		team: Team name
		year: Year of the season
		current_gp: Name of current Grand Prix
	
	Returns:
		Standard deviation of finishing positions in first 3 races, or 20.0 if not available
	"""
	warnings.filterwarnings("ignore", category=RuntimeWarning)
	warnings.filterwarnings("ignore", category=UserWarning)
	
	try:
		schedule = get_event_schedule(year)
		if schedule.empty or "EventName" not in schedule.columns:
			return 20.0
		
		all_gps = schedule["EventName"].dropna().tolist()
		if current_gp not in all_gps:
			return 20.0
		
		current_idx = all_gps.index(current_gp)
		
		# Get first 3 races before current GP (or first 3 races of season if current GP is early)
		if current_idx >= 3:
			# We have at least 3 races before current GP
			early_gps = all_gps[:current_idx][:3]  # First 3 races before current
		elif current_idx > 0:
			# Fewer than 3 races before current GP, use what we have
			early_gps = all_gps[:current_idx]
		else:
			# Current GP is first race, no historical data
			return 20.0
		
		if len(early_gps) == 0:
			return 20.0
		
		positions = []
		
		for gp in early_gps:
			try:
				race_results = get_race_results(year, gp)
				if not race_results.empty and "Driver" in race_results.columns and "Position" in race_results.columns:
					# Try to find driver in results
					driver_data = race_results[race_results["Driver"] == driver]
					if not driver_data.empty:
						pos = driver_data["Position"].iloc[0]
						if pd.notna(pos):
							positions.append(float(pos))
					elif "Team" in race_results.columns and team:
						# Try team if driver not found
						team_data = race_results[race_results["Team"] == team]
						if not team_data.empty:
							# Take best position from team
							pos = team_data["Position"].min()
							if pd.notna(pos):
								positions.append(float(pos))
			except Exception:
				continue
		
		if len(positions) >= 2:
			return float(np.std(positions))
		elif len(positions) == 1:
			# Only one race, use a default variance
			return 10.0
		else:
			return 20.0
	except Exception:
		return 20.0


def calculate_reliability_index(driver: str, team: str, year: int, current_gp: str) -> float:
	"""Calculate car reliability index (DNFs per race).
	
	This measures how often a driver/team experiences DNFs (Did Not Finish).
	Lower values indicate better reliability.
	
	Args:
		driver: Driver code/abbreviation
		team: Team name
		year: Year of the season
		current_gp: Name of current Grand Prix
	
	Returns:
		DNFs per race (0.0 = perfect reliability, 1.0 = DNF every race)
	"""
	warnings.filterwarnings("ignore", category=RuntimeWarning)
	warnings.filterwarnings("ignore", category=UserWarning)
	
	try:
		schedule = get_event_schedule(year)
		if schedule.empty or "EventName" not in schedule.columns:
			return 0.0
		
		all_gps = schedule["EventName"].dropna().tolist()
		if current_gp not in all_gps:
			return 0.0
		
		current_idx = all_gps.index(current_gp)
		previous_gps = all_gps[:current_idx]
		
		if len(previous_gps) == 0:
			return 0.0
		
		dnf_count = 0
		races_entered = 0
		
		# DNF indicators
		dnf_indicators = ["DNF", "DSQ", "DNS", "NC", "NOT CLASSIFIED", "DISQUALIFIED", "DID NOT START"]
		
		for gp in previous_gps:
			try:
				race_results = get_race_results(year, gp)
				if race_results.empty:
					continue
				
				# Try to find driver
				driver_data = race_results[race_results["Driver"] == driver]
				
				if driver_data.empty and "Team" in race_results.columns:
					# Try team if driver not found
					driver_data = race_results[race_results["Team"] == team]
				
				if not driver_data.empty:
					races_entered += 1
					
					# Check for DNF status
					if "Status" in driver_data.columns:
						statuses = driver_data["Status"].dropna().astype(str).str.upper()
						for status in statuses:
							if any(ind in status for ind in dnf_indicators):
								dnf_count += 1
								break
					elif "Position" in driver_data.columns:
						# If no Status column, check if Position is invalid (NaN or very high)
						position = driver_data["Position"].iloc[0]
						if pd.isna(position) or (pd.notna(position) and float(position) > 20):
							dnf_count += 1
			except Exception:
				continue
		
		if races_entered == 0:
			return 0.0
		
		return float(dnf_count / races_entered)
	except Exception:
		return 0.0


def add_regulation_features(df_race_features: pd.DataFrame, 
                           year: int, 
                           gp_name: str,
                           driver_col: str = "Driver",
                           team_col: Optional[str] = "Team") -> pd.DataFrame:
	"""Add regulation-awareness features to race-level features DataFrame.
	
	Adds:
	- regulation_stability: 0 if first year of new regulations, 1 otherwise
	- early_season_variance: std of finishing positions in first 3 races
	- car_reliability_index: DNFs per race
	
	Args:
		df_race_features: Race-level features DataFrame (from aggregate_laps_to_race)
		year: Year of the race
		gp_name: Name of the Grand Prix
		driver_col: Name of driver column
		team_col: Name of team column (optional)
	
	Returns:
		DataFrame with regulation features added
	"""
	if df_race_features.empty:
		return df_race_features
	
	result = df_race_features.copy()
	
	# Regulation stability (same for all drivers in same year)
	regulation_stability = calculate_regulation_stability(year)
	result["regulation_stability"] = regulation_stability
	
	# Early season variance and reliability index (per driver/team)
	early_variance_list = []
	reliability_list = []
	
	for idx, row in result.iterrows():
		driver = str(row.get(driver_col, ""))
		team = str(row.get(team_col, "")) if team_col and team_col in row else ""
		
		early_var = calculate_early_season_variance(driver, team, year, gp_name)
		reliability = calculate_reliability_index(driver, team, year, gp_name)
		
		early_variance_list.append(early_var)
		reliability_list.append(reliability)
	
	result["early_season_variance"] = early_variance_list
	result["car_reliability_index"] = reliability_list
	
	# Add race chaos index (same for all drivers in same race)
	chaos_index = calculate_race_chaos_index(year, gp_name)
	result["race_chaos_index"] = chaos_index
	
	return result


def prepare_race_level_features(year: int, gp_name: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
	"""Prepare race-level features from lap-level predictions.
	
	Pipeline:
	1. Load race session data
	2. Generate lap-level predictions using saved lap-time model
	3. Aggregate to race-level using race_aggregation
	4. Generate labels using winner_labels
	
	Args:
		year: Year of the race
		gp_name: Name of the Grand Prix
	
	Returns:
		Tuple of (X: race-level features DataFrame, y: labels Series)
	"""
	warnings.filterwarnings("ignore", category=RuntimeWarning)
	warnings.filterwarnings("ignore", category=UserWarning)
	
	# Step 1: Load race session data
	df_laps = get_session_data(year, gp_name, "R", include_sprint=False)
	if df_laps.empty:
		return pd.DataFrame(), pd.Series(dtype=int)
	
	# Step 2: Load lap-time model and generate predictions
	lap_model_data = load_best_model()
	if lap_model_data is None:
		raise ValueError("No saved lap-time model found. Train lap-time model first.")
	
	lap_model, lap_model_features = lap_model_data
	
	# Engineer features for lap-level data
	X_laps, _ = engineer_features(df_laps)
	X_laps_aligned = align_features_to_model(X_laps, lap_model_features)
	
	if X_laps_aligned.empty:
		return pd.DataFrame(), pd.Series(dtype=int)
	
	# Generate lap-level predictions
	predicted_lap_times = lap_model.predict(X_laps_aligned)
	df_laps["PredictedLapTime"] = predicted_lap_times
	
	# Step 3: Aggregate to race-level
	df_race_features = aggregate_laps_to_race(
		df_laps,
		predicted_lap_time_col="PredictedLapTime",
		driver_col="Driver",
		lap_number_col="LapNumber",
		tyre_col="Compound",
		track_temp_col="TrackTemp",
		air_temp_col="AirTemp"
	)
	
	if df_race_features.empty:
		return pd.DataFrame(), pd.Series(dtype=int)
	
	# Step 3.5: Add regulation-awareness features
	df_race_features = add_regulation_features(
		df_race_features,
		year=year,
		gp_name=gp_name,
		driver_col="Driver",
		team_col="Team" if "Team" in df_race_features.columns else None
	)
	
	# Step 4: Generate labels
	df_labels = get_winner_labels_from_session(year, gp_name, "R")
	
	if df_labels.empty:
		return pd.DataFrame(), pd.Series(dtype=int)
	
	# Merge features with labels on Driver
	merged = pd.merge(
		df_race_features,
		df_labels,
		on="Driver",
		how="inner"
	)
	
	if merged.empty or "IsWinner" not in merged.columns:
		return pd.DataFrame(), pd.Series(dtype=int)
	
	# Extract features and labels
	feature_cols = [c for c in merged.columns if c not in ["Driver", "IsWinner"]]
	X = merged[feature_cols].select_dtypes(include=[np.number]).fillna(0.0)
	y = merged["IsWinner"].astype(int)
	
	return X, y


def train_winner_model_from_races(years: List[int], random_state: int = 42) -> Dict[str, Dict[str, float]]:
	"""Train winner prediction model using data from multiple races.
	
	Args:
		years: List of years to collect race data from
		random_state: Random seed
	
	Returns:
		Dictionary with model metrics
	"""
	warnings.filterwarnings("ignore", category=RuntimeWarning)
	warnings.filterwarnings("ignore", category=UserWarning)
	
	all_X_list = []
	all_y_list = []
	race_info_list = []  # Track which race each sample comes from
	
	# Collect data from all races
	for year in years:
		schedule = get_event_schedule(year)
		if schedule.empty or "EventName" not in schedule.columns:
			continue
		
		gps = schedule["EventName"].dropna().tolist()
		
		for gp in gps:
			try:
				print(f"  Processing {year} {gp}...")
				X_race, y_race = prepare_race_level_features(year, gp)
				
				if not X_race.empty and not y_race.empty:
					all_X_list.append(X_race)
					all_y_list.append(y_race)
					race_info_list.extend([f"{year}_{gp}"] * len(X_race))
					print(f"    Added {len(X_race)} drivers")
			except Exception as e:
				print(f"    Skipped {year} {gp}: {e}")
				continue
	
	if not all_X_list:
		print("No race data collected.")
		return {}
	
	# Combine all race data
	X_combined = pd.concat(all_X_list, ignore_index=True)
	y_combined = pd.concat(all_y_list, ignore_index=True)
	
	print(f"\nTotal training samples: {len(X_combined)}")
	print(f"Winners in dataset: {y_combined.sum()}")
	
	if y_combined.sum() == 0:
		print("Warning: No winners found in training data.")
		return {}
	
	# Train/test split (stratified by winner label)
	try:
		X_train, X_test, y_train, y_test = train_test_split(
			X_combined, y_combined, test_size=0.2, random_state=random_state, stratify=y_combined
		)
	except ValueError:
		# If stratification fails (e.g., too few winners), use regular split
		X_train, X_test, y_train, y_test = train_test_split(
			X_combined, y_combined, test_size=0.2, random_state=random_state
		)
	
	# Train models
	models = {
		"LogisticRegression": LogisticRegression(random_state=random_state, max_iter=1000, class_weight="balanced"),
		"GradientBoostingClassifier": GradientBoostingClassifier(random_state=random_state, n_estimators=100),
	}
	
	metrics: Dict[str, Dict[str, float]] = {}
	best_name: Optional[str] = None
	best_log_loss: float = float("inf")
	best_model = None
	
	for name, model in models.items():
		try:
			print(f"\nTraining {name}...")
			model.fit(X_train, y_train)
			
			# Predictions
			y_pred = model.predict(X_test)
			y_pred_proba = model.predict_proba(X_test)[:, 1] if hasattr(model, "predict_proba") else y_pred.astype(float)
			
			# Calculate metrics
			log_loss_val = float(log_loss(y_test, y_pred_proba))
			
			# ROC AUC (handle case where all predictions are same class)
			try:
				roc_auc = float(roc_auc_score(y_test, y_pred_proba))
			except ValueError:
				roc_auc = 0.0
			
			# Top-3 accuracy
			# Create a DataFrame for top-3 calculation
			test_df = pd.DataFrame({
				"win_probability": y_pred_proba,
				"IsWinner": y_test.values,
				"Driver": [f"Driver_{i}" for i in range(len(y_test))]  # Placeholder driver names
			})
			top3_acc = calculate_top3_accuracy_by_race(test_df)
			
			metrics[name] = {
				"LogLoss": log_loss_val,
				"ROCAUC": roc_auc,
				"Top3Accuracy": top3_acc
			}
			
			print(f"  Log Loss: {log_loss_val:.4f}")
			print(f"  ROC AUC: {roc_auc:.4f}")
			print(f"  Top-3 Accuracy: {top3_acc:.4f}")
			
			# Best model is the one with lowest log loss
			if log_loss_val < best_log_loss:
				best_log_loss = log_loss_val
				best_name = name
				best_model = model
		except Exception as e:
			print(f"Error training {name}: {e}")
			import traceback
			traceback.print_exc()
			continue
	
	# Save best model
	os.makedirs(MODELS_DIR, exist_ok=True)
	if best_model is not None:
		joblib.dump({"model": best_model, "features": list(X_combined.columns)}, WINNER_MODEL_PATH)
		metrics["best_model_path"] = {"path": WINNER_MODEL_PATH}
		print(f"\nSaved best winner model: {best_name} -> {WINNER_MODEL_PATH}")
		print(f"Best Log Loss: {best_log_loss:.4f}")
	
	return metrics


def load_best_winner_model(path: str = WINNER_MODEL_PATH) -> Optional[Tuple[object, List[str]]]:
	"""Load saved winner prediction model.
	
	Returns:
		Tuple of (model, feature_names) or None if not found
	"""
	if not os.path.exists(path):
		return None
	payload = joblib.load(path)
	return payload["model"], list(payload.get("features", []))


def align_winner_features_to_model(X: pd.DataFrame, expected_features: List[str]) -> pd.DataFrame:
	"""Align feature columns to match saved winner model.
	Adds missing columns with 0.0, removes extra columns.
	"""
	aligned = X.copy()
	for col in expected_features:
		if col not in aligned.columns:
			aligned[col] = 0.0
	return aligned[expected_features]


def calculate_safety_car_probability(gp_name: str, years: Optional[List[int]] = None) -> float:
	"""Calculate historical safety car probability for a circuit.
	
	This is a simplified proxy: we estimate based on DNF rate and track characteristics.
	In practice, you would need to query FastF1 for actual safety car periods.
	
	Args:
		gp_name: Name of the Grand Prix/circuit
		years: Optional list of years to consider (default: last 5 years)
	
	Returns:
		Safety car probability (0.0 to 1.0)
	"""
	if years is None:
		# Default to last 5 years
		from datetime import datetime
		current_year = datetime.now().year
		years = list(range(max(2018, current_year - 5), current_year + 1))
	
	total_races = 0
	estimated_sc_races = 0
	
	for year in years:
		try:
			race_results = get_race_results(year, gp_name)
			if not race_results.empty:
				total_races += 1
				# Estimate SC probability from DNF rate
				# Higher DNF rate suggests more incidents and potential SC periods
				if "Status" in race_results.columns:
					dnf_indicators = ["DNF", "DSQ", "DNS", "NC", "NOT CLASSIFIED", "DISQUALIFIED"]
					statuses = race_results["Status"].dropna().astype(str).str.upper()
					dnf_count = sum(1 for s in statuses if any(ind in s for ind in dnf_indicators))
					# If 3+ DNFs, likely had SC periods
					if dnf_count >= 3:
						estimated_sc_races += 1
				elif "Position" in race_results.columns:
					# Estimate from number of drivers who didn't finish (position > 20 or NaN)
					positions = race_results["Position"].dropna()
					dnf_count = sum(1 for p in positions if pd.isna(p) or (pd.notna(p) and float(p) > 20))
					if dnf_count >= 3:
						estimated_sc_races += 1
		except Exception:
			continue
	
	if total_races == 0:
		return 0.3  # Default moderate probability
	
	return min(1.0, float(estimated_sc_races / total_races))


def calculate_weather_variance(year: int, gp_name: str) -> float:
	"""Calculate weather variance during race.
	
	Measures how much weather conditions change during the race (temperature, humidity).
	Higher variance indicates more chaotic conditions.
	
	Args:
		year: Year of the race
		gp_name: Name of the Grand Prix
	
	Returns:
		Normalized weather variance (0.0 to 1.0)
	"""
	try:
		df_race = get_session_data(year, gp_name, "R", include_sprint=False)
		if df_race.empty:
			return 0.0
		
		# Calculate variance of weather metrics
		variances = []
		
		if "TrackTemp" in df_race.columns:
			track_temps = df_race["TrackTemp"].dropna()
			if len(track_temps) > 1:
				var = float(track_temps.std())
				# Normalize: typical range is 20-50°C, so std of 10°C is high variance
				normalized_var = min(1.0, var / 10.0)
				variances.append(normalized_var)
		
		if "AirTemp" in df_race.columns:
			air_temps = df_race["AirTemp"].dropna()
			if len(air_temps) > 1:
				var = float(air_temps.std())
				normalized_var = min(1.0, var / 10.0)
				variances.append(normalized_var)
		
		if "Humidity" in df_race.columns:
			humidity = df_race["Humidity"].dropna()
			if len(humidity) > 1:
				var = float(humidity.std())
				# Normalize: typical range is 30-80%, so std of 15% is high variance
				normalized_var = min(1.0, var / 15.0)
				variances.append(normalized_var)
		
		if variances:
			return float(np.mean(variances))
		else:
			return 0.0
	except Exception:
		return 0.0


def calculate_grid_spread(year: int, gp_name: str) -> float:
	"""Calculate grid spread (P1–P10 qualifying gap).
	
	Measures the time gap between pole position and P10 in qualifying.
	Larger gaps indicate less competitive field, smaller gaps indicate more chaos potential.
	
	Args:
		year: Year of the race
		gp_name: Name of the Grand Prix
	
	Returns:
		Normalized grid spread (0.0 to 1.0), where 1.0 = very tight grid (chaotic)
	"""
	try:
		qualifying = get_qualifying_results(year, gp_name)
		if qualifying.empty:
			return 0.5  # Default moderate spread
		
		# Get qualifying times
		q_times = []
		for q_col in ["Q3", "Q2", "Q1"]:
			if q_col in qualifying.columns:
				times = pd.to_timedelta(qualifying[q_col], errors="coerce").dt.total_seconds()
				q_times.extend(times.dropna().tolist())
				break
		
		if len(q_times) < 10:
			return 0.5
		
		# Sort and get P1 and P10 times
		sorted_times = sorted(q_times)
		p1_time = sorted_times[0]
		p10_time = sorted_times[9] if len(sorted_times) >= 10 else sorted_times[-1]
		
		gap = p10_time - p1_time
		
		# Normalize: typical gaps are 0.5-3.0 seconds
		# Smaller gap (< 1.0s) = tight grid = more chaos potential
		# Larger gap (> 2.0s) = spread out = less chaos
		if gap < 1.0:
			return 1.0  # Very tight, high chaos
		elif gap > 2.0:
			return 0.0  # Spread out, low chaos
		else:
			# Linear interpolation
			return float(1.0 - (gap - 1.0) / 1.0)
	except Exception:
		return 0.5


def calculate_circuit_dnf_rate(gp_name: str, years: Optional[List[int]] = None) -> float:
	"""Calculate historical DNF rate at a circuit.
	
	Args:
		gp_name: Name of the Grand Prix/circuit
		years: Optional list of years to consider (default: last 5 years)
	
	Returns:
		Average DNF rate per race (0.0 to 1.0)
	"""
	if years is None:
		from datetime import datetime
		current_year = datetime.now().year
		years = list(range(max(2018, current_year - 5), current_year + 1))
	
	total_drivers = 0
	total_dnfs = 0
	
	dnf_indicators = ["DNF", "DSQ", "DNS", "NC", "NOT CLASSIFIED", "DISQUALIFIED", "DID NOT START"]
	
	for year in years:
		try:
			race_results = get_race_results(year, gp_name)
			if not race_results.empty:
				if "Status" in race_results.columns:
					statuses = race_results["Status"].dropna().astype(str).str.upper()
					total_drivers += len(statuses)
					dnf_count = sum(1 for s in statuses if any(ind in s for ind in dnf_indicators))
					total_dnfs += dnf_count
				elif "Position" in race_results.columns:
					positions = race_results["Position"]
					total_drivers += len(positions)
					# Count invalid positions as DNFs
					dnf_count = sum(1 for p in positions if pd.isna(p) or (pd.notna(p) and float(p) > 20))
					total_dnfs += dnf_count
		except Exception:
			continue
	
	if total_drivers == 0:
		return 0.1  # Default moderate DNF rate
	
	return min(1.0, float(total_dnfs / total_drivers))


def calculate_race_chaos_index(year: int, gp_name: str) -> float:
	"""Calculate race chaos index from multiple factors.
	
	Combines:
	- Track safety car probability (historical)
	- Weather variance during race
	- Grid spread (P1–P10 qualifying gap)
	- DNF rate at circuit
	
	Args:
		year: Year of the race
		gp_name: Name of the Grand Prix
	
	Returns:
		Normalized chaos index (0.0 to 1.0), where 1.0 = maximum chaos
	"""
	# Calculate components
	sc_prob = calculate_safety_car_probability(gp_name)
	weather_var = calculate_weather_variance(year, gp_name)
	grid_spread = calculate_grid_spread(year, gp_name)
	dnf_rate = calculate_circuit_dnf_rate(gp_name)
	
	# Weighted combination (all components equally weighted)
	chaos_index = (sc_prob + weather_var + grid_spread + dnf_rate) / 4.0
	
	# Ensure normalized to [0, 1]
	return float(np.clip(chaos_index, 0.0, 1.0))


def predict_winner_probabilities(model, X: pd.DataFrame, chaos_index: Optional[float] = None) -> np.ndarray:
	"""Predict winner probabilities for each driver with chaos-awareness.
	
	When chaos_index is high, probabilities are smoothed to prevent collapse to a single driver.
	
	Args:
		model: Trained classification model
		X: Feature DataFrame
		chaos_index: Optional chaos index (0.0 to 1.0). If None, extracts from X if available.
	
	Returns:
		Array of probabilities (0-1) for each row in X
	"""
	# Extract chaos index from features if not provided
	if chaos_index is None and "race_chaos_index" in X.columns:
		chaos_index = float(X["race_chaos_index"].iloc[0]) if len(X) > 0 else None
	
	if hasattr(model, "predict_proba"):
		proba = model.predict_proba(X)
		# Return probability of class 1 (winner)
		if proba.shape[1] > 1:
			raw_proba = proba[:, 1]
		else:
			raw_proba = proba[:, 0]
	else:
		# Fallback to binary prediction
		raw_proba = model.predict(X).astype(float)
	
	# Apply chaos-aware smoothing if chaos_index is provided and meaningful
	if chaos_index is not None and chaos_index > 0.1:  # Only smooth if chaos is meaningful
		# Smooth probabilities: mix with uniform distribution based on chaos level
		# Higher chaos = more uniform distribution
		n_drivers = len(raw_proba)
		uniform_proba = np.ones(n_drivers) / n_drivers
		
		# Interpolate between raw probabilities and uniform based on chaos
		# chaos_index = 0.0 -> use raw probabilities
		# chaos_index = 1.0 -> use uniform distribution
		smoothed_proba = (1.0 - chaos_index) * raw_proba + chaos_index * uniform_proba
		
		# Renormalize to ensure probabilities sum to 1
		smoothed_proba = smoothed_proba / smoothed_proba.sum()
		
		return smoothed_proba
	else:
		return raw_proba
