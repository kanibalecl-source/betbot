@echo off
echo === TWORZENIE BACKUPU Z DATA ===

:: Pobierz datę i godzinę
for /f "tokens=1-4 delims=/ " %%a in ("%date%") do (
    set YYYY=%%d
    set MM=%%b
    set DD=%%c
)

for /f "tokens=1-2 delims=: " %%a in ("%time%") do (
    set HH=%%a
    set MIN=%%b
)

:: Usuń spacje z godziny
set HH=%HH: =0%

:: Nazwa folderu backup
set BACKUP_DIR=backup_%YYYY%-%MM%-%DD%_%HH%-%MIN%

mkdir %BACKUP_DIR%

echo Folder: %BACKUP_DIR%

:: Kopiuj pliki
copy bot.py %BACKUP_DIR%\
copy data_api.py %BACKUP_DIR%\
copy config.py %BACKUP_DIR%\
copy model.py %BACKUP_DIR%\
copy dashboard.py %BACKUP_DIR%\

:: Kopiuj dane
xcopy data %BACKUP_DIR%\data /E /I /Y

echo === BACKUP GOTOWY ===
pause