@echo off
setlocal
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"

echo ==========================================
echo  BETBOT - tylko dashboard lokalnie
echo ==========================================

if exist ".env.local" (
  for /f "usebackq tokens=1,* delims==" %%A in (".env.local") do (
    if not "%%A"=="" if not "%%A:~0,1%"=="#" set "%%A=%%B"
  )
)

if "%LOCAL_PORT%"=="" set LOCAL_PORT=8501

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m streamlit run dashboard_streamlit.py --server.address 127.0.0.1 --server.port %LOCAL_PORT% --server.headless true --browser.gatherUsageStats false
) else (
  echo Brak .venv. Najpierw uruchom INSTALL_LOCAL_WINDOWS.bat
  pause
  exit /b 1
)

