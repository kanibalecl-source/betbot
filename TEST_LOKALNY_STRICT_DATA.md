# Lokalny test STRICT DATA

Ta paczka jest kopią testową. Nie łączy się z plikami działającej wersji serwerowej i nie wykonuje deployu.

1. Skopiuj `.env.local.example` jako `.env.local`.
2. Wpisz własny `API_FOOTBALL_KEY`. Bez klucza bot bezpiecznie zwróci brak danych i nie utworzy typów.
3. Uruchom `INSTALL_LOCAL_WINDOWS.bat`, jeśli środowisko nie ma zależności.
4. Uruchom testy: `python -m unittest tests.test_strict_real_data -v`.
5. Uruchom lokalny system: `START_LOCAL_FULL.bat`.

Dane testowe trafią do `local_data`. Pusty albo błędny odczyt API nie nadpisuje ostatnich picków ani historii.

Paczka z odzyskaną historią zawiera startowy katalog `data`. Przy lokalnym starcie moduł `legacy_data_migration.py` wykryje także starsze kopie w sąsiednich katalogach `bot_upgrade` i scali nowe rekordy bez modyfikowania źródeł. Dodatkowe katalogi można wskazać zmienną `KANIBAL_LEGACY_DATA_DIRS` (na Windows ścieżki rozdziel średnikiem).

## Warunek bezpiecznego późniejszego wdrożenia

Na Railway podłącz trwały Volume i ustaw `PERSISTENT_DATA_DIR` albo `RAILWAY_VOLUME_MOUNT_PATH` na katalog montowania. Launcher serwerowy zatrzyma start, jeśli wykryje Railway bez trwałego katalogu. To celowa blokada przed utratą historii po redeployu.

Przed pierwszym wdrożeniem skopiuj cały dotychczasowy katalog `data` do Volume. Migracja w `storage_paths.py` kopiuje brakujące pliki i nigdy nie zastępuje istniejącego, niepustego pliku.
