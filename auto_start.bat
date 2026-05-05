@echo off

cd /d %~dp0

echo ==========================
echo STARTING BETBOT SYSTEM...
echo ==========================

call venv\Scripts\activate

REM 🔥 BOT (zminimalizowane okno)
start "" /min cmd /k python main.py loop

timeout /t 5

REM 🔥 DASHBOARD (zminimalizowane okno)
start "" /min cmd /k python -m streamlit run dashboard.py

timeout /t 10

REM 🔥 otwórz przeglądarkę
start "" http://localhost:8501