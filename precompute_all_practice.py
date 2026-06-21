"""
precompute_all_practice.py

Batch job: precompute practice telemetry for ALL GPs in a given year range.
Saves each GP's features to cache/YYYY_gp_name_practice.json.

Usage:
  python precompute_all_practice.py              # defaults: 2024 + 2025 + 2026
  python precompute_all_practice.py 2026         # single year
  python precompute_all_practice.py 2023 2026    # year range (inclusive)
  python precompute_all_practice.py 2026 --skip-existing   # skip already cached

Takes ~3-8 min per GP, so expect 1-2 hrs for a full season.
"""

import os
import sys
import time
import traceback

import fastf1
import pandas as pd

from data_ingestion import get_event_schedule
from practice_data_ingestion import (
    extract_practice_features,
    save_practice_features,
    load_practice_features,
    _cache_path,
)


def _enable_cache() -> None:
    cache_dir = os.path.join(os.getcwd(), "fastf1_cache")
    os.makedirs(cache_dir, exist_ok=True)
    fastf1.Cache.enable_cache(cache_dir)


def _get_schedule_with_fallback(year: int) -> pd.DataFrame:
    """Try FastF1 schedule; if it fails, fall back to known GP names."""
    schedule = get_event_schedule(year)
    if not schedule.empty and "EventName" in schedule.columns:
        return schedule

    # Fallback: hardcoded 2025/2026 calendars
    KNOWN_GPS = {
        2025: [
            "Australian Grand Prix", "Chinese Grand Prix", "Japanese Grand Prix",
            "Bahrain Grand Prix", "Saudi Arabian Grand Prix", "Miami Grand Prix",
            "Emilia Romagna Grand Prix", "Monaco Grand Prix", "Spanish Grand Prix",
            "Canadian Grand Prix", "Austrian Grand Prix", "British Grand Prix",
            "Belgian Grand Prix", "Hungarian Grand Prix", "Dutch Grand Prix",
            "Italian Grand Prix", "Azerbaijan Grand Prix", "Singapore Grand Prix",
            "United States Grand Prix", "Mexico City Grand Prix", "São Paulo Grand Prix",
            "Las Vegas Grand Prix", "Qatar Grand Prix", "Abu Dhabi Grand Prix",
        ],
        2026: [
            "Australian Grand Prix", "Chinese Grand Prix", "Japanese Grand Prix",
            "Bahrain Grand Prix", "Saudi Arabian Grand Prix", "Miami Grand Prix",
            "Emilia Romagna Grand Prix", "Monaco Grand Prix", "Spanish Grand Prix",
            "Canadian Grand Prix", "Austrian Grand Prix", "British Grand Prix",
            "Belgian Grand Prix", "Hungarian Grand Prix", "Dutch Grand Prix",
            "Italian Grand Prix", "Azerbaijan Grand Prix", "Singapore Grand Prix",
            "United States Grand Prix", "Mexico City Grand Prix", "São Paulo Grand Prix",
            "Las Vegas Grand Prix", "Qatar Grand Prix", "Abu Dhabi Grand Prix",
        ],
    }
    if year in KNOWN_GPS:
        print(f"  FastF1 schedule API failed — using hardcoded {year} calendar ({len(KNOWN_GPS[year])} GPs)")
        return pd.DataFrame({"EventName": KNOWN_GPS[year]})

    return pd.DataFrame()


def precompute_year(year: int, skip_existing: bool = True) -> dict:
    """
    Precompute practice features for every GP in a given year.
    Returns a summary dict: {gp_name: "ok" | "skipped" | "failed" | "no_data"}.
    """
    print(f"\n{'='*60}")
    print(f"  Year: {year}")
    print(f"{'='*60}")

    _enable_cache()
    schedule = _get_schedule_with_fallback(year)
    if schedule.empty or "EventName" not in schedule.columns:
        print(f"  Could not load schedule for {year}. Skipping year.")
        return {}

    gps = schedule["EventName"].dropna().tolist()
    print(f"  {len(gps)} events found")

    results = {}

    for i, gp in enumerate(gps, 1):
        print(f"\n[{i}/{len(gps)}] {year} {gp}")

        # Check if already cached
        cache_file = _cache_path(year, gp)
        if skip_existing and os.path.exists(cache_file):
            print(f"  SKIP — cache already exists: {cache_file}")
            results[gp] = "skipped"
            continue

        t0 = time.time()
        try:
            df = extract_practice_features(year, gp)
            if df.empty:
                print(f"  NO DATA — practice sessions not available (future race or missing)")
                results[gp] = "no_data"
            else:
                save_practice_features(df, year, gp)
                elapsed = time.time() - t0
                print(f"  OK — {len(df)} drivers, {len(df.columns)} features ({elapsed:.0f}s)")
                results[gp] = "ok"
        except Exception as e:
            print(f"  FAILED — {e}")
            traceback.print_exc()
            results[gp] = f"failed: {e}"

        # Brief pause between GPs to be kind to FastF1 cache/API
        time.sleep(2)

    return results


def print_summary(all_results: dict) -> None:
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")

    ok = sum(1 for v in all_results.values() if v == "ok")
    skipped = sum(1 for v in all_results.values() if v == "skipped")
    no_data = sum(1 for v in all_results.values() if v == "no_data")
    failed = sum(1 for v in all_results.values() if str(v).startswith("failed"))

    total = len(all_results)
    print(f"  Total GPs  : {total}")
    print(f"  OK         : {ok}")
    print(f"  Skipped    : {skipped}  (already cached)")
    print(f"  No data    : {no_data}  (future race or FP sessions missing)")
    print(f"  Failed     : {failed}")

    if failed > 0:
        print("\n  Failed GPs:")
        for gp, status in all_results.items():
            if str(status).startswith("failed"):
                print(f"    - {gp}: {status}")

    print(f"\n  Cache directory: {os.path.abspath('cache')}")
    print(f"  These caches are used automatically when you query predictions.")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]

    skip_existing = "--skip-existing" in flags or "--skip" in flags

    # Parse year range
    if len(args) == 0:
        years = [2024, 2025, 2026]
    elif len(args) == 1:
        years = [int(args[0])]
    else:
        start, end = int(args[0]), int(args[1])
        years = list(range(start, end + 1))

    print("=" * 60)
    print("  F1 Practice Data — Bulk Precompute")
    print(f"  Years: {years}")
    print(f"  Skip existing: {skip_existing}")
    print("=" * 60)

    t_start = time.time()
    all_results = {}

    for year in years:
        year_results = precompute_year(year, skip_existing=skip_existing)
        for gp, status in year_results.items():
            all_results[f"{year} {gp}"] = status

    print_summary(all_results)
    elapsed_total = time.time() - t_start
    print(f"\n  Total time: {elapsed_total/60:.1f} min")
