# Wdrożenie serwerowe bez nadpisania historii i nauki

## Wymagane ustawienia Railway

1. Podłącz trwały Railway Volume pod `/data`.
2. Ustaw `PERSISTENT_DATA_DIR=/data`.
3. Pozostaw `KANIBAL_REQUIRE_PERSISTENT_STORAGE=1` (wartość domyślna).
4. Zachowaj obecne zmienne `API_FOOTBALL_KEY` i `OPENAI_API_KEY`.
5. Nie usuwaj ani nie twórz ponownie Volume podczas redeployu.

Bez zewnętrznego, zapisywalnego katalogu danych aplikacja przerwie start. Nie
przejdzie awaryjnie na nietrwały katalog wewnątrz deploymentu.

## Zabezpieczenia tej paczki

- ZIP serwerowy nie zawiera katalogu `data`.
- Na serwerze migracja danych z katalogu kodu jest wyłączona.
- Paczka zawierająca pliki w `data` zostanie odrzucona przy starcie.
- Przed uruchomieniem procesów tworzony jest backup SQLite, historii CSV,
  danych nauki i stanów modeli w:
  `/data/server_backups/deployments/<RAILWAY_DEPLOYMENT_ID>/`.
- Ponowny start tego samego deploymentu nie zastępuje jego backupu.
- Zamknięte rekordy `CLOSED` są niezmienne podczas synchronizacji nowych CSV.
- Eksport historii nie ma limitu 5000 rekordów.

## Po wdrożeniu

W logach muszą pojawić się:

- `SERVER DATA GUARD: ...BACKUP_CREATED` albo `ALREADY_BACKED_UP`,
- `APP LAUNCHER START`,
- start procesów `scheduler`, `settlement` i `dashboard`,
- cykle `PERSISTENCE/HISTORY OK` oraz automatycznego rozliczania.

Jeżeli Volume lub zmienna ścieżki są niepoprawne, nie wyłączaj zabezpieczenia.
Popraw montowanie `/data`, a następnie wykonaj redeploy.
