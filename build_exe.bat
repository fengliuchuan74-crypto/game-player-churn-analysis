@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Create the project virtual environment with the dependency installer first.
  pause
  exit /b 1
)
if exist "dist\churn-analysis-app.exe" (
  echo An EXE already exists in dist. Close it and move or rename it before rebuilding.
  echo This script will not stop running applications or delete an existing EXE.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m PyInstaller churn-analysis-app.spec
if errorlevel 1 goto fail
echo Build completed: dist\churn-analysis-app.exe
pause
exit /b 0

:fail
echo Build failed. Check the output above.
pause
exit /b 1
