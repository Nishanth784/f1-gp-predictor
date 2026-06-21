@echo off
title Git Commit + Push
cd /d "D:\prediction system"
echo Removing git lock if exists...
if exist ".git\index.lock" del /f ".git\index.lock"
echo.
echo Staging all changes...
git add -A
echo.
echo Committing...
git commit -m "feat: winner-only prediction rebuild + F1 HUD frontend"
echo.
echo Pushing to GitHub...
git push
echo.
echo === Done ===
pause
