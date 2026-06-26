# F1 Grand Prix Winner Prediction - Complete Project Summary

## 📋 Project Overview

A full-stack machine learning application for predicting F1 Grand Prix lap times using historical race data from FastF1, featuring:
- **Backend**: Python FastAPI REST API
- **Frontend**: React + TailwindCSS web application
- **ML Pipeline**: Feature engineering, model training, and prediction
- **Dashboards**: Streamlit interactive dashboard
- **Real-time**: Optional live weather integration

---

## 📁 Project Structure

```
prediction system/
├── main.py                    # Main training script
├── data_ingestion.py          # FastF1 data loading & caching
├── feature_engineering.py     # Feature transformation pipeline
├── model.py                   # ML model training & evaluation
├── realtime.py                # Live weather & real-time predictions
├── dashboard.py               # Streamlit dashboard (refactored)
├── streamlit_app.py           # Original Streamlit app
├── requirements.txt           # Python dependencies (root)
├── README.md                  # Setup & usage instructions
├── render.yaml                # Backend deployment config (Render)
├── netlify.toml               # Frontend deployment config (Netlify)
│
├── backend/
│   ├── main.py                # FastAPI application & endpoints
│   └── requirements.txt       # Backend-specific dependencies
│
├── frontend/
│   ├── package.json           # Node.js dependencies
│   ├── vite.config.js         # Vite build configuration
│   ├── tailwind.config.js     # TailwindCSS theme config
│   ├── postcss.config.js      # PostCSS config
│   ├── index.html             # HTML entry point
│   └── src/
│       ├── main.jsx           # React router setup
│       ├── styles.css         # Global F1-themed styles
│       ├── components/
│       │   └── Navbar.jsx     # Navigation component
│       └── pages/
│           ├── Home.jsx       # Landing page
│           ├── Predict.jsx    # Prediction form page
│           └── Compare.jsx    # Comparison dashboard page
│
├── tests/
│   ├── test_feature_engineering.py  # Feature engineering tests
│   └── test_model.py                # Model tests
│
├── models/
│   └── best_model.joblib      # Saved trained model
│
└── fastf1_cache/              # FastF1 cached session data
```

---

## 🔧 Core Python Modules

### 1. **`main.py`** - Entry Point for Training
**Purpose**: Orchestrates the ML pipeline: data loading → feature engineering → model training → saving.

**Key Functions**:
- Loads F1 session data (Monaco 2023 Qualifying by default)
- Engineers features from raw lap data
- Trains and evaluates multiple models (Linear Regression, Random Forest, Gradient Boosting)
- Saves the best model to `models/best_model.joblib`
- Optional: Runs live prediction demo if `RUN_LIVE_DEMO=1`

**Usage**:
```bash
.venv\Scripts\python main.py
```

---

### 2. **`data_ingestion.py`** - Data Loading & Caching
**Purpose**: Handles FastF1 API interactions, session data loading, weather merging, and sprint weekend support.

**Key Functions**:
- `get_event_schedule(year)` - Fetches F1 calendar for a year
- `load_session_with_weather(year, gp_name, session_code)` - Loads lap data and merges weather snapshots
- `get_session_data(year, gp_name, session_type, include_sprint=False)` - Main entry point; supports sprint sessions (SQ, SS, SR)

**Features**:
- Automatic caching via FastF1 (saves to `fastf1_cache/`)
- Weather data merged using `pd.merge_asof` (nearest match per lap)
- Handles missing columns gracefully
- Returns cleaned DataFrame with: Driver, Team, LapNumber, LapTime, Sector1-3Times, Compound, TyreLife, TrackTemp, AirTemp, Humidity

---

### 3. **`feature_engineering.py`** - Feature Transformation
**Purpose**: Converts raw F1 lap data into ML-ready features.

**Key Functions**:
- `timedelta_to_seconds(series)` - Converts lap/sector times to float seconds
- `add_driver_team_key(df)` - Creates `DriverTeam` composite key (e.g., "HAM_Mercedes")
- `engineer_features(df)` - Main transformation pipeline

**Feature Engineering Steps**:
1. **Time Conversion**: LapTime, Sector1-3Times → seconds (float)
2. **Sector Normalization**: Z-score normalization per sector (`Sector1Seconds_z`, etc.)
3. **Derived Features**:
   - `AvgSectorSeconds` - Average of all three sectors
   - `TyreLife` - Proxy for tyre degradation (filled with median if missing)
   - `TrackEvolution` - Normalized lap number (0-1) for track rubbering
   - `PhaseProgress` - Per-session-phase progress (for sprint weekends)
4. **Categorical Encoding**: One-hot encoding for Driver, Team, Compound, DriverTeam, SessionPhase
5. **Output**: Returns `(X: DataFrame, y: Series)` where `y = LapTimeSeconds`

---

### 4. **`model.py`** - Model Training & Evaluation
**Purpose**: Trains multiple regression models, evaluates performance, saves the best model.

**Key Functions**:
- `train_and_evaluate(X, y, random_state=42)` - Trains Linear Regression, Random Forest (300 trees), Gradient Boosting; returns metrics dict
- `align_features_to_model(X, expected_features)` - Aligns feature columns to match saved model (adds missing columns with 0.0)
- `load_best_model(path)` - Loads saved model and feature names from joblib

**Models Tested**:
- **LinearRegression**: Baseline linear model
- **RandomForestRegressor**: 300 estimators, parallel (`n_jobs=-1`)
- **GradientBoostingRegressor**: Ensemble boosting model

**Evaluation Metrics**:
- **MAE** (Mean Absolute Error) - Average prediction error in seconds
- **RMSE** (Root Mean Squared Error) - Penalizes larger errors more

**Model Persistence**:
- Saved to `models/best_model.joblib` as `{"model": <sklearn_model>, "features": [list_of_feature_names]}`

---

### 5. **`realtime.py`** - Live Weather & Real-Time Predictions
**Purpose**: Integrates OpenWeatherMap API for live weather data and performs near-real-time predictions during live sessions.

**Key Functions**:
- `get_live_weather(location, api_key)` - Fetches current weather from OpenWeatherMap API
- `live_predict_latest_laps(year, gp_name, session_code, location, iterations=3, sleep_seconds=5)` - Polls FastF1 for new laps, merges live weather, runs predictions

**Usage**:
```bash
$env:OPENWEATHER_API_KEY = "<your_key>"
$env:RUN_LIVE_DEMO = "1"
.venv\Scripts\python main.py
```

---

### 6. **`dashboard.py`** - Streamlit Dashboard (Refactored)
**Purpose**: Interactive web dashboard for exploring predictions and comparing actual vs predicted lap times.

**Features**:
- Sidebar controls: Year, Grand Prix, Session (Q/R), Include Sprint toggle
- Prediction table: Driver, Team, LapNumber, ActualLapTime, PredictedLapTime, AbsoluteError
- Line chart: Mean predicted vs actual lap times per lap number
- Filters: Multi-select by Driver and Team
- Metrics: MAE and RMSE displayed for filtered data

**Usage**:
```bash
.venv\Scripts\python -m streamlit run dashboard.py
```

---

### 7. **`streamlit_app.py`** - Original Streamlit App
**Purpose**: Earlier version of the Streamlit dashboard (kept for reference).

**Note**: Functionally similar to `dashboard.py` but with slightly different implementation details.

---

## 🌐 Backend (FastAPI)

### **`backend/main.py`** - REST API Server
**Purpose**: FastAPI application exposing prediction endpoints and metadata for frontend consumption.

**Endpoints**:

1. **`GET /health`**
   - Health check endpoint
   - Returns `{"status": "ok"}`

2. **`GET /years`**
   - Returns available years (2018-2025)
   - Response: `{"years": [2018, 2019, ...]}`

3. **`GET /events?year=2023`**
   - Returns list of Grand Prix names for a given year
   - Response: `{"events": ["Bahrain Grand Prix", "Monaco Grand Prix", ...]}`

4. **`GET /metadata?year=2023&gp=Monaco`**
   - Returns metadata for frontend dropdowns
   - Response: `{"gps": [...], "sessions": ["Q", "R"], "drivers": [...], "teams": [...], "tyres": ["SOFT", "MEDIUM", "HARD"]}`
   - If `gp` provided, fetches drivers/teams from that session

5. **`POST /predict`**
   - Predicts lap time for given inputs
   - Request body:
     ```json
     {
       "year": 2023,
       "gp": "Monaco",
       "session_type": "Q",
       "driver": "VER",
       "team": "Red Bull",
       "tyre": "SOFT",
       "weather": {"AirTemp": 25.0, "Humidity": 60.0}
     }
     ```
   - Response: `{"predicted_lap_time": 89.234, "features_used": [...]}`

6. **`GET /compare?year=2023&gp=Monaco&session_type=Q`**
   - Returns predicted vs actual lap times for all laps in a session
   - Response: `{"rows": [{"Driver": "...", "Team": "...", "LapNumber": 1, "ActualLapTime": 89.5, "PredictedLapTime": 89.2}, ...]}`

**Key Features**:
- **Case-insensitive GP matching**: `_resolve_gp_name()` handles partial matches (e.g., "monaco" → "Monaco Grand Prix")
- **CORS enabled**: Allows frontend to call API from any origin
- **Error handling**: Graceful HTTP exceptions with descriptive messages
- **Model loading**: Automatically loads `models/best_model.joblib` on startup

**Usage**:
```bash
.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8011
```

---

## 🎨 Frontend (React + TailwindCSS)

### **`frontend/src/main.jsx`** - React Router Setup
**Purpose**: Configures React Router and renders the app shell with Navbar.

**Routes**:
- `/` - Home page
- `/predict` - Prediction form
- `/compare` - Comparison dashboard

---

### **`frontend/src/pages/Home.jsx`** - Landing Page
**Purpose**: Hero section with project description and call-to-action buttons.

**Features**:
- F1-themed gradient background
- Three feature cards: FastF1 Integration, Feature Engineering, Modeling
- Links to Predict and Compare pages

---

### **`frontend/src/pages/Predict.jsx`** - Prediction Form
**Purpose**: Form for submitting lap time prediction requests.

**Features**:
- **Dropdowns** (populated from backend `/metadata`):
  - Year (from `/years`)
  - Grand Prix (from `/metadata?year=...`)
  - Session (Q/R)
  - Driver (from `/metadata?year=...&gp=...`)
  - Team (from `/metadata?year=...&gp=...`)
  - Tyre compound (SOFT/MEDIUM/HARD)
- **Optional inputs**: Air Temperature, Humidity
- **Submit**: Calls `/predict` endpoint, displays predicted lap time
- **Auto-population**: Automatically selects first available option when data loads

---

### **`frontend/src/pages/Compare.jsx`** - Comparison Dashboard
**Purpose**: Visualizes predicted vs actual lap times for a session.

**Features**:
- **Dropdowns**: Year, Grand Prix, Session
- **Table**: Driver, Team, Lap, Actual, Predicted, |Error|
- **Line Chart** (Recharts): Predicted vs Actual lap times across laps
- **Refresh button**: Reloads data from `/compare` endpoint

---

### **`frontend/src/components/Navbar.jsx`** - Navigation Bar
**Purpose**: Responsive navigation with F1-themed styling.

**Links**: Home, Predict, Compare (highlighted based on current route)

---

### **`frontend/src/styles.css`** - Global Styles
**Purpose**: F1-themed CSS with TailwindCSS utilities.

**Theme Colors**:
- Primary: `#e10600` (F1 red)
- Background: Black (`#000000`)
- Text: White/neutral grays
- Glass effects: `backdrop-blur` for panels

**Custom Classes**:
- `.title` - Bold, gradient text
- `.btn` - Primary button (red gradient)
- `.btn-outline` - Outlined button
- `.card` - Glass panel with border
- `.panel-glass` - Glassmorphism effect

---

### **`frontend/tailwind.config.js`** - TailwindCSS Configuration
**Purpose**: Extends Tailwind theme with F1 colors and gradients.

**Custom Colors**:
- `primary`: F1 red (`#e10600`)
- `neutral`: Gray scale

---

### **`frontend/vite.config.js`** - Vite Configuration
**Purpose**: Configures Vite build tool for React.

**Plugins**: `@vitejs/plugin-react`

---

## 🧪 Tests

### **`tests/test_feature_engineering.py`**
**Purpose**: Unit tests for feature engineering pipeline.

**Tests**:
- `test_engineer_features_basic()` - Verifies feature engineering produces expected columns (AvgSectorSeconds, TrackEvolution, one-hot encoded categories)

---

### **`tests/test_model.py`**
**Purpose**: Unit tests for model functions.

**Tests**:
- `test_align_features_to_model_adds_missing_cols()` - Verifies feature alignment adds missing columns with 0.0
- `test_train_and_evaluate_runs()` - Verifies model training completes successfully

**Usage**:
```bash
.venv\Scripts\python -m pytest tests/
```

---

## 📦 Dependencies

### **`requirements.txt`** (Root)
Python dependencies for core ML pipeline:
- `numpy==2.3.2`
- `pandas==2.3.2`
- `scikit-learn==1.7.1`
- `matplotlib==3.10.6`
- `seaborn==0.13.2`
- `streamlit==1.49.1`
- `fastf1==3.6.1`
- `requests==2.32.5`
- `joblib==1.5.2`
- Plus supporting libraries (scipy, pyarrow, watchdog, protobuf, altair)

### **`backend/requirements.txt`**
Backend-specific dependencies:
- `fastapi==0.115.6`
- `uvicorn==0.34.0`
- `pydantic==2.9.2`
- Plus shared ML/data libraries (numpy, pandas, scikit-learn, fastf1, requests, joblib)

### **`frontend/package.json`**
Node.js dependencies:
- **Runtime**: `react`, `react-dom`, `react-router-dom`, `recharts`
- **Dev**: `@vitejs/plugin-react`, `vite`, `tailwindcss`, `autoprefixer`, `postcss`

---

## 🚀 Deployment Configuration

### **`render.yaml`** - Backend Deployment (Render)
**Purpose**: Configures Render.com deployment for FastAPI backend.

**Settings**:
- Service type: Web
- Build command: `pip install -r backend/requirements.txt`
- Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- Plan: Free tier

---

### **`netlify.toml`** - Frontend Deployment (Netlify)
**Purpose**: Configures Netlify deployment for React frontend.

**Settings**:
- Build base: `frontend`
- Build command: `npm run build`
- Publish directory: `frontend/dist`
- Environment variable: `VITE_API_BASE` (set to Render backend URL)

---

## 📝 Configuration Files

### **`.gitignore`**
Excludes from Git:
- `.venv/` - Python virtual environment
- `node_modules/` - Node.js dependencies
- `dist/` - Frontend build output
- `.env`, `.env.production` - Environment variables
- `__pycache__/` - Python bytecode
- `models/` - Saved ML models (large files)
- `fastf1_cache/` - FastF1 cached data

---

## 🔄 Data Flow

### **Training Pipeline**:
```
main.py
  → data_ingestion.get_session_data()
    → FastF1 API → DataFrame (laps + weather)
  → feature_engineering.engineer_features()
    → DataFrame → (X, y) features + target
  → model.train_and_evaluate()
    → Train 3 models → Evaluate → Save best → models/best_model.joblib
```

### **Prediction Pipeline (Backend)**:
```
Frontend Request
  → backend/main.py /predict endpoint
    → data_ingestion.get_session_data() → Get representative row
    → Override with user inputs (driver, team, tyre, weather)
    → feature_engineering.engineer_features() → (X, y)
    → model.align_features_to_model() → Match saved model features
    → model.predict() → Predicted lap time
  → JSON response to frontend
```

### **Comparison Pipeline (Backend)**:
```
Frontend Request
  → backend/main.py /compare endpoint
    → data_ingestion.get_session_data() → All laps
    → feature_engineering.engineer_features() → (X, y)
    → model.predict() → Predictions for all laps
    → Combine with actual lap times
  → JSON response (rows array) → Frontend renders table + chart
```

---

## 🎯 Key Features

1. **Sprint Weekend Support**: Handles sprint qualifying (SQ) and sprint race (SS/SR) sessions
2. **Driver-Team Encoding**: `DriverTeam` composite key handles mid-season driver switches
3. **Track Evolution**: Normalized lap number and phase progress for track rubbering
4. **Weather Integration**: Merges weather snapshots (TrackTemp, AirTemp, Humidity) per lap
5. **Case-Insensitive GP Matching**: Backend resolves "monaco" → "Monaco Grand Prix"
6. **Feature Alignment**: Automatically aligns new data features to saved model features
7. **Real-Time Weather**: Optional OpenWeatherMap integration for live predictions
8. **Responsive UI**: Mobile-friendly React frontend with F1-themed design

---

## 📊 Model Performance

**Typical Performance** (on Monaco 2023 Qualifying):
- **Linear Regression**: MAE ~0.5-1.0s, RMSE ~0.7-1.5s
- **Random Forest**: MAE ~0.3-0.6s, RMSE ~0.4-0.9s (usually best)
- **Gradient Boosting**: MAE ~0.3-0.7s, RMSE ~0.4-1.0s

**Best Model**: Usually RandomForestRegressor (saved to `models/best_model.joblib`)

---

## 🔐 Environment Variables

- **`OPENWEATHER_API_KEY`**: OpenWeatherMap API key for live weather (optional)
- **`RUN_LIVE_DEMO`**: Set to `"1"` to enable live prediction demo in `main.py`
- **`VITE_API_BASE`**: Frontend environment variable for backend URL (default: `http://localhost:8000`)
- **`PORT`**: Backend port (default: 8000, Render sets automatically)

---

## 📚 Usage Examples

### **Train Model**:
```bash
.venv\Scripts\python main.py
```

### **Run Streamlit Dashboard**:
```bash
.venv\Scripts\python -m streamlit run dashboard.py
```

### **Start Backend API**:
```bash
.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8011
```

### **Start Frontend**:
```bash
cd frontend
npm install
npm run dev
```

### **Run Tests**:
```bash
.venv\Scripts\python -m pytest tests/
```

---

## 🌍 Deployment URLs

- **Backend**: `https://YOUR-RENDER-API.onrender.com` (configured in `render.yaml`)
- **Frontend**: `https://YOUR-NETLIFY-SITE.netlify.app` (configured in `netlify.toml`)

**Note**: Update `netlify.toml` `VITE_API_BASE` to point to your Render backend URL before deploying frontend.

---

## 🐛 Known Issues & Solutions

1. **"Failed to fetch" in frontend**: Ensure backend is running and `VITE_API_BASE` is set correctly in `frontend/.env`
2. **Port already in use**: Use a different port (e.g., 8011 instead of 8000)
3. **ModuleNotFoundError**: Ensure virtual environment is activated and dependencies are installed
4. **FastF1 cache**: First run downloads data (slow), subsequent runs use cache (fast)

---

## 📈 Future Enhancements

Potential improvements:
- Add more features (DRS usage, pit stops, safety car periods)
- Implement time-series models (LSTM, GRU) for sequential lap predictions
- Add driver/team performance history features
- Real-time WebSocket updates for live sessions
- Model versioning and A/B testing
- Export predictions to CSV/PDF
- Multi-session comparison (compare across multiple GPs)

---

## 📄 License

This project is provided as-is for educational and demonstration purposes.

---

**Last Updated**: Based on current project state as of latest Git commit.

