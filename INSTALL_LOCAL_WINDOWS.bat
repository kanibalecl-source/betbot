@echo off
setlocal
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"

echo ==========================================
echo  BETBOT - instalacja lokalna Windows
echo ==========================================

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  set PY_CMD=py -3
) else (
  where python >nul 2>nul
  if %ERRORLEVEL% EQU 0 (
    set PY_CMD=python
  ) else (
    echo Nie znaleziono Pythona. Zainstaluj Python 3.11+ i uruchom ponownie.
    pause
    exit /b 1
  )
)

if not exist ".venv" (
  echo Tworze lokalne srodowisko .venv...
  %PY_CMD% -m venv .venv
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Gotowe.
echo Teraz skopiuj .env.local.example jako .env.local i wpisz klucze API.
echo Potem uruchom START_LOCAL_FULL.bat
pause

