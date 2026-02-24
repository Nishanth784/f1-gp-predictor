# F1 Grand Prix Winner Prediction

## Setup

1. Create venv (Windows):
```
python -m venv .venv
.venv\Scripts\python -m ensurepip --upgrade
.venv\Scripts\python -m pip install --upgrade pip setuptools wheel
```
2. Install deps:
```
.venv\Scripts\python -m pip install -r requirements.txt
```

## Train and Save Model
```
.venv\Scripts\python main.py
```
Outputs `models/best_model.joblib`.

## Streamlit Dashboard
```
.venv\Scripts\python -m streamlit run dashboard.py
```
Use sidebar to select Year/GP/Session; view predicted vs actual table and lap chart.

## Live Weather + Near-Real-Time (optional)
Set an OpenWeatherMap API key and enable demo loop:
```
$env:OPENWEATHER_API_KEY = "<your_api_key>"
$env:RUN_LIVE_DEMO = "1"
.venv\Scripts\python main.py
```

---

# Full-Stack Web App

## Backend (FastAPI)

Install backend requirements:
```
.venv\Scripts\python -m pip install -r backend/requirements.txt
```
Run the server:
```
.venv\Scripts\python -m uvicorn backend.main:app --reload --port 8000
```
API:
- POST /predict {year, gp, session_type, driver, team?, tyre?, weather?}
- GET /compare?year=YYYY&gp=Monaco&session_type=Q

## Frontend (React + Tailwind)

Install Node deps (from frontend/):
```
cd frontend
npm install
npm run dev
```
The app opens on http://localhost:5173

Configure backend URL (optional): set VITE_API_BASE in a `.env` file in `frontend/`.

## Notes
- Sprint weekends supported; enable in the dashboard sidebar.
- Feature engineering includes DriverTeam encoding, sector z-scores, tyre age proxy, and track/phase evolution.

---

# Grand Prix Winner Prediction (2026-ready)

## Overview

The system includes two complementary prediction models:

**Lap-Time Model** (`models/best_model.joblib`):
- Predicts individual lap times (regression)
- Uses lap-level features: sector times, tyre compound, track evolution, weather
- Trained on: Linear Regression, Random Forest, Gradient Boosting
- Use case: Analyze driver performance, compare lap-by-lap predictions

**Winner Model** (`models/winner_model.joblib`):
- Predicts race winners (classification)
- Uses race-level aggregated features: mean/median lap times, consistency, degradation, regulation stability, chaos index
- Trained on: Logistic Regression, Gradient Boosting Classifier
- Use case: Predict Grand Prix winners, assess race outcome probabilities

## Energy-Era Considerations

The winner model accounts for regulation changes affecting race outcomes:

- **Regulation Stability**: Tracks regulation reset years (2014, 2022, 2026). First-year regulations (stability=0) show higher variance as teams adapt.
- **Early Season Variance**: Measures driver/team consistency in the first 3 races, indicating adaptation to new regulations.
- **Car Reliability Index**: Tracks DNF rates per driver/team, critical in the energy era where reliability can determine race outcomes.

## Chaos Modeling

Race outcomes are influenced by unpredictable factors. The system includes a **race chaos index** (0.0-1.0) computed from:

- **Safety Car Probability**: Historical track incident rates
- **Weather Variance**: Temperature and humidity changes during the race
- **Grid Spread**: Qualifying gap between P1 and P10 (tighter = more chaos potential)
- **Circuit DNF Rate**: Historical reliability issues at specific tracks

**Chaos-Aware Predictions**: When chaos index > 0.1, probabilities are smoothed to prevent overconfidence. High chaos (≥0.7) results in more uniform probability distributions, reflecting increased unpredictability.

## Running Winner Prediction Locally

### 1. Train Winner Model

```bash
.venv\Scripts\python main.py
```

This trains both models:
- Lap-time model (for lap-level predictions)
- Winner model (using aggregated race-level features)

Models are saved to `models/best_model.joblib` and `models/winner_model.joblib`.

### 2. Use Python API

```python
from winner_model import prepare_race_level_features, load_best_winner_model, predict_winner_probabilities, align_winner_features_to_model

# Prepare features for a race
X, y = prepare_race_level_features(2023, "Monaco")

# Load model
model, features = load_best_winner_model()

# Align and predict
X_aligned = align_winner_features_to_model(X, features)
probabilities = predict_winner_probabilities(model, X_aligned)

# Display results
for i, prob in enumerate(probabilities):
    driver = X.index[i] if hasattr(X, 'index') else f"Driver_{i}"
    print(f"{driver}: {prob*100:.1f}%")
```

### 3. Use REST API

Start the backend server:
```bash
.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8011
```

Query the endpoint:
```bash
curl "http://localhost:8011/predict-winner?year=2023&gp=Monaco"
```

Response:
```json
{
  "race": "Monaco Grand Prix",
  "year": 2023,
  "predictions": [
    {"driver": "VER", "win_probability": 0.34},
    {"driver": "NOR", "win_probability": 0.26},
    ...
  ]
}
```

### 4. Use Frontend

Navigate to `/winner` page in the React app. Select year and Grand Prix to view:
- Ranked table with win probabilities
- Horizontal bar chart visualization
- Chaos probability indicator
- Top 3 drivers highlighted

---
