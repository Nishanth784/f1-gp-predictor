from typing import Tuple, List

import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder


def timedelta_to_seconds(series: pd.Series) -> pd.Series:
	try:
		return series.dt.total_seconds()
	except Exception:
		return pd.to_timedelta(series, errors="coerce").dt.total_seconds()


def add_driver_team_key(df: pd.DataFrame) -> pd.DataFrame:
	work = df.copy()
	if set(["Driver", "Team"]).issubset(work.columns):
		work["DriverTeam"] = work["Driver"].astype(str) + "_" + work["Team"].astype(str)
	return work


def engineer_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
	if df is None or df.empty:
		return pd.DataFrame(), pd.Series(dtype=float)

	work = add_driver_team_key(df)

	# Ensure base seconds
	if "LapTimeSeconds" not in work.columns and "LapTime" in work.columns:
		work["LapTimeSeconds"] = timedelta_to_seconds(work["LapTime"])  # type: ignore[index]
	for src, dst in [("Sector1Time", "Sector1Seconds"), ("Sector2Time", "Sector2Seconds"), ("Sector3Time", "Sector3Seconds")]:
		if dst not in work.columns and src in work.columns:
			work[dst] = timedelta_to_seconds(work[src])

	# Drop rows with missing target
	work = work.dropna(subset=["LapTimeSeconds"]).reset_index(drop=True)

	# Normalize sectors (z-score within dataset)
	for col in ["Sector1Seconds", "Sector2Seconds", "Sector3Seconds"]:
		if col in work.columns:
			mean_val = work[col].mean()
			std_val = work[col].std(ddof=0) or 1.0
			work[f"{col}_z"] = (work[col] - mean_val) / std_val

	# Derived features
	if set(["Sector1Seconds", "Sector2Seconds", "Sector3Seconds"]).issubset(work.columns):
		work["AvgSectorSeconds"] = work[["Sector1Seconds", "Sector2Seconds", "Sector3Seconds"]].mean(axis=1)
	# Tyre age proxy
	if "TyreLife" in work.columns:
		work["TyreLife"] = work["TyreLife"].fillna(work["TyreLife"].median())
	else:
		work["TyreLife"] = 0.0

	# Track evolution: include normalized lap within session and per-phase if available
	if "LapNumber" in work.columns and len(work) > 0:
		max_lap = max(work["LapNumber"].max(), 1)
		work["TrackEvolution"] = work["LapNumber"].astype(float) / float(max_lap)
	else:
		work["TrackEvolution"] = 0.0
	if "SessionPhase" in work.columns:
		# Relative lap progress per phase (e.g., sprint vs quali)
		work["PhaseProgress"] = work.groupby("SessionPhase")["LapNumber"].transform(lambda s: s.astype(float) / max(s.max(), 1))
	else:
		work["PhaseProgress"] = work["TrackEvolution"]

	# Categorical one-hot encoding including DriverTeam
	categorical_cols: List[str] = [c for c in ["Driver", "Team", "Compound", "DriverTeam", "SessionPhase"] if c in work.columns]
	if categorical_cols:
		enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
		encoded = enc.fit_transform(work[categorical_cols])
		encoded_cols = enc.get_feature_names_out(categorical_cols)
		encoded_df = pd.DataFrame(encoded, columns=encoded_cols, index=work.index)
		work = pd.concat([work.drop(columns=categorical_cols, errors="ignore"), encoded_df], axis=1)

	feature_cols = [
		c for c in work.columns
		if c not in ["LapTimeSeconds", "LapTime", "Sector1Time", "Sector2Time", "Sector3Time", "LapStartTime"]
	]
	X = work[feature_cols].select_dtypes(include=[np.number]).fillna(0.0)
	y = work["LapTimeSeconds"].astype(float)
	return X, y
