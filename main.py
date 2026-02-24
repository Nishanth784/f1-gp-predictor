import os

import numpy as np
import pandas as pd

from data_ingestion import get_session_data, get_event_schedule, get_winner_prediction_data
from feature_engineering import engineer_features
from model import train_and_evaluate
from realtime import live_predict_latest_laps
from winner_feature_engineering import engineer_winner_features
from winner_model import train_and_evaluate_winner_model


if __name__ == "__main__":
	# Demo: Monaco Grand Prix 2023 Qualifying
	year_example = 2023
	grand_prix_example = "Monaco"
	session_example = "Q"

	print(f"Loading session: {year_example} {grand_prix_example} {session_example}...")
	df_clean = get_session_data(year_example, grand_prix_example, session_example, include_sprint=True)
	print("Sample rows:")
	print(df_clean.head(10))

	print("\nEngineering features...")
	X, y = engineer_features(df_clean)
	print(X.head(5))
	print(y.head(5).to_string(index=False))

	print("\nTraining lap time models (80/20 split) and evaluating...")
	_ = train_and_evaluate(X, y)

	# Train winner prediction model
	print("\n" + "="*60)
	print("Training Winner Prediction Model")
	print("="*60)
	
	try:
		# Collect data from multiple GPs in the year
		schedule = get_event_schedule(year_example)
		if not schedule.empty and "EventName" in schedule.columns:
			gps = schedule["EventName"].dropna().tolist()
			print(f"Found {len(gps)} Grand Prix events in {year_example}")
			
			all_X_list = []
			all_y_list = []
			
			for gp in gps:
				try:
					print(f"  Loading data for {gp}...")
					winner_data = get_winner_prediction_data(year_example, gp)
					if not winner_data.empty:
						X_winner, y_winner = engineer_winner_features(winner_data, year_example, gp, include_historical=True)
						if not X_winner.empty and not y_winner.empty:
							all_X_list.append(X_winner)
							all_y_list.append(y_winner)
							print(f"    Added {len(X_winner)} drivers")
				except Exception as e:
					print(f"    Skipped {gp}: {e}")
					continue
			
			if all_X_list:
				# Combine all GP data
				X_combined = pd.concat(all_X_list, ignore_index=True)
				y_combined = pd.concat(all_y_list, ignore_index=True)
				
				print(f"\nTotal training samples: {len(X_combined)}")
				print(f"Winners in dataset: {y_combined.sum()}")
				
				print("\nTraining winner prediction models...")
				winner_metrics = train_and_evaluate_winner_model(X_combined, y_combined)
				print("\nWinner Model Metrics:")
				for model_name, model_metrics in winner_metrics.items():
					if model_name != "best_model_path":
						print(f"  {model_name}:")
						for metric_name, metric_value in model_metrics.items():
							print(f"    {metric_name}: {metric_value:.4f}")
			else:
				print("No winner prediction data collected.")
		else:
			print("Could not load event schedule for winner model training.")
	except Exception as e:
		print(f"Error training winner model: {e}")
		import traceback
		traceback.print_exc()

	if os.getenv("RUN_LIVE_DEMO") == "1":
		print("\nStarting live prediction loop (simulated polling)...")
		live_predict_latest_laps(year_example, grand_prix_example, session_example, location="Monaco,MC", iterations=2, sleep_seconds=3)
