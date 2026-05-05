@echo off
echo === DOSTEPNE BACKUPY ===
dir /b /ad backup_*

echo.
set /p BACKUP_DIR=Podaj nazwe folderu backup: 

echo Przywracanie z: %BACKUP_DIR%

copy %BACKUP_DIR%\bot.py .
copy %BACKUP_DIR%\data_api.py .
copy %BACKUP_DIR%\config.py .
copy %BACKUP_DIR%\model.py .
copy %BACKUP_DIR%\dashboard.py .

xcopy %BACKUP_DIR%\data data /E /I /Y

echo === PRZYWRÓCONO ===
pause