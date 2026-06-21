@echo off
title F1 Winner Model Training — Extended Features
cd /d "D:\prediction system"
echo ============================================================
echo  F1 Winner Model Training — Extended Feature Set
echo  NEW: Chaos index, SC rate, grid spread features included
echo  Takes 20-40 min. Do NOT close this window.
echo  Progress also saved to training_log.txt
echo ============================================================
echo.
".venv\Scripts\python.exe" -u main.py
echo.
echo === Done — exit code %ERRORLEVEL% ===
echo Check training_log.txt for AUC score and comparison.
echo New model saved to: models\winner_model.joblib
pause
