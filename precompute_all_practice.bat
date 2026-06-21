@echo off
title F1 Practice Data — Bulk Precompute
cd /d "D:\prediction system"
echo ============================================================
echo  F1 Practice Data — Bulk Precompute
echo  Extracts FP1/FP2/FP3 telemetry for all GPs and caches them.
echo  ~3-8 min per GP. Expect 1-2 hours for a full season.
echo  Do NOT close this window.
echo ============================================================
echo.
echo Default: precomputes 2024 + 2025 + 2026 (skips already cached)
echo To change, edit this .bat or run:
echo   python precompute_all_practice.py 2026
echo   python precompute_all_practice.py 2023 2026
echo.
echo Starting in 5 seconds... (Ctrl+C to abort)
timeout /t 5 >nul
echo.
".venv\Scripts\python.exe" -u precompute_all_practice.py 2024 2026 --skip-existing
echo.
echo === Done ===
pause
