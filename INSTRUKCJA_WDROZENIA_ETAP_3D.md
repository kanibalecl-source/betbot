# Instrukcja wdro?enia - Etap 3D final

## Przed wdro?eniem

1. Pobierz backup aktualnej aplikacji z serwera.
2. Upewnij si?, ?e Railway Variables zawieraj? klucze API.
3. Nie kasuj volume/katalogu `/data`.

## Wdro?enie

1. Wgraj ZIP Etapu 3D.
2. Zr?b redeploy/restart.
3. Sprawd? logi:
   - `APP LAUNCHER START`
   - `scheduler STARTED`
   - `BOT EXECUTED`
   - `PERSISTENCE/HISTORY OK`
   - `HEARTBEAT`
4. Otw?rz panel www.
5. Po jednym cyklu sprawd?, czy rosn? pliki w `data/history`.

## Test po wdro?eniu

- PREMATCH pokazuje typy lub zachowuje stare CSV, je?li API nie zwr?ci mecz?w.
- HISTORY nie znika.
- MOJE ZAK?ADY zapisuje single/AKO.
- SETTINGS zmienia profil filtr?w bez kasowania historii.
- GPT dzia?a, je?li `OPENAI_API_KEY` jest ustawiony.

## Cofni?cie

Wgraj poprzedni backup ZIP i zrestartuj us?ug?. Nie usuwaj `data/history`, bo to nowa historia append-only.
