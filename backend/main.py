import os
import sys
from typing import Optional, List, Dict, Any, Tuple

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_ingestion import get_event_schedule, get_winner_prediction_data
from winner_feature_engineering import engineer_winner_features
from winner_model import (
    load_best_winner_model, align_winner_features_to_model, predict_winner_probabilities,
    add_regulation_features,
)


app = FastAPI(title="F1 Grand Prix Winner Prediction API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


class ScenarioProbs(BaseModel):
    best_case: float
    likely: float
    worst_case: float


class DriverPrediction(BaseModel):
    driver: str
    team: str
    win_probability: float          # the "likely" scenario — kept for backward compat
    scenarios: ScenarioProbs
    grid_position: Optional[int] = None


class WinnerProbabilitiesOutput(BaseModel):
    race: str
    year: int
    chaos_index: float
    sc_rate: float
    has_practice_data: bool
    predictions: List[DriverPrediction]


# ---------------------------------------------------------------------------
# Shared prediction helper
# ---------------------------------------------------------------------------

def _build_predictions(
    winner_data: pd.DataFrame,
    year: int,
    gp_name: str,
    model,
    expected_features: List[str],
) -> WinnerProbabilitiesOutput:
    X, _ = engineer_winner_features(
        winner_data, year, gp_name,
        include_historical=True,
        include_practice=True,
    )
    X = align_winner_features_to_model(X, expected_features)

    if X.empty:
        raise HTTPException(status_code=400, detail="Could not construct features from race data.")

    base_probabilities = predict_winner_probabilities(model, X)

    # Check practice cache availability
    has_practice_data = False
    try:
        from practice_data_ingestion import load_practice_features
        pf = load_practice_features(year, gp_name)
        has_practice_data = pf is not None and not pf.empty
    except Exception:
        pass

    # Chaos-adjusted scenario ranges
    chaos_index, sc_rate = 0.3, 0.4
    scenarios_by_driver: List[Dict[str, float]] = []

    try:
        from chaos_matrix import get_chaos_adjusted_predictions
        from data_ingestion import get_qualifying_results

        wind_speed = 0.0
        if has_practice_data:
            from practice_data_ingestion import load_practice_features
            pf = load_practice_features(year, gp_name)
            if pf is not None and "AvgWindSpeed" in pf.columns:
                wind_speed = float(pf["AvgWindSpeed"].mean())

        quali_df = get_qualifying_results(year, gp_name)
        chaos_result = get_chaos_adjusted_predictions(
            gp_name,
            base_probabilities,
            qualifying_df=quali_df if not quali_df.empty else None,
            weather_wind_speed=wind_speed,
        )
        chaos_index = chaos_result["chaos_index"]
        sc_rate = chaos_result["sc_rate"]
        scenarios = chaos_result["scenarios"]
        for i in range(len(base_probabilities)):
            scenarios_by_driver.append({
                "best_case": float(scenarios["best_case"][i]),
                "likely":    float(scenarios["likely"][i]),
                "worst_case": float(scenarios["worst_case"][i]),
            })
    except Exception:
        for p in base_probabilities:
            scenarios_by_driver.append({
                "best_case": float(p), "likely": float(p), "worst_case": float(p),
            })

    predictions = []
    for i, (_, row) in enumerate(winner_data.iterrows()):
        if i >= len(base_probabilities):
            break
        grid_pos = row.get("GridPosition")
        sc = scenarios_by_driver[i] if i < len(scenarios_by_driver) else {
            "best_case": float(base_probabilities[i]),
            "likely":    float(base_probabilities[i]),
            "worst_case": float(base_probabilities[i]),
        }
        predictions.append(DriverPrediction(
            driver=str(row.get("Driver", "Unknown")),
            team=str(row.get("Team", "Unknown")),
            win_probability=sc["likely"],
            scenarios=ScenarioProbs(**sc),
            grid_position=int(grid_pos) if pd.notna(grid_pos) else None,
        ))

    predictions.sort(key=lambda x: x.win_probability, reverse=True)

    return WinnerProbabilitiesOutput(
        race=gp_name,
        year=year,
        chaos_index=round(chaos_index, 3),
        sc_rate=round(sc_rate, 3),
        has_practice_data=has_practice_data,
        predictions=predictions,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/years")
async def years() -> Dict[str, List[int]]:
    return {"years": list(range(2018, 2027))}


@app.get("/schedule")
async def schedule(year: int = Query(..., ge=2010, le=2100)) -> Dict[str, Any]:
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
    """
    Return win probabilities for all drivers, ranked highest first.
    Includes best_case / likely / worst_case scenario ranges.
    Automatically uses practice session cache if available.
    """
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

    return _build_predictions(winner_data, year, gp_name, model, expected_features)


@app.post("/predict-winner", response_model=WinnerProbabilitiesOutput)
async def predict_winner(payload: PredictWinnerInput) -> WinnerProbabilitiesOutput:
    """Predict winner probabilities, optionally filtered to a single driver."""
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

    if payload.driver:
        if "Driver" not in winner_data.columns or not (winner_data["Driver"] == payload.driver).any():
            raise HTTPException(status_code=404, detail=f"Driver '{payload.driver}' not found.")
        winner_data = winner_data[winner_data["Driver"] == payload.driver].copy()

    return _build_predictions(winner_data, payload.year, gp_name, model, expected_features)


# ---------------------------------------------------------------------------
# Practice precompute endpoint (triggered manually after FP3)
# ---------------------------------------------------------------------------

def _run_practice_precompute(year: int, gp_name: str) -> None:
    try:
        from practice_data_ingestion import extract_practice_features, save_practice_features
        print(f"[precompute] Starting: {year} {gp_name}")
        df = extract_practice_features(year, gp_name)
        if not df.empty:
            path = save_practice_features(df, year, gp_name)
            print(f"[precompute] Done → {path}")
        else:
            print(f"[precompute] No data for {year} {gp_name}")
    except Exception as e:
        print(f"[precompute] Error: {e}")


@app.post("/precompute-practice/{year}/{gp}")
async def precompute_practice(
    year: int,
    gp: str,
    background_tasks: BackgroundTasks,
) -> Dict[str, str]:
    """
    Trigger practice data extraction in the background.
    Call this after FP3 ends (Saturday morning) for the upcoming race.
    Takes 10-45 min. Check /practice-status to see when it's ready.
    """
    gp_name = _resolve_gp_name(year, gp)
    background_tasks.add_task(_run_practice_precompute, year, gp_name)
    return {
        "status": "started",
        "message": f"Practice precomputation started for {year} {gp_name}. Takes 10-45 min.",
        "cache_key": f"{year}_{gp_name.replace(' ', '_').lower()}_practice.json",
    }


@app.get("/practice-status/{year}/{gp}")
async def practice_status(year: int, gp: str) -> Dict[str, Any]:
    """Check whether practice data has been precomputed and cached for a GP."""
    gp_name = _resolve_gp_name(year, gp)
    try:
        from practice_data_ingestion import load_practice_features
        pf = load_practice_features(year, gp_name)
        if pf is not None and not pf.empty:
            return {
                "available": True,
                "drivers": len(pf),
                "features": len(pf.columns),
                "gp": gp_name,
                "year": year,
            }
    except Exception:
        pass
    return {"available": False, "gp": gp_name, "year": year}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8011"))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
