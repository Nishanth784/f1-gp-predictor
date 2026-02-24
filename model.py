import os
from typing import Dict, Optional, List, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
import joblib


MODELS_DIR = "models"
BEST_PATH = os.path.join(MODELS_DIR, "best_model.joblib")


def align_features_to_model(X: pd.DataFrame, expected_features: List[str]) -> pd.DataFrame:
	aligned = X.copy()
	for col in expected_features:
		if col not in aligned.columns:
			aligned[col] = 0.0
	return aligned[expected_features]


def train_and_evaluate(X: pd.DataFrame, y: pd.Series, random_state: int = 42) -> Dict[str, Dict[str, float]]:
	if X.empty or y.empty:
		return {}

	X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=random_state)

	models = {
		"LinearRegression": LinearRegression(),
		"RandomForestRegressor": RandomForestRegressor(n_estimators=300, random_state=random_state, n_jobs=-1),
		"GradientBoostingRegressor": GradientBoostingRegressor(random_state=random_state),
	}

	metrics: Dict[str, Dict[str, float]] = {}
	best_name: Optional[str] = None
	best_rmse: float = float("inf")
	best_model = None

	for name, model in models.items():
		model.fit(X_train, y_train)
		pred = model.predict(X_test)
		mae = float(mean_absolute_error(y_test, pred))
		rmse = float(np.sqrt(mean_squared_error(y_test, pred)))
		metrics[name] = {"MAE": mae, "RMSE": rmse}
		if rmse < best_rmse:
			best_rmse = rmse
			best_name = name
			best_model = model

	os.makedirs(MODELS_DIR, exist_ok=True)
	if best_model is not None:
		joblib.dump({"model": best_model, "features": list(X.columns)}, BEST_PATH)
		metrics["best_model_path"] = {"path": BEST_PATH}
	return metrics


def load_best_model(path: str = BEST_PATH) -> Optional[Tuple[object, List[str]]]:
	if not os.path.exists(path):
		return None
	payload = joblib.load(path)
	return payload["model"], list(payload.get("features", []))
