@echo off
title BetBot - START ALL FULL
echo ====================================================
echo BETBOT START_ALL FULL
echo ====================================================
echo.

if not exist data mkdir data
if not exist reports mkdir reports
if not exist _backups mkdir _backups

echo [1/5] Tworze szybki backup plikow przed startem...
set BACKUP_DIR=_backups\before_start_%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%
set BACKUP_DIR=%BACKUP_DIR: =0%
mkdir "%BACKUP_DIR%" >nul 2>nul
copy *.py "%BACKUP_DIR%" >nul 2>nul
copy *.json "%BACKUP_DIR%" >nul 2>nul
copy *.cmd "%BACKUP_DIR%" >nul 2>nul
xcopy data "%BACKUP_DIR%\data" /E /I /Y >nul 2>nul

echo [2/5] Instaluje wymagane biblioteki...
python -m pip install -r requirements.txt

echo [3/5] Uruchamiam petle bota...
start "BetBot LOOP" cmd /k python bot_loop.py

echo [4/5] Uruchamiam petle rozliczania wynikow...
start "BetBot SETTLE LOOP" cmd /k python settle_loop.py

echo [5/5] Uruchamiam panel WWW...
start "BetBot WEB" cmd /k python app.py

echo.
echo GOTOWE.
echo Panel WWW: http://localhost:8000
echo.
pause
