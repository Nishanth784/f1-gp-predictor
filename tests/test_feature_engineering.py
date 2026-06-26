import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np

from feature_engineering import engineer_features


def test_engineer_features_basic():
	data = {
		"Driver": ["HAM", "VER"],
		"Team": ["Mercedes", "Red Bull"],
		"LapNumber": [1, 2],
		"LapTime": [pd.to_timedelta("00:01:40.000"), pd.to_timedelta("00:01:39.000")],
		"Sector1Time": [pd.to_timedelta("00:00:30.000"), pd.to_timedelta("00:00:29.500")],
		"Sector2Time": [pd.to_timedelta("00:00:40.000"), pd.to_timedelta("00:00:39.000")],
		"Sector3Time": [pd.to_timedelta("00:00:30.000"), pd.to_timedelta("00:00:30.500")],
		"Compound": ["SOFT", "MEDIUM"],
		"TyreLife": [5.0, 7.0],
	}
	df = pd.DataFrame(data)
	X, y = engineer_features(df)

	assert not X.empty
	assert y.shape[0] == 2
	assert "AvgSectorSeconds" in X.columns
	assert "TrackEvolution" in X.columns
	# One-hot columns exist for categories
	cat_cols = [c for c in X.columns if c.startswith("Driver_") or c.startswith("Team_") or c.startswith("Compound_")]
	assert cat_cols, "Expected categorical one-hot columns"
