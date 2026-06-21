@echo off
title F1 Model Training (this will take 30-60 min)
cd /d "D:\prediction system"
echo Training winner model on 2018-2025 F1 data...
echo Output is ALSO being saved to training_log.txt - window closing won't lose progress.
echo Do NOT close this window.
echo.
".venv\Scripts\python.exe" -u main.py
echo.
echo === Process exited with code %ERRORLEVEL% ===
echo Check training_log.txt in D:\prediction system for full output.
pause
