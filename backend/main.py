import os
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import numpy as np
import pandas as pd

from data_ingestion import get_session_data, get_event_schedule, get_winner_prediction_data
from feature_engineering import engineer_features
from model import load_best_model, align_features_to_model
from winner_feature_engineering import engineer_winner_features
from winner_model import (
	load_best_winner_model, align_winner_features_to_model, predict_winner_probabilities,
	prepare_race_level_features, add_regulation_features
)
from race_aggregation import aggregate_laps_to_race


app = FastAPI(title="F1 Grand Prix Winner Prediction API", version="1.0.0")

# CORS (adjust origins as needed)
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

# Load winner model on startup (cached)
_winner_model_cache: Optional[Tuple[object, List[str]]] = None


@app.on_event("startup")
async def load_winner_model_on_startup():
	"""Load winner model on application startup."""
	global _winner_model_cache
	try:
		_winner_model_cache = load_best_winner_model()
		if _winner_model_cache is not None:
			print(f"Loaded winner model with {len(_winner_model_cache[1])} features")
		else:
			print("Warning: No winner model found. Train and save a winner model first.")
	except Exception as e:
		print(f"Error loading winner model on startup: {e}")


def get_winner_model() -> Tuple[object, List[str]]:
	"""Get cached winner model or load it if not cached."""
	global _winner_model_cache
	if _winner_model_cache is None:
		_winner_model_cache = load_best_winner_model()
	if _winner_model_cache is None:
		raise HTTPException(status_code=400, detail="No trained winner model found. Train and save a winner model first.")
	return _winner_model_cache


class PredictInput(BaseModel):
	year: int = Field(..., ge=2010, le=2100)
	gp: str
	session_type: str = Field(..., description="Q or R")
	driver: str
	team: Optional[str] = None
	tyre: Optional[str] = Field(None, description="Compound, e.g., SOFT, MEDIUM, HARD")
	weather: Optional[Dict[str, Optional[float]]] = Field(default=None, description="{AirTemp, Humidity}")


class PredictOutput(BaseModel):
	predicted_lap_time: float
	features_used: List[str]


class PredictWinnerInput(BaseModel):
	year: int = Field(..., ge=2010, le=2100)
	gp: str
	driver: Optional[str] = None
	team: Optional[str] = None


class PredictWinnerOutput(BaseModel):
	driver: str
	team: str
	win_probability: float
	grid_position: Optional[int] = None


class WinnerProbabilitiesOutput(BaseModel):
	probabilities: List[Dict[str, Any]]


class WinnerPredictionResponse(BaseModel):
	race: str
	year: int
	predictions: List[Dict[str, float]]


def _resolve_gp_name(year: int, gp_input: str) -> str:
	"""Resolve a Grand Prix name case-insensitively (and by partial match) to the official EventName.
	Raises HTTPException if not found.
	"""
	schedule = get_event_schedule(year)
	if schedule is None or schedule.empty or "EventName" not in schedule.columns:
		raise HTTPException(status_code=404, detail="Event schedule unavailable for the given year.")
	names = schedule["EventName"].astype(str).tolist()
	lower_to_name = {n.lower(): n for n in names}
	candidate = lower_to_name.get(gp_input.lower())
	if candidate:
		return candidate
	# try partial match
	for n in names:
		if gp_input.lower() in n.lower():
			return n
	raise HTTPException(status_code=404, detail=f"Grand Prix '{gp_input}' not found in {year} schedule.")


@app.get("/health")
async def health() -> Dict[str, str]:
	return {"status": "ok"}


@app.get("/events")
async def events(year: int = Query(..., ge=2010, le=2100)) -> Dict[str, Any]:
	schedule = get_event_schedule(year)
	if schedule is None or schedule.empty or "EventName" not in schedule.columns:
		raise HTTPException(status_code=404, detail="No events found for the given year.")
	return {"events": schedule["EventName"].dropna().unique().tolist()}


@app.get("/years")
async def years() -> Dict[str, Any]:
	yrs = list(range(2018, 2026))
	return {"years": yrs}


@app.get("/metadata")
async def metadata(
	year: int = Query(..., ge=2010, le=2100),
	gp: Optional[str] = Query(None),
) -> Dict[str, Any]:
	# Resolve GP if provided
	gp_name = None
	if gp:
		try:
			gp_name = _resolve_gp_name(year, gp)
		except HTTPException:
			gp_name = None

	# Sessions and events
	schedule = get_event_schedule(year)
	gps = schedule["EventName"].dropna().unique().tolist() if (schedule is not None and not schedule.empty and "EventName" in schedule.columns) else []
	sessions = ["Q", "R"]

	# Drivers/Teams from the qualifying (or race) session if gp provided
	drivers: List[str] = []
	teams: List[str] = []
	if gp_name:
		for sess in ["Q", "R"]:
			try:
				df = get_session_data(year, gp_name, sess, include_sprint=False)
				if not df.empty:
					if "Driver" in df.columns:
						drivers = sorted(list(set(drivers) | set(df["Driver"].dropna().astype(str).unique().tolist())))
					if "Team" in df.columns:
						teams = sorted(list(set(teams) | set(df["Team"].dropna().astype(str).unique().tolist())))
			except Exception:
				pass

	tyres = ["SOFT", "MEDIUM", "HARD"]
	return {"gps": gps, "sessions": sessions, "drivers": drivers, "teams": teams, "tyres": tyres}


@app.post("/predict", response_model=PredictOutput)
async def predict(payload: PredictInput):
	loaded = load_best_model()
	if loaded is None:
		raise HTTPException(status_code=400, detail="No trained model found. Train and save a model first.")
	model, expected_features = loaded

	# Resolve GP name (case-insensitive, partial ok)
	gp_name = _resolve_gp_name(payload.year, payload.gp)

	# Build a single-row DataFrame using a minimal session snapshot
	try:
		df = get_session_data(payload.year, gp_name, payload.session_type, include_sprint=False)
		if df.empty:
			raise HTTPException(status_code=404, detail="Session data not found.")
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to load session: {e}")

	# Pick a representative row and override with user inputs
	row = df.iloc[[0]].copy()
	row["Driver"] = payload.driver
	if payload.team is not None:
		row["Team"] = payload.team
	if payload.tyre is not None:
		row["Compound"] = payload.tyre
	if payload.weather:
		if "AirTemp" in payload.weather and payload.weather["AirTemp"] is not None:
			row["AirTemp"] = float(payload.weather["AirTemp"])  # type: ignore[index]
		if "Humidity" in payload.weather and payload.weather["Humidity"] is not None:
			row["Humidity"] = float(payload.weather["Humidity"])  # type: ignore[index]

	X, _ = engineer_features(row)
	X = align_features_to_model(X, expected_features)
	if X.empty:
		raise HTTPException(status_code=400, detail="Could not construct features from provided inputs.")

	try:
		pred = float(model.predict(X)[0])
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Prediction failed: {e}")

	return PredictOutput(predicted_lap_time=pred, features_used=list(X.columns))


@app.get("/compare")
async def compare(
	year: int = Query(..., ge=2010, le=2100),
	gp: str = Query(...),
	session_type: str = Query(..., description="Q or R"),
) -> Dict[str, Any]:
	loaded = load_best_model()
	if loaded is None:
		raise HTTPException(status_code=400, detail="No trained model found. Train and save a model first.")
	model, expected_features = loaded

	# Resolve GP name
	gp_name = _resolve_gp_name(year, gp)

	try:
		df = get_session_data(year, gp_name, session_type, include_sprint=False)
		if df.empty:
			raise HTTPException(status_code=404, detail="Session data not found.")
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to load session: {e}")

	X, y = engineer_features(df)
	X = align_features_to_model(X, expected_features)
	if X.empty:
		raise HTTPException(status_code=400, detail="No features available for this session.")

	pred = model.predict(X)
	out = pd.DataFrame({
		"Driver": df.get("Driver", pd.Series([None]*len(X))).values,
		"Team": df.get("Team", pd.Series([None]*len(X))).values,
		"LapNumber": df.get("LapNumber", pd.Series([None]*len(X))).values,
		"ActualLapTime": y.values if y is not None and not y.empty else np.nan,
		"PredictedLapTime": pred,
	})
	return {"rows": out.to_dict(orient="records")}


@app.post("/predict-winner", response_model=PredictWinnerOutput)
async def predict_winner(payload: PredictWinnerInput):
	"""Predict winner probability for a specific driver in a Grand Prix."""
	loaded = load_best_winner_model()
	if loaded is None:
		raise HTTPException(status_code=400, detail="No trained winner model found. Train and save a winner model first.")
	model, expected_features = loaded
	
	# Resolve GP name
	gp_name = _resolve_gp_name(payload.year, payload.gp)
	
	# Get winner prediction data
	try:
		winner_data = get_winner_prediction_data(payload.year, gp_name)
		if winner_data.empty:
			raise HTTPException(status_code=404, detail="Race data not found for this Grand Prix.")
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to load race data: {e}")
	
	# Engineer features
	X, _ = engineer_winner_features(winner_data, payload.year, gp_name, include_historical=True)
	X = align_winner_features_to_model(X, expected_features)
	
	if X.empty:
		raise HTTPException(status_code=400, detail="Could not construct features from race data.")
	
	# If driver specified, filter to that driver
	if payload.driver:
		if "Driver" not in winner_data.columns:
			raise HTTPException(status_code=400, detail="Driver column not found in race data.")
		driver_mask = winner_data["Driver"] == payload.driver
		if not driver_mask.any():
			raise HTTPException(status_code=404, detail=f"Driver '{payload.driver}' not found in race data.")
		X = X[driver_mask]
		winner_data = winner_data[driver_mask]
	
	# Predict probabilities
	probabilities = predict_winner_probabilities(model, X)
	
	if len(probabilities) == 0:
		raise HTTPException(status_code=400, detail="No predictions generated.")
	
	# Get driver info
	driver_idx = np.argmax(probabilities) if len(probabilities) > 1 else 0
	driver = str(winner_data.iloc[driver_idx].get("Driver", "Unknown"))
	team = str(winner_data.iloc[driver_idx].get("Team", "Unknown"))
	grid_pos = winner_data.iloc[driver_idx].get("GridPosition", None)
	if pd.notna(grid_pos):
		grid_pos = int(grid_pos)
	else:
		grid_pos = None
	
	return PredictWinnerOutput(
		driver=driver,
		team=team,
		win_probability=float(probabilities[driver_idx]),
		grid_position=grid_pos
	)


@app.get("/winner-probabilities", response_model=WinnerProbabilitiesOutput)
async def get_winner_probabilities(
	year: int = Query(..., ge=2010, le=2100),
	gp: str = Query(...),
) -> WinnerProbabilitiesOutput:
	"""Get winner probabilities for all drivers in a Grand Prix."""
	loaded = load_best_winner_model()
	if loaded is None:
		raise HTTPException(status_code=400, detail="No trained winner model found. Train and save a winner model first.")
	model, expected_features = loaded
	
	# Resolve GP name
	gp_name = _resolve_gp_name(year, gp)
	
	# Get winner prediction data
	try:
		winner_data = get_winner_prediction_data(year, gp_name)
		if winner_data.empty:
			raise HTTPException(status_code=404, detail="Race data not found for this Grand Prix.")
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to load race data: {e}")
	
	# Engineer features
	X, _ = engineer_winner_features(winner_data, year, gp_name, include_historical=True)
	X = align_winner_features_to_model(X, expected_features)
	
	if X.empty:
		raise HTTPException(status_code=400, detail="Could not construct features from race data.")
	
	# Predict probabilities
	probabilities = predict_winner_probabilities(model, X)
	
	# Combine with driver info
	results = []
	for idx, row in winner_data.iterrows():
		if idx < len(probabilities):
			results.append({
				"driver": str(row.get("Driver", "Unknown")),
				"team": str(row.get("Team", "Unknown")),
				"win_probability": float(probabilities[idx]),
				"grid_position": int(row.get("GridPosition", 20)) if pd.notna(row.get("GridPosition")) else None,
				"position": int(row.get("Position", 0)) if pd.notna(row.get("Position")) else None,
			})
	
	# Sort by probability (highest first)
	results.sort(key=lambda x: x["win_probability"], reverse=True)
	
	return WinnerProbabilitiesOutput(probabilities=results)


@app.get("/predict-winner", response_model=WinnerPredictionResponse)
async def predict_winner_get(
	year: int = Query(..., ge=2010, le=2100, description="Year of the race"),
	gp: str = Query(..., description="Grand Prix name"),
) -> WinnerPredictionResponse:
	"""Predict winner probabilities for all drivers in a Grand Prix using race-level aggregated features.
	
	Uses the full pipeline:
	1. Load race session data
	2. Generate lap-level predictions using lap-time model
	3. Aggregate to race-level features
	4. Add regulation and chaos features
	5. Predict using winner model
	
	Returns predictions sorted by win_probability descending.
	"""
	# Get winner model (from cache or load)
	model, expected_features = get_winner_model()
	
	# Resolve GP name
	gp_name = _resolve_gp_name(year, gp)
	
	try:
		# Use the full pipeline to prepare race-level features
		# We need to replicate the pipeline to get driver order
		
		# Step 1: Load race session data
		df_laps = get_session_data(year, gp_name, "R", include_sprint=False)
		if df_laps.empty:
			raise HTTPException(status_code=404, detail="Race session data not found.")
		
		# Step 2: Generate lap-level predictions
		lap_model_data = load_best_model()
		if lap_model_data is None:
			raise HTTPException(status_code=400, detail="No lap-time model found. Train lap-time model first.")
		
		lap_model, lap_model_features = lap_model_data
		X_laps, _ = engineer_features(df_laps)
		X_laps_aligned = align_features_to_model(X_laps, lap_model_features)
		
		if X_laps_aligned.empty:
			raise HTTPException(status_code=400, detail="Could not engineer lap-level features.")
		
		predicted_lap_times = lap_model.predict(X_laps_aligned)
		df_laps = df_laps.copy()
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
			raise HTTPException(status_code=404, detail="Could not aggregate race-level features.")
		
		# Step 3.5: Add regulation and chaos features
		df_race_features = add_regulation_features(
			df_race_features,
			year=year,
			gp_name=gp_name,
			driver_col="Driver",
			team_col="Team" if "Team" in df_race_features.columns else None
		)
		
		# Extract features (excluding Driver)
		feature_cols = [c for c in df_race_features.columns if c != "Driver"]
		X = df_race_features[feature_cols].select_dtypes(include=[np.number]).fillna(0.0)
		
		# Get drivers in the same order as features
		drivers = df_race_features["Driver"].tolist() if "Driver" in df_race_features.columns else []
		
		if not drivers or X.empty:
			raise HTTPException(status_code=404, detail="Could not prepare race-level features.")
		
		# Align features to model
		X_aligned = align_winner_features_to_model(X, expected_features)
		
		if X_aligned.empty:
			raise HTTPException(status_code=400, detail="Could not align features to model.")
		
		# Predict probabilities (with chaos-awareness)
		probabilities = predict_winner_probabilities(model, X_aligned)
		
		# Create predictions list
		predictions = []
		for i, driver in enumerate(drivers):
			if i < len(probabilities):
				predictions.append({
					"driver": str(driver),
					"win_probability": float(probabilities[i])
				})
		
		# Sort by win_probability descending
		predictions.sort(key=lambda x: x["win_probability"], reverse=True)
		
		return WinnerPredictionResponse(
			race=gp_name,
			year=year,
			predictions=predictions
		)
		
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to generate predictions: {e}")


if __name__ == "__main__":
	uvicorn.run("backend.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
