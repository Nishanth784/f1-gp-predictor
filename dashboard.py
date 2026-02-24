import os
from typing import List, Tuple, Dict

import numpy as np
import pandas as pd
import streamlit as st
import joblib

from data_ingestion import get_event_schedule, get_session_data
from feature_engineering import engineer_features
from model import load_best_model, align_features_to_model


st.set_page_config(page_title="F1 Prediction Dashboard", layout="wide")


def load_or_train_model(X: pd.DataFrame, y: pd.Series, model_path: str):
	loaded = load_best_model(model_path)
	if loaded is not None:
		return loaded[0], loaded[1], {}
	# Quick fallback model
	from sklearn.ensemble import GradientBoostingRegressor
	from sklearn.model_selection import train_test_split
	from sklearn.metrics import mean_absolute_error, mean_squared_error
	X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
	model = GradientBoostingRegressor(random_state=42)
	model.fit(X_train, y_train)
	pred = model.predict(X_test)
	mae = float(mean_absolute_error(y_test, pred))
	rmse = float(np.sqrt(mean_squared_error(y_test, pred)))
	return model, list(X.columns), {"MAE": mae, "RMSE": rmse}


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
	if df_pred.empty or "LapNumber" not in df_pred.columns:
		st.info("No data to plot.")
		return
	agg = df_pred.groupby("LapNumber")[["ActualLapTime", "PredictedLapTime"]].mean().reset_index()
	st.line_chart(agg.set_index("LapNumber"))


with st.sidebar:
	st.header("Controls")
	year = st.number_input("Year", min_value=2018, max_value=2025, value=2023, step=1)
	schedule = get_event_schedule(int(year))
	gp_names = schedule["EventName"].dropna().unique().tolist() if "EventName" in schedule.columns else []
	default_gp = gp_names[0] if gp_names else "Monaco"
	gp = st.selectbox("Grand Prix", options=gp_names if gp_names else [default_gp], index=0)
	session_label_to_code = {"Qualifying": "Q", "Race": "R"}
	session_label = st.selectbox("Session", options=list(session_label_to_code.keys()), index=0)
	session_code = session_label_to_code[session_label]
	model_path = os.path.join("models", "best_model.joblib")
	include_sprint = st.toggle("Include Sprint Sessions (if available)", value=True)

st.title("F1 Grand Prix Prediction - Dashboard")

with st.spinner("Loading session data..."):
	df_clean = get_session_data(int(year), gp, session_code, include_sprint=include_sprint)

if df_clean.empty:
	st.warning("No session data available.")
	st.stop()

with st.spinner("Preparing features and loading model..."):
	X, y = engineer_features(df_clean)
	model, features, train_metrics = load_or_train_model(X, y, model_path)

if train_metrics:
	st.caption(f"Model trained on the fly (no saved model found). MAE={train_metrics['MAE']:.3f}s, RMSE={train_metrics['RMSE']:.3f}s")

with st.spinner("Running predictions..."):
	pred_table = build_predictions_table(df_clean, model, features)

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

if not filtered.empty:
	mae = float((filtered["PredictedLapTime"] - filtered["ActualLapTime"]).abs().mean())
	rmse = float(np.sqrt(((filtered["PredictedLapTime"] - filtered["ActualLapTime"]) ** 2).mean()))
	st.metric(label="MAE (s)", value=f"{mae:.3f}")
	st.metric(label="RMSE (s)", value=f"{rmse:.3f}")

st.subheader("Predicted vs Actual Lap Times")
st.dataframe(filtered, use_container_width=True, hide_index=True)

st.subheader("Lap Time Comparison (Mean per Lap)")
plot_lap_times(filtered)

st.caption("Use the sidebar to tweak Year/GP/Session, include sprint sessions, and filter by driver/team.")
