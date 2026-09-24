@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install

py -3.12 -c "import sys" >nul 2>nul
if not errorlevel 1 (
  py -3.12 -m venv .venv
  if errorlevel 1 goto fail
  goto install
)

python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>nul
if errorlevel 1 (
  echo Python 3.12 was not found. Install Python 3.12 and enable Add to PATH.
  pause
  exit /b 1
)
python -m venv .venv
if errorlevel 1 goto fail

:install
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo Dependencies installed in this project's .venv folder.
pause
exit /b 0

:fail
echo Dependency installation failed. Existing project files were preserved.
pause
exit /b 1
