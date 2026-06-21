import os
import sys
import traceback

import pandas as pd

from data_ingestion import get_event_schedule, get_winner_prediction_data
from winner_feature_engineering import engineer_winner_features
from winner_model import train_and_evaluate_winner_model

LOG_PATH = os.path.join(os.path.dirname(__file__), "training_log.txt")


class Tee:
	"""Write to both stdout and a log file simultaneously."""
	def __init__(self, file):
		self.file = file
		self.stdout = sys.stdout

	def write(self, data):
		self.stdout.write(data)
		self.file.write(data)
		self.file.flush()

	def flush(self):
		self.stdout.flush()
		self.file.flush()


if __name__ == "__main__":
	with open(LOG_PATH, "w", encoding="utf-8") as log_file:
		sys.stdout = Tee(log_file)
		sys.stderr = Tee(log_file)

		try:
			years_to_train = list(range(2018, 2026))

			all_X_list = []
			all_y_list = []

			for year in years_to_train:
				print(f"\n{'='*60}")
				print(f"Loading data for {year} season")
				print(f"{'='*60}")
				sys.stdout.flush()

				schedule = get_event_schedule(year)
				if schedule.empty or "EventName" not in schedule.columns:
					print(f"  Could not load schedule for {year}, skipping.")
					continue

				gps = schedule["EventName"].dropna().tolist()
				print(f"  Found {len(gps)} events")

				for gp in gps:
					try:
						print(f"  Loading {gp}...", flush=True)
						winner_data = get_winner_prediction_data(year, gp)
						if not winner_data.empty:
							X_winner, y_winner = engineer_winner_features(
								winner_data, year, gp, include_historical=True
							)
							if not X_winner.empty and not y_winner.empty:
								all_X_list.append(X_winner)
								all_y_list.append(y_winner)
								print(f"    Added {len(X_winner)} drivers")
					except Exception as e:
						print(f"    Skipped {gp}: {e}")
						traceback.print_exc()
						continue

			if not all_X_list:
				print("\nNo training data collected. Exiting.")
			else:
				X_combined = pd.concat(all_X_list, ignore_index=True)
				y_combined = pd.concat(all_y_list, ignore_index=True)

				print(f"\nTotal training samples: {len(X_combined)}")
				print(f"Winners in dataset: {int(y_combined.sum())}")

				print("\nTraining winner prediction models...")
				metrics = train_and_evaluate_winner_model(X_combined, y_combined)

				print("\nModel Metrics:")
				for model_name, model_metrics in metrics.items():
					if model_name != "best_model_path":
						print(f"  {model_name}:")
						for metric_name, metric_value in model_metrics.items():
							print(f"    {metric_name}: {metric_value:.4f}")

				print("\nTRAINING COMPLETE - model saved.")

		except Exception:
			print("\n\n*** FATAL ERROR - training crashed ***")
			traceback.print_exc()
			print("\nCheck training_log.txt for details.")

		finally:
			sys.stdout = sys.stdout.stdout
			sys.stderr = sys.stderr.stdout
