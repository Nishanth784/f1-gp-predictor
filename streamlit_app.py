import os
import warnings
from typing import List, Tuple, Dict

import numpy as np
import pandas as pd
import streamlit as st
import joblib

import fastf1

# Import utilities from main module
from data_ingestion import get_session_data
from feature_engineering import engineer_features
from model import align_features_to_model


st.set_page_config(page_title="F1 Grand Prix Prediction", layout="wide")

warnings.filterwarnings("ignore", category=UserWarning)


def load_or_train_model(X: pd.DataFrame, y: pd.Series, model_path: str) -> Tuple[object, List[str], Dict[str, float]]:
	"""Load saved model if present; otherwise train a quick GradientBoosting model on provided data."""
	metrics: Dict[str, float] = {}
	if os.path.exists(model_path):
		payload = joblib.load(model_path)
		return payload["model"], list(payload.get("features", list(X.columns))), metrics
	# Fallback quick model
	from sklearn.ensemble import GradientBoostingRegressor
	from sklearn.model_selection import train_test_split
	from sklearn.metrics import mean_absolute_error, mean_squared_error
	X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
	model = GradientBoostingRegressor(random_state=42)
	model.fit(X_train, y_train)
	pred = model.predict(X_test)
	mae = float(mean_absolute_error(y_test, pred))
	rmse = float(np.sqrt(mean_squared_error(y_test, pred)))
	metrics = {"MAE": mae, "RMSE": rmse}
	return model, list(X.columns), metrics


def get_gp_options(year: int) -> List[str]:
	try:
		schedule = fastf1.get_event_schedule(year, include_testing=False)
		if "EventName" in schedule.columns:
			return schedule["EventName"].dropna().unique().tolist()
		return []
	except Exception:
		return []


def build_predictions_table(df_clean: pd.DataFrame, model, feature_names: List[str]) -> pd.DataFrame:
	X, y = engineer_features(df_clean)
	if feature_names:
		X = align_features_to_model(X, feature_names)
	pred = model.predict(X)
	out = pd.concat([
		df_clean.reset_index(drop=True)[[c for c in ["Driver", "Team", "LapNumber"] if c in df_clean.columns]],
		pd.DataFrame({
			"ActualLapTime": y.values if not y.empty else np.nan,
			"PredictedLapTime": pred,
		})
	], axis=1)
	out["AbsoluteError"] = (out["PredictedLapTime"] - out["ActualLapTime"]).abs()
	return out


def plot_lap_times(df_pred: pd.DataFrame):
	if df_pred.empty:
		st.info("No data to plot.")
		return
	if "LapNumber" not in df_pred.columns:
		st.info("Lap numbers are missing for plotting.")
		return
	cols = [c for c in ["ActualLapTime", "PredictedLapTime"] if c in df_pred.columns]
	if len(cols) < 2:
		st.info("Required columns missing for plotting.")
		return
	agg = df_pred.groupby("LapNumber")[cols].mean(numeric_only=True).reset_index()
	st.line_chart(agg.set_index("LapNumber"))


# Sidebar controls
with st.sidebar:
	st.header("Controls")
	year = st.number_input("Year", min_value=2018, max_value=2025, value=2023, step=1)
	gp_names = get_gp_options(int(year))
	default_gp = gp_names[0] if gp_names else "Monaco"
	gp = st.selectbox("Grand Prix", options=gp_names if gp_names else [default_gp], index=0)
	session_label_to_code = {"Qualifying": "Q", "Race": "R"}
	session_label = st.selectbox("Session", options=list(session_label_to_code.keys()), index=0)
	session_code = session_label_to_code[session_label]
	model_path = os.path.join("models", "best_model.joblib")

st.title("F1 Grand Prix Winner Prediction - Dashboard")

# Load data and model
with st.spinner("Loading session data..."):
	df_clean = get_session_data(int(year), gp, session_code)

if df_clean.empty:
	st.warning("No session data available.")
	st.stop()

with st.spinner("Preparing features and loading model..."):
	X, y = engineer_features(df_clean)
	model, features, train_metrics = load_or_train_model(X, y, model_path)

if train_metrics:
	st.caption(f"Model trained on the fly (no saved model found). MAE={train_metrics['MAE']:.3f}s, RMSE={train_metrics['RMSE']:.3f}s")

# Build predictions table
with st.spinner("Running predictions..."):
	pred_table = build_predictions_table(df_clean, model, features)

# Filters
cols = st.columns(2)
with cols[0]:
	drivers = sorted(pred_table["Driver"].dropna().unique().tolist()) if "Driver" in pred_table.columns else []
	driver_filter = st.multiselect("Filter by Driver", options=drivers, default=[])
with cols[1]:
	teams = sorted(pred_table["Team"].dropna().unique().tolist()) if "Team" in pred_table.columns else []
	team_filter = st.multiselect("Filter by Team", options=teams, default=[])

filtered = pred_table.copy()
if driver_filter:
	filtered = filtered[filtered["Driver"].isin(driver_filter)]
if team_filter:
	filtered = filtered[filtered["Team"].isin(team_filter)]

# Summary metrics
if not filtered.empty:
	mae = float((filtered["PredictedLapTime"] - filtered["ActualLapTime"]).abs().mean())
	rmse = float(np.sqrt(((filtered["PredictedLapTime"] - filtered["ActualLapTime"]) ** 2).mean()))
	st.metric(label="MAE (s)", value=f"{mae:.3f}")
	st.metric(label="RMSE (s)", value=f"{rmse:.3f}")

# Table
st.subheader("Predicted vs Actual Lap Times")
st.dataframe(
	filtered,
	use_container_width=True,
	hide_index=True,
)

# Plot
st.subheader("Lap Time Comparison (Mean per Lap)")
plot_lap_times(filtered)

st.caption("Tip: Use the sidebar to change Year/GP/Session and apply driver/team filters.")
