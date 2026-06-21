@echo off
title Git Push to GitHub
cd /d "D:\prediction system"
echo Removing git lock if exists...
if exist ".git\index.lock" del /f ".git\index.lock"
echo.
echo Setting remote URL...
git remote set-url origin https://github.com/Nishanth784/f1-gp-predictor.git
echo.
echo Removing F1-lap-time-prediction submodule from git tracking...
git rm -r --cached "F1-lap-time-prediction" 2>nul
if exist ".gitmodules" del /f ".gitmodules"
echo.
echo Staging all changes (netlify.toml fix + submodule removal)...
git add -A
echo.
echo Committing...
git commit -m "fix: remove F1-lap-time-prediction submodule, fix netlify publish dir"
echo.
echo Pushing to GitHub...
git push origin main
echo.
echo === Done - Netlify will redeploy ===
pause
