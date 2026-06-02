@echo off
setlocal
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"

echo ==========================================
echo  BETBOT - pelny start lokalny
echo ==========================================
echo Ten tryb nie laczy sie z serwerem Railway i nie zmienia plikow na serwerze.
echo Wszystkie zapisy trafiaja do lokalnego folderu data w tej paczce.
echo.

if not exist ".env.local" (
  echo Brak .env.local
  echo Skopiuj .env.local.example jako .env.local i wpisz klucze API.
  pause
  exit /b 1
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" app_launcher_local.py
) else (
  echo Brak .venv. Najpierw uruchom INSTALL_LOCAL_WINDOWS.bat
  pause
  exit /b 1
)

