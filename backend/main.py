import os
import sys
from typing import Optional, List, Dict, Any, Tuple

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import numpy as np
import pandas as pd

# Add project root to path so we can import shared modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_ingestion import get_event_schedule, get_winner_prediction_data
from winner_feature_engineering import engineer_winner_features
from winner_model import (
	load_best_winner_model, align_winner_features_to_model, predict_winner_probabilities,
	add_regulation_features,
)


app = FastAPI(title="F1 Grand Prix Winner Prediction API", version="2.0.0")

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

# Startup cache for the winner model
_winner_model_cache: Optional[Tuple[object, List[str]]] = None


@app.on_event("startup")
async def load_winner_model_on_startup():
	global _winner_model_cache
	try:
		_winner_model_cache = load_best_winner_model()
		if _winner_model_cache is not None:
			print(f"Winner model loaded ({len(_winner_model_cache[1])} features)")
		else:
			print("Warning: No winner model found. Run main.py to train first.")
	except Exception as e:
		print(f"Error loading winner model: {e}")


def _get_winner_model() -> Tuple[object, List[str]]:
	global _winner_model_cache
	if _winner_model_cache is None:
		_winner_model_cache = load_best_winner_model()
	if _winner_model_cache is None:
		raise HTTPException(
			status_code=503,
			detail="Winner model not trained yet. Run main.py first."
		)
	return _winner_model_cache


def _resolve_gp_name(year: int, gp_input: str) -> str:
	schedule = get_event_schedule(year)
	if schedule is None or schedule.empty or "EventName" not in schedule.columns:
		raise HTTPException(status_code=404, detail=f"No schedule found for {year}.")
	names = schedule["EventName"].astype(str).tolist()
	lower_map = {n.lower(): n for n in names}
	match = lower_map.get(gp_input.lower())
	if match:
		return match
	for n in names:
		if gp_input.lower() in n.lower():
			return n
	raise HTTPException(status_code=404, detail=f"Grand Prix '{gp_input}' not found in {year} schedule.")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class PredictWinnerInput(BaseModel):
	year: int = Field(..., ge=2010, le=2100)
	gp: str
	driver: Optional[str] = None


class DriverPrediction(BaseModel):
	driver: str
	team: str
	win_probability: float
	grid_position: Optional[int] = None


class WinnerProbabilitiesOutput(BaseModel):
	race: str
	year: int
	predictions: List[DriverPrediction]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> Dict[str, str]:
	return {"status": "ok"}


@app.get("/years")
async def years() -> Dict[str, List[int]]:
	return {"years": list(range(2018, 2026))}


@app.get("/schedule")
async def schedule(year: int = Query(..., ge=2010, le=2100)) -> Dict[str, Any]:
	"""Return list of Grand Prix events for a given year."""
	df = get_event_schedule(year)
	if df is None or df.empty or "EventName" not in df.columns:
		raise HTTPException(status_code=404, detail=f"No events found for {year}.")
	events = df["EventName"].dropna().unique().tolist()
	return {"year": year, "events": events}


@app.get("/winner-probabilities", response_model=WinnerProbabilitiesOutput)
async def get_winner_probabilities(
	year: int = Query(..., ge=2010, le=2100),
	gp: str = Query(..., description="Grand Prix name"),
) -> WinnerProbabilitiesOutput:
	"""Return win probabilities for all drivers in a Grand Prix, ranked highest first."""
	model, expected_features = _get_winner_model()
	gp_name = _resolve_gp_name(year, gp)

	try:
		winner_data = get_winner_prediction_data(year, gp_name)
		if winner_data.empty:
			raise HTTPException(status_code=404, detail="No race data found for this Grand Prix.")
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to load race data: {e}")

	X, _ = engineer_winner_features(winner_data, year, gp_name, include_historical=True)
	X = align_winner_features_to_model(X, expected_features)

	if X.empty:
		raise HTTPException(status_code=400, detail="Could not construct features from race data.")

	probabilities = predict_winner_probabilities(model, X)

	predictions = []
	for i, (_, row) in enumerate(winner_data.iterrows()):
		if i >= len(probabilities):
			break
		grid_pos = row.get("GridPosition")
		predictions.append(DriverPrediction(
			driver=str(row.get("Driver", "Unknown")),
			team=str(row.get("Team", "Unknown")),
			win_probability=float(probabilities[i]),
			grid_position=int(grid_pos) if pd.notna(grid_pos) else None,
		))

	predictions.sort(key=lambda x: x.win_probability, reverse=True)

	return WinnerProbabilitiesOutput(race=gp_name, year=year, predictions=predictions)


@app.post("/predict-winner", response_model=WinnerProbabilitiesOutput)
async def predict_winner(payload: PredictWinnerInput) -> WinnerProbabilitiesOutput:
	"""Predict winner probability for all drivers (or a single driver) in a Grand Prix."""
	model, expected_features = _get_winner_model()
	gp_name = _resolve_gp_name(payload.year, payload.gp)

	try:
		winner_data = get_winner_prediction_data(payload.year, gp_name)
		if winner_data.empty:
			raise HTTPException(status_code=404, detail="No race data found for this Grand Prix.")
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to load race data: {e}")

	# Optional: filter to single driver
	if payload.driver:
		if "Driver" not in winner_data.columns or not (winner_data["Driver"] == payload.driver).any():
			raise HTTPException(status_code=404, detail=f"Driver '{payload.driver}' not found.")
		winner_data = winner_data[winner_data["Driver"] == payload.driver].copy()

	X, _ = engineer_winner_features(winner_data, payload.year, gp_name, include_historical=True)
	X = align_winner_features_to_model(X, expected_features)

	if X.empty:
		raise HTTPException(status_code=400, detail="Could not construct features from race data.")

	probabilities = predict_winner_probabilities(model, X)

	predictions = []
	for i, (_, row) in enumerate(winner_data.iterrows()):
		if i >= len(probabilities):
			break
		grid_pos = row.get("GridPosition")
		predictions.append(DriverPrediction(
			driver=str(row.get("Driver", "Unknown")),
			team=str(row.get("Team", "Unknown")),
			win_probability=float(probabilities[i]),
			grid_position=int(grid_pos) if pd.notna(grid_pos) else None,
		))

	predictions.sort(key=lambda x: x.win_probability, reverse=True)

	return WinnerProbabilitiesOutput(race=gp_name, year=payload.year, predictions=predictions)


if __name__ == "__main__":
	port = int(os.getenv("PORT", "8011"))
	uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
