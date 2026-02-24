import os
import time
from typing import Optional, List

import numpy as np
import pandas as pd
import requests

import fastf1

from feature_engineering import engineer_features
from model import load_best_model, align_features_to_model


def get_live_weather(location: str, api_key: Optional[str] = None) -> dict:
	api_key = api_key or os.getenv("OPENWEATHER_API_KEY")
	if not api_key:
		return {"AirTemp": None, "Humidity": None}
	try:
		r = requests.get(
			"https://api.openweathermap.org/data/2.5/weather",
			params={"q": location, "appid": api_key, "units": "metric"},
			timeout=10,
		)
		r.raise_for_status()
		data = r.json()
		m = data.get("main", {})
		return {"AirTemp": m.get("temp"), "Humidity": m.get("humidity")}
	except Exception:
		return {"AirTemp": None, "Humidity": None}


def live_predict_latest_laps(year: int, gp_name: str, session_code: str, location: str, iterations: int = 3, sleep_seconds: int = 5) -> None:
	loaded = load_best_model()
	if loaded is None:
		print("No saved model found. Train a model first.")
		return
	model, expected_features = loaded

	s = fastf1.get_session(year, gp_name, session_code)
	s.load(telemetry=False, weather=True, messages=False)

	seen_rows = 0
	for _ in range(iterations):
		laps: pd.DataFrame = s.laps
		if laps is None or laps.empty:
			print("No laps yet...")
			time.sleep(sleep_seconds)
			continue

		latest = laps.sort_values(["LapStartTime" if "LapStartTime" in laps.columns else "Time"]).reset_index(drop=True)
		new = latest.iloc[seen_rows:].copy() if seen_rows < len(latest) else pd.DataFrame()
		seen_rows = len(latest)
		if new.empty:
			print("No new laps...")
			time.sleep(sleep_seconds)
			continue

		w = get_live_weather(location)
		for col in ["AirTemp", "Humidity"]:
			if w.get(col) is not None:
				new[col] = float(w[col])

		keep = ["Driver", "Team", "LapNumber", "LapTime", "Sector1Time", "Sector2Time", "Sector3Time", "Compound", "TyreLife", "AirTemp", "Humidity"]
		new = new[[c for c in keep if c in new.columns]].copy()

		X, y = engineer_features(new)
		X = align_features_to_model(X, expected_features)
		if X.empty:
			print("No usable features yet...")
			time.sleep(sleep_seconds)
			continue

		pred = model.predict(X)
		out = pd.DataFrame({"PredictedLap": pred, "ActualLap": y.values if not y.empty else np.nan})
		print(out.head(10).to_string(index=False))
		time.sleep(sleep_seconds)
