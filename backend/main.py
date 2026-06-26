import os
import sys
from typing import Optional, List, Dict, Any, Tuple

# Load .env before anything else (no-op if file absent or dotenv not installed)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from security import load_env
load_env()

from fastapi import FastAPI, HTTPException, Query, Request, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
import uvicorn
import asyncio
import pandas as pd

from security import (
    SecurityHeadersMiddleware,
    get_allowed_origins,
    RateLimits,
    sanitize_gp_name,
    validate_year,
)

# Optional slowapi rate limiter -- gracefully disabled if package not installed
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    _limiter = Limiter(
        key_func=get_remote_address,
        enabled=os.getenv("DISABLE_RATE_LIMITING", "false").lower() != "true",
    )
    _RATE_LIMITING = True
except ImportError:
    _limiter = None
    _RATE_LIMITING = False
    print("[security] slowapi not installed -- rate limiting disabled")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_ingestion import get_event_schedule, get_winner_prediction_data
from winner_feature_engineering import engineer_winner_features
from winner_model import (
    load_best_winner_model, align_winner_features_to_model, predict_winner_probabilities,
)


app = FastAPI(
    title="F1 Grand Prix Winner Prediction API",
    version="3.1.0",
    docs_url="/docs" if os.getenv("ENVIRONMENT", "development") != "production" else None,
    redoc_url=None,
)

# Security headers (outermost -- wraps everything)
app.add_middleware(SecurityHeadersMiddleware)

# CORS
_allowed_origins = get_allowed_origins()
print(f"[security] CORS allowed origins: {_allowed_origins}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

# Rate limiter
if _RATE_LIMITING and _limiter:
    app.state.limiter = _limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def _limit(rate: str):
    """Return a slowapi limiter decorator, or a no-op if slowapi is absent."""
    if _RATE_LIMITING and _limiter:
        return _limiter.limit(rate)
    def _noop(fn):
        return fn
    return _noop


_winner_model_cache: Optional[Tuple[object, List[str]]] = None

# In-memory result cache: key="year_gp" → (fetched_at_unix, WinnerProbabilitiesOutput)
# Survives the lifetime of the process; wiped on cold start.
_predictions_cache: Dict[str, Tuple[float, Any]] = {}
_PREDICTIONS_TTL = 3600  # seconds — re-fetch from FastF1 after 1 hour


def _predictions_cache_get(year: int, gp: str) -> Optional[Any]:
    import time
    key = f"{year}_{gp.lower()}"
    if key in _predictions_cache:
        ts, result = _predictions_cache[key]
        if time.time() - ts < _PREDICTIONS_TTL:
            return result
        del _predictions_cache[key]
    return None


def _predictions_cache_set(year: int, gp: str, result: Any) -> None:
    import time
    _predictions_cache[f"{year}_{gp.lower()}"] = (time.time(), result)


from live_timing_engine import start_engine, get_live_state, is_session_live, get_engine


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class _LiveConnectionManager:
    def __init__(self):
        self._clients: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._clients.append(ws)
        print(f"[ws/live] client connected — total {len(self._clients)}")

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._clients = [c for c in self._clients if c is not ws]
        print(f"[ws/live] client disconnected — total {len(self._clients)}")

    async def broadcast(self, payload: dict):
        import json
        msg = json.dumps(payload)
        dead = []
        for ws in list(self._clients):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    @property
    def count(self) -> int:
        return len(self._clients)


_live_mgr = _LiveConnectionManager()


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
    # Start live timing engine
    start_engine()
    # Kick off background tasks
    asyncio.create_task(_prewarm_recent_race())
    asyncio.create_task(_live_broadcast_loop())


async def _prewarm_recent_race():
    """Pre-fetch FastF1 data for the most recent race so first user request is fast."""
    import time
    await asyncio.sleep(2)  # Let startup finish first
    try:
        from data_ingestion import get_event_schedule
        import datetime
        year = datetime.datetime.now().year
        schedule = get_event_schedule(year)
        if schedule is None or schedule.empty:
            return
        today = datetime.datetime.now()
        past = schedule[pd.to_datetime(schedule.get("EventDate", schedule.iloc[:, 0])) < today]
        if past.empty:
            return
        last = past.iloc[-1]
        gp_name = str(last.get("EventName", last.get("OfficialEventName", "")))
        if not gp_name:
            return
        # Check cache first
        if _predictions_cache_get(year, gp_name) is not None:
            print(f"[prewarm] Already cached: {year} {gp_name}")
            return
        print(f"[prewarm] Pre-warming: {year} {gp_name}")
        t0 = time.time()
        model, expected_features = _get_winner_model()
        winner_data = get_winner_prediction_data(year, gp_name)
        if not winner_data.empty:
            result = _build_predictions(winner_data, year, gp_name, model, expected_features)
            _predictions_cache_set(year, gp_name, result)
            print(f"[prewarm] Done in {time.time()-t0:.1f}s — {gp_name}")
    except Exception as e:
        print(f"[prewarm] Skipped: {e}")


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
    year: int = Field(..., ge=2018, le=2027)
    gp: str
    driver: Optional[str] = None

    @field_validator("year")
    @classmethod
    def _check_year(cls, v):
        return validate_year(v)

    @field_validator("gp")
    @classmethod
    def _check_gp(cls, v):
        return sanitize_gp_name(v)

    @field_validator("driver")
    @classmethod
    def _check_driver(cls, v):
        if v is None:
            return v
        v = v.strip().upper()
        if not v or len(v) > 20:
            raise ValueError("Driver code must be 1-20 characters.")
        return v


class ScenarioProbs(BaseModel):
    best_case: float
    likely: float
    worst_case: float


class DriverPrediction(BaseModel):
    driver: str
    team: str
    win_probability: float
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

    has_practice_data = False
    try:
        from practice_data_ingestion import load_practice_features
        pf = load_practice_features(year, gp_name)
        has_practice_data = pf is not None and not pf.empty
    except Exception:
        pass

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
@_limit(RateLimits.HEALTH)
async def health(request: Request) -> Dict[str, str]:
    return {"status": "ok", "version": "3.1.0"}


@app.get("/years")
@_limit(RateLimits.METADATA)
async def years(request: Request) -> Dict[str, List[int]]:
    return {"years": list(range(2018, 2027))}


@app.get("/schedule")
@_limit(RateLimits.METADATA)
async def schedule(request: Request, year: int = Query(..., ge=2018, le=2027)) -> Dict[str, Any]:
    try:
        validate_year(year)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    df = get_event_schedule(year)
    if df is None or df.empty or "EventName" not in df.columns:
        raise HTTPException(status_code=404, detail=f"No events found for {year}.")
    events = df["EventName"].dropna().unique().tolist()
    return {"year": year, "events": events}


@app.get("/winner-probabilities", response_model=WinnerProbabilitiesOutput)
@_limit(RateLimits.PREDICT)
async def get_winner_probabilities(
    request: Request,
    year: int = Query(..., ge=2018, le=2027),
    gp: str = Query(..., description="Grand Prix name", max_length=80),
) -> WinnerProbabilitiesOutput:
    """Return win probabilities for all drivers. Includes scenario ranges."""
    try:
        validate_year(year)
        gp = sanitize_gp_name(gp)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    model, expected_features = _get_winner_model()
    gp_name = _resolve_gp_name(year, gp)

    cached = _predictions_cache_get(year, gp_name)
    if cached is not None:
        return cached

    try:
        winner_data = get_winner_prediction_data(year, gp_name)
        if winner_data.empty:
            raise HTTPException(status_code=404, detail="No race data found for this Grand Prix.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load race data: {e}")

    result = _build_predictions(winner_data, year, gp_name, model, expected_features)
    _predictions_cache_set(year, gp_name, result)
    return result


@app.post("/predict-winner", response_model=WinnerProbabilitiesOutput)
@_limit(RateLimits.PREDICT)
async def predict_winner(request: Request, payload: PredictWinnerInput) -> WinnerProbabilitiesOutput:
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
# Practice precompute endpoints
# ---------------------------------------------------------------------------

def _run_practice_precompute(year: int, gp_name: str) -> None:
    try:
        from practice_data_ingestion import extract_practice_features, save_practice_features
        print(f"[precompute] Starting: {year} {gp_name}")
        df = extract_practice_features(year, gp_name)
        if not df.empty:
            path = save_practice_features(df, year, gp_name)
            print(f"[precompute] Done -> {path}")
        else:
            print(f"[precompute] No data for {year} {gp_name}")
    except Exception as e:
        print(f"[precompute] Error: {e}")


@app.post("/precompute-practice/{year}/{gp}")
@_limit(RateLimits.PRECOMPUTE)
async def precompute_practice(
    request: Request,
    year: int,
    gp: str,
    background_tasks: BackgroundTasks,
) -> Dict[str, str]:
    """Trigger practice data extraction in the background after FP3."""
    gp_name = _resolve_gp_name(year, gp)
    background_tasks.add_task(_run_practice_precompute, year, gp_name)
    return {
        "status": "started",
        "message": f"Practice precomputation started for {year} {gp_name}. Takes 10-45 min.",
        "cache_key": f"{year}_{gp_name.replace(' ', '_').lower()}_practice.json",
    }


@app.get("/practice-status/{year}/{gp}")
@_limit(RateLimits.METADATA)
async def practice_status(request: Request, year: int, gp: str) -> Dict[str, Any]:
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


# ---------------------------------------------------------------------------
# Phase 2 -- Live Timing Endpoints
# ---------------------------------------------------------------------------

def _get_session_type(session_type: str) -> str:
    st = session_type.upper()
    if st in ("R", "RACE"):
        return "R"
    if st in ("Q", "QUALI"):
        return "Q"
    if st in ("FP1", "FP2", "FP3"):
        return st
    return "R"


@app.get("/timing/{year}/{gp}")
@_limit(RateLimits.TIMING)
async def get_timing(
    request: Request,
    year: int,
    gp: str,
    session_type: str = Query("R", description="Session type: R, Q, FP1, FP2, FP3"),
    lap: Optional[int] = Query(None, description="Return snapshot at this lap (omit for all laps)"),
) -> Dict[str, Any]:
    """
    Lap-by-lap timing data for a session with sector colour codes, tyres, pit flags.
    First call may take 30-90s while FastF1 loads; subsequent calls are instant (cached).
    """
    try:
        validate_year(year)
        gp = sanitize_gp_name(gp)
        st = _get_session_type(session_type)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    gp_name = _resolve_gp_name(year, gp)

    try:
        from backend.live_timing import load_timing_data, get_lap_snapshot
        data = load_timing_data(year, gp_name, st)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load session: {e}")

    if lap is not None:
        snapshot = get_lap_snapshot(data, lap)
        return {
            "year": year, "gp": gp_name, "session_type": st,
            "lap": lap, "total_laps": data["total_laps"],
            "snapshot": snapshot,
            "race_control": [m for m in data["race_control"] if (m.get("lap") or 0) <= lap],
        }

    return data


@app.get("/race-control/{year}/{gp}")
@_limit(RateLimits.TIMING)
async def get_race_control(
    request: Request,
    year: int,
    gp: str,
    session_type: str = Query("R"),
) -> Dict[str, Any]:
    """Race control messages: safety cars, flags, DRS, incidents, and weather data."""
    try:
        validate_year(year)
        gp = sanitize_gp_name(gp)
        st = _get_session_type(session_type)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    gp_name = _resolve_gp_name(year, gp)

    try:
        from backend.live_timing import load_timing_data
        data = load_timing_data(year, gp_name, st)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load session: {e}")

    return {
        "year":         year,
        "gp":           gp_name,
        "session_type": st,
        "race_control": data.get("race_control", []),
        "weather":      data.get("weather", []),
    }


# ---------------------------------------------------------------------------
# Live timing broadcast loop (runs as asyncio background task)
# ---------------------------------------------------------------------------

async def _live_broadcast_loop():
    """Push engine state to all connected /ws/live clients every POLL_INTERVAL seconds."""
    import json
    while True:
        try:
            if _live_mgr.count > 0:
                state = get_live_state()
                await _live_mgr.broadcast({"type": "state", "data": state})
        except Exception as e:
            print(f"[ws/live] broadcast error: {e}")
        await asyncio.sleep(3)


# ---------------------------------------------------------------------------
# /ws/live  — WebSocket endpoint for real-time pit wall
# ---------------------------------------------------------------------------

@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    await _live_mgr.connect(ws)
    try:
        # Send current state immediately on connect
        state = get_live_state()
        await ws.send_text(__import__("json").dumps({"type": "state", "data": state}))
        # Keep connection alive; client sends pings
        while True:
            try:
                msg = await asyncio.wait_for(ws.receive_text(), timeout=30)
                if msg == "ping":
                    await ws.send_text('{"type":"pong"}')
            except asyncio.TimeoutError:
                await ws.send_text('{"type":"ping"}')
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[ws/live] error: {e}")
    finally:
        await _live_mgr.disconnect(ws)


# ---------------------------------------------------------------------------
# /car-telemetry  — FastF1 telemetry for a driver's fastest lap (historical)
# ---------------------------------------------------------------------------

@app.get("/car-telemetry/{year}/{gp}/{driver}")
async def get_car_telemetry(
    request: Request,
    year: int,
    gp: str,
    driver: str,
    session_type: str = Query("R"),
) -> Dict[str, Any]:
    """
    Return throttle/brake/speed/gear/DRS/RPM traces for a driver's fastest lap.
    Loads FastF1 with telemetry=True — slow on first call (~30s), cached after.
    """
    import fastf1
    import pandas as pd

    gp_name = _resolve_gp_name(year, gp)
    st = _get_session_type(session_type)
    cache_key = (year, gp_name.lower(), st, driver.upper(), "telem")

    with _CACHE_LOCK:
        entry = _PREDICTIONS_CACHE.get(str(cache_key))
        if entry and (time.time() - entry.get("ts", 0)) < 3600:
            return entry["data"]

    try:
        session = fastf1.get_session(year, gp_name, st)
        session.load(laps=True, telemetry=True, weather=False, messages=False)

        drv_laps = session.laps.pick_drivers(driver.upper())
        if drv_laps.empty:
            raise HTTPException(status_code=404, detail=f"No laps found for {driver}")

        fastest = drv_laps.pick_fastest()
        tel = fastest.get_telemetry()

        # Normalise distance to 0-100%
        max_dist = float(tel["Distance"].max()) if "Distance" in tel.columns and len(tel) > 0 else 1.0

        rows = []
        for _, row in tel.iterrows():
            rows.append({
                "dist":     round(float(row.get("Distance", 0)) / max_dist * 100, 2),
                "speed":    int(row.get("Speed", 0)),
                "throttle": int(row.get("Throttle", 0)),
                "brake":    bool(row.get("Brake", False)),
                "gear":     int(row.get("nGear", row.get("Gear", 0))),
                "drs":      int(row.get("DRS", 0)),
                "rpm":      int(row.get("RPM", 0)),
            })

        lap_time = None
        try:
            lt = fastest["LapTime"]
            if not pd.isna(lt):
                t = lt.total_seconds()
                lap_time = f"{int(t//60)}:{t%60:06.3f}"
        except Exception:
            pass

        result = {
            "driver":       driver.upper(),
            "gp":           gp_name,
            "year":         year,
            "session_type": st,
            "lap_time":     lap_time,
            "compound":     str(fastest.get("Compound", "")),
            "telemetry":    rows,
        }

        with _CACHE_LOCK:
            _PREDICTIONS_CACHE[str(cache_key)] = {"data": result, "ts": time.time()}

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# /live-car-data  — OpenF1 real-time car data (throttle/brake/speed/gear/DRS)
# ---------------------------------------------------------------------------

@app.get("/live-car-data/{driver_number}")
async def get_live_car_data(
    request: Request,
    driver_number: int,
) -> Dict[str, Any]:
    """
    Return recent car telemetry for a driver from OpenF1 (live sessions only).
    Samples the last 200 data points (~1 lap worth).
    """
    import httpx

    state = get_live_state()
    session = state.get("session") or {}
    sk = session.get("session_key")

    if not sk:
        raise HTTPException(status_code=503, detail="No active session")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.openf1.org/v1/car_data",
                params={"driver_number": driver_number, "session_key": sk},
            )
            r.raise_for_status()
            data = r.json()

        # Keep last 200 samples (roughly 1 lap)
        data = data[-200:] if len(data) > 200 else data

        rows = [{
            "date":     row.get("date"),
            "speed":    row.get("speed", 0),
            "throttle": row.get("throttle", 0),
            "brake":    row.get("brake", False),
            "gear":     row.get("n_gear", 0),
            "drs":      row.get("drs", 0),
            "rpm":      row.get("rpm", 0),
        } for row in data]

        return {
            "driver_number": driver_number,
            "session_key":   sk,
            "is_live":       state.get("is_live", False),
            "samples":       len(rows),
            "car_data":      rows,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# /live-status  — REST: is a session currently live?
# ---------------------------------------------------------------------------

@app.get("/live-status")
async def live_status() -> Dict[str, Any]:
    """Returns current session info and whether it is live right now."""
    state = get_live_state()
    session = state.get("session") or {}
    return {
        "is_live":      state.get("is_live", False),
        "session_name": session.get("name", ""),
        "session_type": session.get("type", ""),
        "gp":           session.get("gp", ""),
        "circuit":      session.get("circuit", ""),
        "year":         session.get("year"),
        "date_start":   session.get("date_start"),
        "date_end":     session.get("date_end"),
        "track_status": state.get("track_status", "AllClear"),
        "lap_count":    state.get("lap_count", {}),
        "drivers_live": len(state.get("leaderboard", [])),
        "last_updated": state.get("last_updated"),
    }