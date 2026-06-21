@echo off
title F1 Backend (port 8011)
cd /d "D:\prediction system"
echo Starting FastAPI backend on port 8011...
".venv\Scripts\python.exe" -m uvicorn backend.main:app --port 8011 --reload
