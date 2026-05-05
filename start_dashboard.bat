@echo off

REM 🔥 przejdź do folderu projektu (gdzie jest ten plik)
cd /d %~dp0

echo Starting Dashboard...

REM aktywuj środowisko
call venv\Scripts\activate

REM uruchom dashboard w osobnym oknie
start cmd /k streamlit run dashboard.py

REM poczekaj aż się uruchomi
timeout /t 8

REM otwórz przeglądarkę
start http://localhost:8501