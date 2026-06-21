@echo off
title Git Push to GitHub
cd /d "D:\prediction system"
echo Removing git lock if exists...
if exist ".git\index.lock" del /f ".git\index.lock"
echo.
echo Setting remote URL...
git remote set-url origin https://github.com/Nishanth784/f1-gp-predictor.git
echo.
echo Staging changes...
git add -A
echo.
echo Committing...
git commit -m "feat: add 2026 season support + upgrade fastf1 to 3.8.3"
echo.
echo Pushing to GitHub...
git push origin main
echo.
echo === Done - Render will redeploy ===
pause
