@echo off
title BetBot - BACKUP CURRENT VERSION
echo ====================================================
echo TWORZENIE KOPII BEZPIECZENSTWA OBECNEGO BOTA
echo ====================================================
echo.

if not exist _backups mkdir _backups

set BACKUP_DIR=_backups\BASELINE_%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%
set BACKUP_DIR=%BACKUP_DIR: =0%
mkdir "%BACKUP_DIR%" >nul 2>nul

echo Kopiuje pliki .py, .json, .csv, .cmd oraz folder data...
copy *.py "%BACKUP_DIR%" >nul 2>nul
copy *.json "%BACKUP_DIR%" >nul 2>nul
copy *.cmd "%BACKUP_DIR%" >nul 2>nul
copy *.csv "%BACKUP_DIR%" >nul 2>nul
xcopy data "%BACKUP_DIR%\data" /E /I /Y >nul 2>nul
xcopy templates "%BACKUP_DIR%\templates" /E /I /Y >nul 2>nul
xcopy static "%BACKUP_DIR%\static" /E /I /Y >nul 2>nul

echo.
echo GOTOWE. Backup zapisany w:
echo %BACKUP_DIR%
echo.
pause
