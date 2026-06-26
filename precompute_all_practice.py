"""
precompute_all_practice.py

Batch-precompute practice telemetry for all (or selected) GPs in a season.
Saves each GP cache file to cache/YYYY_gp_name_practice.json.

Usage:
  python precompute_all_practice.py                       # 2024+2025+2026
  python precompute_all_practice.py 2026                  # single year
  python precompute_all_practice.py 2023 2026             # year range inclusive
  python precompute_all_practice.py 2026 --skip-existing  # skip cached
  python precompute_all_practice.py 2026 --gp Austrian    # single GP substring
  python precompute_all_practice.py 2026 --dry-run        # list only
  python precompute_all_practice.py 2026 --gp Austrian --force
"""

import os
import sys
import time
import traceback
import argparse

import fastf1
import pandas as pd

from data_ingestion import get_event_schedule
from practice_data_ingestion import (
    extract_practice_features,
    save_practice_features,
    load_practice_features,
    _cache_path,
)

# ---------------------------------------------------------------------------
# Hardcoded fallback calendars
# ---------------------------------------------------------------------------
KNOWN_GPS = {
    2018: [
        "Australian Grand Prix", "Bahrain Grand Prix", "Chinese Grand Prix",
        "Azerbaijan Grand Prix", "Spanish Grand Prix", "Monaco Grand Prix",
        "Canadian Grand Prix", "French Grand Prix", "Austrian Grand Prix",
        "British Grand Prix", "German Grand Prix", "Hungarian Grand Prix",
        "Belgian Grand Prix", "Italian Grand Prix", "Singapore Grand Prix",
        "Russian Grand Prix", "Japanese Grand Prix", "United States Grand Prix",
        "Mexico City Grand Prix", "São Paulo Grand Prix", "Abu Dhabi Grand Prix",
    ],
    2019: [
        "Australian Grand Prix", "Bahrain Grand Prix", "Chinese Grand Prix",
        "Azerbaijan Grand Prix", "Spanish Grand Prix", "Monaco Grand Prix",
        "Canadian Grand Prix", "French Grand Prix", "Austrian Grand Prix",
        "British Grand Prix", "German Grand Prix", "Hungarian Grand Prix",
        "Belgian Grand Prix", "Italian Grand Prix", "Singapore Grand Prix",
        "Russian Grand Prix", "Japanese Grand Prix", "Mexico City Grand Prix",
        "United States Grand Prix", "São Paulo Grand Prix", "Abu Dhabi Grand Prix",
    ],
    2020: [
        "Austrian Grand Prix", "Styrian Grand Prix", "Hungarian Grand Prix",
        "British Grand Prix", "70th Anniversary Grand Prix", "Spanish Grand Prix",
        "Belgian Grand Prix", "Italian Grand Prix", "Tuscan Grand Prix",
        "Russian Grand Prix", "Eifel Grand Prix", "Portuguese Grand Prix",
        "Emilia Romagna Grand Prix", "Turkish Grand Prix", "Bahrain Grand Prix",
        "Sakhir Grand Prix", "Abu Dhabi Grand Prix",
    ],
    2021: [
        "Bahrain Grand Prix", "Emilia Romagna Grand Prix", "Portuguese Grand Prix",
        "Spanish Grand Prix", "Monaco Grand Prix", "Azerbaijan Grand Prix",
        "French Grand Prix", "Styrian Grand Prix", "Austrian Grand Prix",
        "British Grand Prix", "Hungarian Grand Prix", "Belgian Grand Prix",
        "Dutch Grand Prix", "Italian Grand Prix", "Russian Grand Prix",
        "Turkish Grand Prix", "United States Grand Prix", "Mexico City Grand Prix",
        "São Paulo Grand Prix", "Qatar Grand Prix", "Saudi Arabian Grand Prix",
        "Abu Dhabi Grand Prix",
    ],
    2022: [
        "Bahrain Grand Prix", "Saudi Arabian Grand Prix", "Australian Grand Prix",
        "Emilia Romagna Grand Prix", "Miami Grand Prix", "Spanish Grand Prix",
        "Monaco Grand Prix", "Azerbaijan Grand Prix", "Canadian Grand Prix",
        "British Grand Prix", "Austrian Grand Prix", "French Grand Prix",
        "Hungarian Grand Prix", "Belgian Grand Prix", "Dutch Grand Prix",
        "Italian Grand Prix", "Singapore Grand Prix", "Japanese Grand Prix",
        "United States Grand Prix", "Mexico City Grand Prix", "São Paulo Grand Prix",
        "Abu Dhabi Grand Prix",
    ],
    2023: [
        "Bahrain Grand Prix", "Saudi Arabian Grand Prix", "Australian Grand Prix",
        "Azerbaijan Grand Prix", "Miami Grand Prix", "Monaco Grand Prix",
        "Spanish Grand Prix", "Canadian Grand Prix", "Austrian Grand Prix",
        "British Grand Prix", "Hungarian Grand Prix", "Belgian Grand Prix",
        "Dutch Grand Prix", "Italian Grand Prix", "Singapore Grand Prix",
        "Japanese Grand Prix", "Qatar Grand Prix", "United States Grand Prix",
        "Mexico City Grand Prix", "São Paulo Grand Prix", "Las Vegas Grand Prix",
        "Abu Dhabi Grand Prix",
    ],
    2024: [
        "Bahrain Grand Prix", "Saudi Arabian Grand Prix", "Australian Grand Prix",
        "Japanese Grand Prix", "Chinese Grand Prix", "Miami Grand Prix",
        "Emilia Romagna Grand Prix", "Monaco Grand Prix", "Canadian Grand Prix",
        "Spanish Grand Prix", "Austrian Grand Prix", "British Grand Prix",
        "Hungarian Grand Prix", "Belgian Grand Prix", "Dutch Grand Prix",
        "Italian Grand Prix", "Azerbaijan Grand Prix", "Singapore Grand Prix",
        "United States Grand Prix", "Mexico City Grand Prix", "São Paulo Grand Prix",
        "Las Vegas Grand Prix", "Qatar Grand Prix", "Abu Dhabi Grand Prix",
    ],
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

SEP = "=" * 62


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _enable_cache():
    d = os.environ.get("FASTF1_CACHE_DIR", os.path.join(os.getcwd(), "fastf1_cache"))
    os.makedirs(d, exist_ok=True)
    fastf1.Cache.enable_cache(d)
    print(f"  FastF1 cache: {d}")


def _get_schedule(year):
    try:
        s = get_event_schedule(year)
        if not s.empty and "EventName" in s.columns:
            return s
    except Exception as e:
        print(f"  [warn] schedule API failed for {year}: {e}")
    if year in KNOWN_GPS:
        print(f"  Using hardcoded {year} calendar ({len(KNOWN_GPS[year])} GPs)")
        return pd.DataFrame({"EventName": KNOWN_GPS[year]})
    return pd.DataFrame()


def _match_gp(name, query):
    return query.lower() in name.lower()


def _fmt(secs):
    if secs < 60:
        return f"{secs:.0f}s"
    m, s = divmod(int(secs), 60)
    return f"{m}m {s:02d}s"


def _bar(done, total, w=28):
    filled = int(w * done / max(total, 1))
    return "[" + "█" * filled + "░" * (w - filled) + f"] {done}/{total}"


# ---------------------------------------------------------------------------
# Per-year precompute
# ---------------------------------------------------------------------------

def precompute_year(year, skip_existing=True, gp_filter="", dry_run=False, force=False):
    print()
    print(SEP)
    print(f"  Year: {year}   filter: '{gp_filter or 'ALL'}'   skip-existing: {skip_existing}")
    print(SEP)
    _enable_cache()

    schedule = _get_schedule(year)
    if schedule.empty or "EventName" not in schedule.columns:
        print(f"  No schedule for {year}. Skipping.")
        return {}

    gps = schedule["EventName"].dropna().tolist()
    if gp_filter:
        gps = [g for g in gps if _match_gp(g, gp_filter)]
        if not gps:
            print(f"  No GPs matched '{gp_filter}' in {year}.")
            return {}

    print(f"  {len(gps)} event(s) to process\n")
    results = {}
    times = []
    total = len(gps)

    for i, gp in enumerate(gps, 1):
        cache_file = _cache_path(year, gp)
        already = os.path.exists(cache_file)
        print(f"  {_bar(i - 1, total)}  [{i}/{total}] {year} · {gp}")

        if dry_run:
            tag = "cached" if already else "would compute"
            print(f"    DRY RUN  -> {tag}")
            results[gp] = "dry_run"
            continue

        if already and skip_existing and not force:
            kb = os.path.getsize(cache_file) / 1024
            print(f"    SKIP     — cache exists ({kb:.0f} KB)")
            results[gp] = "skipped"
            continue

        t0 = time.time()
        try:
            df = extract_practice_features(year, gp)
            elapsed = time.time() - t0
            if df is None or df.empty:
                print("    NO DATA  — practice sessions not available")
                results[gp] = "no_data"
            else:
                save_practice_features(df, year, gp)
                times.append(elapsed)
                remaining = total - i
                eta_str = ""
                if remaining > 0 and times:
                    eta = (sum(times) / len(times)) * remaining
                    eta_str = f"  (ETA remaining: {_fmt(eta)})"
                print(f"    OK       — {len(df)} drivers · {len(df.columns)} features · {_fmt(elapsed)}{eta_str}")
                results[gp] = "ok"
        except Exception as e:
            elapsed = time.time() - t0
            print(f"    FAIL     — {e} ({_fmt(elapsed)})")
            if os.environ.get("PRECOMPUTE_VERBOSE"):
                traceback.print_exc()
            results[gp] = f"failed: {e}"

        if i < total:
            time.sleep(1.5)

    print()
    print(f"  {_bar(total, total)}")
    return results


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(all_results, t_start):
    elapsed = time.time() - t_start
    counts = {"ok": 0, "skipped": 0, "no_data": 0, "dry_run": 0, "failed": 0}
    failures = []

    for gp, st in all_results.items():
        if st == "ok":
            counts["ok"] += 1
        elif st == "skipped":
            counts["skipped"] += 1
        elif st == "no_data":
            counts["no_data"] += 1
        elif st == "dry_run":
            counts["dry_run"] += 1
        elif st.startswith("failed"):
            counts["failed"] += 1
            failures.append((gp, st))

    print()
    print(SEP)
    print("  SUMMARY")
    print(SEP)
    print(f"  Total GPs  : {len(all_results)}")
    print(f"  OK         : {counts['ok']}")
    if counts["skipped"]:
        print(f"  Skipped    : {counts['skipped']}  (already cached)")
    if counts["no_data"]:
        print(f"  No data    : {counts['no_data']}  (future/missing sessions)")
    if counts["dry_run"]:
        print(f"  Dry-run    : {counts['dry_run']}")
    if counts["failed"]:
        print(f"  Failed     : {counts['failed']}")
    if failures:
        print("\n  Failed GPs:")
        for gp, st in failures:
            print(f"    - {gp}: {st}")
    print(f"\n  Total time : {_fmt(elapsed)}")
    print(f"  Cache dir  : {os.path.abspath('cache')}")
    if counts["ok"]:
        print(f"\n  {counts['ok']} new cache file(s) picked up automatically by the backend.")
        print("  Restart the backend if already running.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args():
    p = argparse.ArgumentParser(
        description="Batch-precompute F1 practice features for winner prediction.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "years", nargs="*", type=int,
        help="Year(s): one value = single year, two values = inclusive range. Default: 2024 2025 2026",
    )
    p.add_argument("--skip-existing", "--skip", action="store_true",
                   help="Skip GPs whose cache file already exists.")
    p.add_argument("--force", action="store_true",
                   help="Re-compute even if cache exists (overrides --skip-existing).")
    p.add_argument("--gp", type=str, default="",
                   help="Case-insensitive substring filter. E.g. --gp Austrian")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would be computed without downloading anything.")
    p.add_argument("--verbose", action="store_true",
                   help="Print full tracebacks on failure.")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.verbose:
        os.environ["PRECOMPUTE_VERBOSE"] = "1"

    if not args.years:
        years = [2024, 2025, 2026]
    elif len(args.years) == 1:
        years = [args.years[0]]
    else:
        years = list(range(args.years[0], args.years[1] + 1))

    print(SEP)
    print("  F1 Practice Data — Bulk Precompute")
    print(f"  Years      : {years}")
    print(f"  GP filter  : '{args.gp or 'ALL'}'")
    print(f"  Skip cached: {args.skip_existing}   Force: {args.force}   Dry run: {args.dry_run}")
    print(SEP)

    t_start = time.time()
    all_results = {}

    for year in years:
        year_results = precompute_year(
            year,
            skip_existing=args.skip_existing,
            gp_filter=args.gp,
            dry_run=args.dry_run,
            force=args.force,
        )
        for gp, st in year_results.items():
            all_results[f"{year} · {gp}"] = st

    print_summary(all_results, t_start)
