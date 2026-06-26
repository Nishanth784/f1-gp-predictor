"""
retrain_model.py

Incrementally retrain the F1 winner prediction model with new season data.
Backs up the current model, adds new years, retrains, and prints a
before-vs-after accuracy table so you can decide whether to keep the new model.

Usage:
  python retrain_model.py                          # adds 2025 + 2026 to existing training set
  python retrain_model.py --years 2026             # add only 2026
  python retrain_model.py --years 2025 2026        # add 2025 and 2026
  python retrain_model.py --from-scratch           # retrain 2018-2026 from scratch
  python retrain_model.py --years 2026 --dry-run   # show what data would be added
  python retrain_model.py --years 2026 --no-backup # skip model backup

Environment variables:
  FASTF1_CACHE_DIR   — FastF1 local cache directory (default: ./fastf1_cache)
  PRECOMPUTE_VERBOSE — set to 1 for full tracebacks
"""

import argparse
import json
import os
import shutil
import sys
import time
import traceback
import warnings
from datetime import datetime
from typing import Optional

import fastf1
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score

from data_ingestion import get_event_schedule, get_winner_prediction_data
from winner_feature_engineering import engineer_winner_features
from winner_model import (
    WINNER_MODEL_PATH,
    MODELS_DIR,
    train_and_evaluate_winner_model,
    load_best_winner_model,
    calculate_top3_accuracy,
    align_winner_features_to_model,
    predict_winner_probabilities,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RETRAIN_LOG   = "retrain_log.json"          # JSON history of retrain runs
BACKUP_SUFFIX = ".pre_retrain.joblib"       # suffix for model backup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _enable_cache() -> None:
    cache_dir = os.environ.get("FASTF1_CACHE_DIR", os.path.join(os.getcwd(), "fastf1_cache"))
    os.makedirs(cache_dir, exist_ok=True)
    fastf1.Cache.enable_cache(cache_dir)


def _fmt(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s"


def _bar(done: int, total: int, w: int = 28) -> str:
    filled = int(w * done / max(total, 1))
    return "[" + "█" * filled + "░" * (w - filled) + f"] {done}/{total}"


def _backup_model() -> Optional[str]:
    """Copy current model to a timestamped backup. Returns backup path or None."""
    if not os.path.exists(WINNER_MODEL_PATH):
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = WINNER_MODEL_PATH.replace(".joblib", f"_{ts}{BACKUP_SUFFIX}")
    shutil.copy2(WINNER_MODEL_PATH, backup_path)
    print(f"  Backup → {backup_path}")
    return backup_path


def _evaluate_existing_model(X: pd.DataFrame, y: pd.Series) -> Optional[dict]:
    """Score the current saved model on the supplied data, returns metrics or None."""
    result = load_best_winner_model()
    if result is None:
        return None
    model, expected_features = result
    X_aligned = align_winner_features_to_model(X, expected_features)
    if X_aligned.empty:
        return None
    try:
        proba = predict_winner_probabilities(model, X_aligned)
        preds = (proba >= 0.5).astype(int)
        auc  = float(roc_auc_score(y, proba))   if y.sum() > 0 else 0.0
        ll   = float(log_loss(y, proba))         if y.sum() > 0 else 1.0
        acc  = float(accuracy_score(y, preds))
        top3 = float(calculate_top3_accuracy(y.values, proba))
        return {"roc_auc": auc, "log_loss": ll, "accuracy": acc, "top3_accuracy": top3,
                "n_samples": len(y), "n_winners": int(y.sum())}
    except Exception as e:
        print(f"  [warn] Could not evaluate existing model: {e}")
        return None


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_year_data(
    year: int,
    dry_run: bool = False,
) -> tuple[pd.DataFrame, pd.Series, dict]:
    """
    Load all race data for a given year and engineer winner features.

    Returns (X, y, summary) where summary has per-GP counts.
    """
    _enable_cache()
    summary = {"year": year, "gps_attempted": 0, "gps_loaded": 0, "drivers": 0}

    schedule = get_event_schedule(year)
    if schedule.empty or "EventName" not in schedule.columns:
        print(f"  [warn] No schedule found for {year}")
        return pd.DataFrame(), pd.Series(dtype=int), summary

    gps = schedule["EventName"].dropna().tolist()
    summary["gps_attempted"] = len(gps)

    if dry_run:
        print(f"  DRY RUN: would process {len(gps)} GPs for {year}")
        for g in gps:
            print(f"    · {g}")
        return pd.DataFrame(), pd.Series(dtype=int), summary

    X_parts, y_parts = [], []

    for i, gp in enumerate(gps, 1):
        print(f"  {_bar(i, len(gps))}  {year} · {gp}", end="  ", flush=True)
        try:
            winner_data = get_winner_prediction_data(year, gp)
            if winner_data.empty:
                print("→ no data")
                continue
            X_gp, y_gp = engineer_winner_features(
                winner_data, year, gp,
                include_historical=True, include_practice=True,
            )
            if X_gp.empty or y_gp.empty:
                print("→ no features")
                continue
            X_parts.append(X_gp)
            y_parts.append(y_gp)
            summary["gps_loaded"] += 1
            summary["drivers"]    += len(X_gp)
            print(f"→ {len(X_gp)} drivers ✓")
        except Exception as e:
            print(f"→ skipped ({e})")
            if os.environ.get("PRECOMPUTE_VERBOSE"):
                traceback.print_exc()

    if not X_parts:
        return pd.DataFrame(), pd.Series(dtype=int), summary

    X = pd.concat(X_parts, ignore_index=True)
    y = pd.concat(y_parts, ignore_index=True)
    return X, y, summary


def load_baseline_data(
    base_years: list[int],
    dry_run: bool = False,
) -> tuple[pd.DataFrame, pd.Series]:
    """Load + concatenate feature data for the baseline training years."""
    X_all, y_all = [], []
    for year in base_years:
        print(f"\n── {year} (baseline) ──────────────────────────────────")
        X, y, info = load_year_data(year, dry_run=dry_run)
        if not X.empty:
            X_all.append(X)
            y_all.append(y)
            print(f"  Year totals: {info['gps_loaded']}/{info['gps_attempted']} GPs, "
                  f"{info['drivers']} driver-race rows")
    if not X_all:
        return pd.DataFrame(), pd.Series(dtype=int)
    return pd.concat(X_all, ignore_index=True), pd.concat(y_all, ignore_index=True)


# ---------------------------------------------------------------------------
# Comparison printing
# ---------------------------------------------------------------------------

def _pct(v: float) -> str:
    return f"{v * 100:.2f}%"


def print_comparison(before: Optional[dict], after: dict, new_years: list[int]) -> None:
    cols = ["roc_auc", "log_loss", "accuracy", "top3_accuracy"]
    labels = ["ROC-AUC ↑", "Log Loss ↓", "Accuracy ↑", "Top-3 Acc ↑"]
    better = [True, False, True, True]  # True = higher is better

    print(f"\n{'='*62}")
    print("  ACCURACY COMPARISON")
    print(f"{'='*62}")
    print(f"  {'Metric':<16}  {'Before':>10}  {'After':>10}  {'Delta':>10}  {'Verdict':>8}")
    print(f"  {'-'*16}  {'-'*10}  {'-'*10}  {'-'*10}  {'-'*8}")

    wins, losses = 0, 0

    for col, label, hi_better in zip(cols, labels, better):
        b_val = before[col] if before else None
        a_val = after.get(col)

        b_str = f"{b_val:.4f}" if b_val is not None else "   N/A"
        a_str = f"{a_val:.4f}" if a_val is not None else "   N/A"

        if b_val is not None and a_val is not None:
            delta  = a_val - b_val
            delta_str = f"{delta:+.4f}"
            improved = (delta > 0) if hi_better else (delta < 0)
            verdict = "✓ BETTER" if improved else ("= SAME" if delta == 0 else "✗ WORSE")
            if improved:   wins   += 1
            elif delta != 0: losses += 1
        else:
            delta_str = "       -"
            verdict   = "-"

        print(f"  {label:<16}  {b_str:>10}  {a_str:>10}  {delta_str:>10}  {verdict:>8}")

    print(f"\n  Training set: {after.get('n_samples', '?')} driver-race rows "
          f"({after.get('n_winners', '?')} race winners)")
    print(f"  New data added: {new_years}")
    print()

    if before is None:
        print("  (No baseline model found — this is the first training run)")
    elif wins > losses:
        print("  ✓  New model is better on balance. Keeping new model.")
    elif wins == losses:
        print("  =  Models are roughly equivalent. New model saved (has fresher data).")
    else:
        print("  !  New model may be slightly worse. It's still saved because it has")
        print("     more recent data. Roll back with: python retrain_model.py --restore")


# ---------------------------------------------------------------------------
# Retrain log
# ---------------------------------------------------------------------------

def _append_retrain_log(entry: dict) -> None:
    log = []
    if os.path.exists(RETRAIN_LOG):
        try:
            with open(RETRAIN_LOG) as f:
                log = json.load(f)
        except Exception:
            pass
    log.append(entry)
    with open(RETRAIN_LOG, "w") as f:
        json.dump(log, f, indent=2, default=str)
    print(f"  Retrain log updated → {RETRAIN_LOG}")


def restore_latest_backup() -> None:
    """Restore the most recent model backup (--restore flag)."""
    backups = sorted(
        [f for f in os.listdir(MODELS_DIR) if BACKUP_SUFFIX in f],
        reverse=True,
    )
    if not backups:
        print("No backup found.")
        return
    src = os.path.join(MODELS_DIR, backups[0])
    shutil.copy2(src, WINNER_MODEL_PATH)
    print(f"Restored: {src} → {WINNER_MODEL_PATH}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Retrain F1 winner model with new season data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--years", nargs="*", type=int, default=[2025, 2026],
        help="New years to add to the training set (default: 2025 2026).",
    )
    parser.add_argument(
        "--from-scratch", action="store_true",
        help="Retrain from 2018 onwards (ignores existing model entirely).",
    )
    parser.add_argument(
        "--base-years", nargs="*", type=int, default=None,
        help="Override baseline years (default: 2018-2024). Only used with --from-scratch.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show which GPs would be loaded without downloading anything.",
    )
    parser.add_argument(
        "--no-backup", action="store_true",
        help="Skip backing up the current model before overwriting.",
    )
    parser.add_argument(
        "--restore", action="store_true",
        help="Restore the most recent model backup and exit.",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print full tracebacks on data-loading errors.",
    )
    args = parser.parse_args()

    if args.verbose:
        os.environ["PRECOMPUTE_VERBOSE"] = "1"

    # ── Quick restore path ────────────────────────────────────────────────
    if args.restore:
        restore_latest_backup()
        return

    # ── Determine what to train on ────────────────────────────────────────
    new_years = sorted(set(args.years or []))
    current_year = datetime.now().year

    if args.from_scratch:
        base_years = args.base_years or list(range(2018, current_year))
        all_years  = sorted(set(base_years + new_years))
    else:
        all_years = new_years   # incremental: only new data + existing model

    print("=" * 62)
    print("  F1 Winner Model — Retraining")
    print(f"  Mode        : {'FROM SCRATCH' if args.from_scratch else 'INCREMENTAL'}")
    print(f"  New years   : {new_years}")
    if args.from_scratch:
        print(f"  All years   : {all_years}")
    print(f"  Dry run     : {args.dry_run}")
    print("=" * 62)

    t_start = time.time()

    # ── Load new year(s) data ─────────────────────────────────────────────
    print("\n── Loading new season data ────────────────────────────────")
    X_new_parts, y_new_parts, year_summaries = [], [], []

    for year in new_years:
        print(f"\n── {year} ──────────────────────────────────────────────────")
        X, y, info = load_year_data(year, dry_run=args.dry_run)
        year_summaries.append(info)
        if not X.empty:
            X_new_parts.append(X)
            y_new_parts.append(y)
            print(f"  Year totals: {info['gps_loaded']}/{info['gps_attempted']} GPs, "
                  f"{info['drivers']} driver-race rows, {int(y.sum())} winners")

    if args.dry_run:
        print("\n  Dry run complete. No model changes made.")
        return

    if not X_new_parts and not args.from_scratch:
        print("\n  No new data loaded. Nothing to retrain on. Exiting.")
        sys.exit(1)

    X_new = pd.concat(X_new_parts, ignore_index=True) if X_new_parts else pd.DataFrame()
    y_new = pd.concat(y_new_parts, ignore_index=True) if y_new_parts else pd.Series(dtype=int)

    # ── Build full training dataset ───────────────────────────────────────
    if args.from_scratch:
        # Load baseline years too
        print("\n── Loading baseline years ─────────────────────────────────")
        base_years_to_load = [yr for yr in all_years if yr not in new_years]
        X_base, y_base = load_baseline_data(base_years_to_load, dry_run=False)
        if not X_base.empty and not X_new.empty:
            X_train = pd.concat([X_base, X_new], ignore_index=True)
            y_train = pd.concat([y_base, y_new], ignore_index=True)
        elif not X_base.empty:
            X_train, y_train = X_base, y_base
        elif not X_new.empty:
            X_train, y_train = X_new, y_new
        else:
            print("\n  No training data loaded. Exiting.")
            sys.exit(1)
    else:
        # Incremental: load existing training data from disk if present,
        # otherwise treat new years as the full training set.
        train_cache = os.path.join(MODELS_DIR, "training_data_cache.joblib")
        if os.path.exists(train_cache):
            print(f"\n  Loading cached training data from {train_cache}…")
            cached = joblib.load(train_cache)
            X_cached, y_cached = cached["X"], cached["y"]
            print(f"  Cached: {len(X_cached)} rows. Adding {len(X_new)} new rows.")
            X_train = pd.concat([X_cached, X_new], ignore_index=True)
            y_train = pd.concat([y_cached, y_new], ignore_index=True)
        else:
            # No cache found; load the full baseline set
            print("\n  No cached training data found — loading 2018-2024 baseline…")
            base_years = list(range(2018, min(new_years)))
            X_base, y_base = load_baseline_data(base_years, dry_run=False)
            if not X_base.empty:
                X_train = pd.concat([X_base, X_new], ignore_index=True)
                y_train = pd.concat([y_base, y_new], ignore_index=True)
            else:
                X_train, y_train = X_new, y_new

    print(f"\n  Final training set: {len(X_train)} rows, {int(y_train.sum())} winners")

    # ── Evaluate BEFORE ───────────────────────────────────────────────────
    print("\n── Evaluating existing model ──────────────────────────────")
    before_metrics = _evaluate_existing_model(X_train, y_train)
    if before_metrics:
        print(f"  Existing model → AUC {before_metrics['roc_auc']:.4f}  "
              f"Top3 {before_metrics['top3_accuracy']:.4f}")
    else:
        print("  No existing model found (or evaluation failed).")

    # ── Backup ────────────────────────────────────────────────────────────
    if not args.no_backup:
        print("\n── Backing up current model ───────────────────────────────")
        backup_path = _backup_model()
    else:
        backup_path = None

    # ── Retrain ───────────────────────────────────────────────────────────
    print("\n── Training ───────────────────────────────────────────────")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        after_raw = train_and_evaluate_winner_model(X_train, y_train)

    # Extract best model's metrics (GradientBoosting or LogisticRegression)
    after_metrics: dict = {}
    for key, val in after_raw.items():
        if key == "best_model_path":
            continue
        if not after_metrics or val.get("roc_auc", 0) > after_metrics.get("roc_auc", 0):
            after_metrics = dict(val)
    after_metrics["n_samples"] = len(X_train)
    after_metrics["n_winners"] = int(y_train.sum())

    # ── Save training data cache for next incremental run ─────────────────
    os.makedirs(MODELS_DIR, exist_ok=True)
    train_cache = os.path.join(MODELS_DIR, "training_data_cache.joblib")
    joblib.dump({"X": X_train, "y": y_train, "years": all_years}, train_cache)
    print(f"\n  Training data cached → {train_cache}")

    # ── Print comparison ───────────────────────────────────────────────────
    print_comparison(before_metrics, after_metrics, new_years)

    elapsed = time.time() - t_start
    print(f"  Total time  : {_fmt(elapsed)}")

    # ── Append to retrain log ─────────────────────────────────────────────
    _append_retrain_log({
        "timestamp":   datetime.now().isoformat(),
        "new_years":   new_years,
        "from_scratch": args.from_scratch,
        "n_samples":   len(X_train),
        "n_winners":   int(y_train.sum()),
        "before":      before_metrics,
        "after":       after_metrics,
        "backup":      backup_path,
        "elapsed_s":   round(elapsed, 1),
    })

    print(f"\n  Model saved → {WINNER_MODEL_PATH}")
    print("  Restart the backend server to load the new model.\n")


if __name__ == "__main__":
    main()
