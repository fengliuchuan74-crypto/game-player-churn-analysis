@echo off
setlocal
cd /d "%~dp0"
if not exist "launcher.py" (
  echo Application source was not found.
  pause
  exit /b 1
)
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" launcher.py
  if errorlevel 1 goto fail
  exit /b 0
)
py -3.12 -c "import streamlit, pandas, openpyxl, xlrd" >nul 2>nul
if not errorlevel 1 (
  py -3.12 launcher.py
  if errorlevel 1 goto fail
  exit /b 0
)
python -c "import streamlit, pandas, openpyxl, xlrd" >nul 2>nul
if not errorlevel 1 (
  python launcher.py
  if errorlevel 1 goto fail
  exit /b 0
)
echo Python dependencies were not found. Run the dependency installer first.
pause
exit /b 1

:fail
echo The app stopped with an error. Check the output above.
pause
exit /b 1
