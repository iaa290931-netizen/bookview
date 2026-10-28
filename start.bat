@echo off
cd /d "%~dp0"
echo [1/3] Checking Python...
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% --version
if errorlevel 1 (
  echo.
  echo Python was not found.
  echo Install Python 3.12 from https://www.python.org/downloads/
  echo IMPORTANT: check "Add python.exe to PATH" on the first screen.
  echo Or use the GitHub exe method in README.txt
  pause
  exit /b 1
)
echo.
echo [2/3] Installing pygame and numpy. This can take 1-3 minutes...
%PY% -m pip install pygame numpy
if errorlevel 1 (
  echo.
  echo Install failed. Please send me the message above.
  pause
  exit /b 1
)
echo.
echo [3/3] Starting BookView...
%PY% bookview.py
pause
