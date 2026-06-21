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
git commit -m "fix: set Render backend URL in netlify.toml"
echo.
echo Pushing to GitHub...
git push origin main
echo.
echo === Done - Netlify will auto-deploy ===
pause
