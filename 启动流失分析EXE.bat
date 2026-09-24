@echo off
setlocal
cd /d "%~dp0"
if not exist "dist\churn-analysis-app.exe" (
  echo Published EXE not found.
  pause
  exit /b 1
)
start "" "%~dp0dist\churn-analysis-app.exe"
endlocal
