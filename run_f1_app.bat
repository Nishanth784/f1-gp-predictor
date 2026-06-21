@echo off
title F1 Predictor Launcher
echo Starting F1 Winner Prediction App...
echo.
start "F1 Backend" "D:\prediction system\start_backend.bat"
timeout /t 3 /nobreak >nul
start "F1 Frontend" "D:\prediction system\start_frontend.bat"
echo.
echo Backend: http://localhost:8011
echo Frontend: http://localhost:5173
echo.
pause
