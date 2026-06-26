"""
build_corner_features_2026.py  (v3 — uses FastF1 sector times, no raw telemetry)
─────────────────────────────────────────────────────────────────────────────────
Extracts per-driver corner performance from sector time analysis.
FastF1 loads sector times fine for 2026; no car_data/OpenF1 needed.

Sector proxy mapping (most circuits):
  S1 = high-speed cornering ability (fast sweepers)
  S2 = mixed: medium + slow corners, braking zones
  S3 = traction + slow corner exit + final chicanes

Run locally:  python build_corner_features_2026.py
"""

import sys, json, warnings, argparse
from pathlib import Path
from datetime import datetime

warnings.filterwarnings("ignore")

ROOT       = Path(__file__).parent
MODELS_DIR = ROOT / "models"
CACHE_FILE = MODELS_DIR / "corner_features_2026.json"

FEATURE_NAMES = [
    "sector1_pace",   # high-speed corners
    "sector2_pace",   # mixed corners + braking
    "sector3_pace",   # slow corner traction
    "consistency",    # lap time std dev (lower = more consistent)
    "race_pace",      # overall normalised lap time
]


def extract_race_features(year: int, gp_name: str) -> dict | None:
    import fastf1, numpy as np, pandas as pd
    fastf1.Cache.enable_cache(str(MODELS_DIR))

    print(f"\n  Loading {year} {gp_name}…", end="", flush=True)
    try:
        session = fastf1.get_session(year, gp_name, "R")
        session.load(laps=True, telemetry=False, weather=False, messages=False)
        print(f" ✓ ({len(session.drivers)} drivers)")
    except Exception as e:
        print(f" ✗ {e}")
        return None

    results = {}

    # Get all clean laps (accurate, not pit laps, lap > 2)
    laps = session.laps
    # Column names vary by FastF1 version — use .get() style via .get accessor
    pit_in  = laps["PitInTime"].notna()  if "PitInTime"  in laps.columns else False
    pit_out = laps["PitOutTime"].notna() if "PitOutTime" in laps.columns else False
    accurate = laps["IsAccurate"] if "IsAccurate" in laps.columns else True

    clean = laps[
        accurate &
        (~pit_in) &
        (~pit_out) &
        (laps["LapNumber"] > 2)
    ].copy()

    if clean.empty:
        print("  No clean laps found")
        return None

    # Convert sector times to seconds
    for col in ["Sector1Time","Sector2Time","Sector3Time","LapTime"]:
        clean[f"{col}_s"] = clean[col].dt.total_seconds()

    # Session medians (exclude top/bottom 10% to remove outliers)
    def trimmed_median(series):
        s = series.dropna()
        if len(s) < 4:
            return s.median()
        lo, hi = s.quantile(0.10), s.quantile(0.90)
        return s[(s >= lo) & (s <= hi)].median()

    s1_med  = trimmed_median(clean["Sector1Time_s"])
    s2_med  = trimmed_median(clean["Sector2Time_s"])
    s3_med  = trimmed_median(clean["Sector3Time_s"])
    lap_med = trimmed_median(clean["LapTime_s"])

    print(f"  Medians — S1:{s1_med:.3f}  S2:{s2_med:.3f}  S3:{s3_med:.3f}  lap:{lap_med:.3f}")

    for drv in session.drivers:
        try:
            drv_info  = session.get_driver(drv)
            drv_code  = drv_info.get("Abbreviation", drv)
            drv_laps  = clean[clean["DriverNumber"] == drv]

            if len(drv_laps) < 3:
                continue

            # Median sector times for this driver
            d_s1  = trimmed_median(drv_laps["Sector1Time_s"])
            d_s2  = trimmed_median(drv_laps["Sector2Time_s"])
            d_s3  = trimmed_median(drv_laps["Sector3Time_s"])
            d_lap = trimmed_median(drv_laps["LapTime_s"])
            d_std = drv_laps["LapTime_s"].std()

            if any(v is None or (hasattr(v,'__class__') and str(v) == 'nan')
                   for v in [d_s1, d_s2, d_s3, d_lap]):
                continue

            import math
            if any(math.isnan(v) for v in [d_s1, d_s2, d_s3, d_lap]):
                continue

            results[drv_code] = {
                # Normalised: lower ratio = faster = better pace
                # We invert so >1.0 means BETTER than median
                "sector1_pace": round(s1_med  / d_s1,  4) if d_s1  else 1.0,
                "sector2_pace": round(s2_med  / d_s2,  4) if d_s2  else 1.0,
                "sector3_pace": round(s3_med  / d_s3,  4) if d_s3  else 1.0,
                "race_pace":    round(lap_med / d_lap, 4) if d_lap else 1.0,
                "consistency":  round(1.0 / (1.0 + float(d_std or 1.0)), 4),
                "laps":         len(drv_laps),
            }
        except Exception as e:
            pass

    # Print per-driver
    print(f"  {'DRV':4} {'S1':6} {'S2':6} {'S3':6} {'PACE':6} {'CONSIST':8} {'LAPS':4}")
    for drv, v in sorted(results.items(), key=lambda x: -x[1]["race_pace"]):
        print(f"  {drv:4} {v['sector1_pace']:6.3f} {v['sector2_pace']:6.3f} "
              f"{v['sector3_pace']:6.3f} {v['race_pace']:6.3f} "
              f"{v['consistency']:8.4f} {v['laps']:4}")

    print(f"  ✓ {len(results)} drivers")
    return results


def run_extraction():
    import fastf1, numpy as np, pandas as pd
    fastf1.Cache.enable_cache(str(MODELS_DIR))

    print("Loading 2026 schedule…")
    sched = fastf1.get_event_schedule(2026, include_testing=False)

    now = datetime.now()
    completed = sched[pd.to_datetime(sched["EventDate"]).dt.tz_localize(None) < now]
    print(f"Found {len(completed)} completed events\n")

    all_features = {}
    driver_agg   = {}

    for _, row in completed.iterrows():
        gp = row["EventName"]
        print(f"══ {gp} ══")
        feats = extract_race_features(2026, gp)
        if feats:
            all_features[gp] = feats
            for drv, vals in feats.items():
                driver_agg.setdefault(drv, []).append(vals)

    if not driver_agg:
        print("\nNo data extracted.")
        return {}

    # Aggregate per driver across all races
    driver_profile = {}
    for drv, race_list in driver_agg.items():
        profile = {"races": len(race_list), "driver": drv}
        for feat in FEATURE_NAMES:
            vals = [r[feat] for r in race_list if r.get(feat) is not None]
            profile[feat] = round(float(np.mean(vals)), 4) if vals else 1.0
        driver_profile[drv] = profile

    # Summary table
    print("\n\n── 2026 DRIVER CORNER PROFILES (season average) ──")
    print(f"{'DRV':5} {'RACES':6} {'S1(HS)':8} {'S2(MIX)':9} {'S3(TRACT)':10} {'PACE':6} {'CONSISTENCY':12}")
    print("─" * 60)
    for drv, p in sorted(driver_profile.items(), key=lambda x: -x[1].get("race_pace", 1)):
        print(f"{drv:5} {p['races']:6} "
              f"{p['sector1_pace']:8.4f} "
              f"{p['sector2_pace']:9.4f} "
              f"{p['sector3_pace']:10.4f} "
              f"{p['race_pace']:6.4f} "
              f"{p['consistency']:12.4f}")

    CACHE_FILE.parent.mkdir(exist_ok=True)
    cache = {
        "year": 2026,
        "extracted_at": datetime.now().isoformat(),
        "source": "fastf1_sectors",
        "note": "sector1=high-speed, sector2=mixed, sector3=traction/slow",
        "races": list(all_features.keys()),
        "driver_profiles": driver_profile,
        "per_race": all_features,
    }
    CACHE_FILE.write_text(json.dumps(cache, indent=2))
    print(f"\n✓ Saved to {CACHE_FILE}")
    print("\nNext: commit and push to deploy the corner adjustment:")
    print("  git add models/corner_features_2026.json backend/main.py build_corner_features_2026.py")
    print('  git commit -m "feat: 2026 corner performance profiles from sector analysis"')
    print("  git push")
    return driver_profile


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gp", type=str, help="Test single GP name e.g. 'Australian Grand Prix'")
    args = parser.parse_args()

    if args.gp:
        import fastf1
        fastf1.Cache.enable_cache(str(MODELS_DIR))
        extract_race_features(2026, args.gp)
    else:
        run_extraction()
