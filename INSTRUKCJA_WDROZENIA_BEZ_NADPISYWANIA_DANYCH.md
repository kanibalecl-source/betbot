# Instrukcja wdrozenia bez nadpisywania danych

## Paczka

Uzyj paczki:

`KANIBAL_FINAL_SERWER_NO_DATA_OVERWRITE.zip`

Ta paczka NIE zawiera katalogu `data`, dzieki czemu nie wnosi pustych plikow typow na serwer.

## Najwazniejsze

Nie usuwaj katalogu danych bota na serwerze.

Na Railway nie usuwaj:

- Volume,
- Variables,
- danych wskazanych przez `PERSISTENT_DATA_DIR`,
- danych w `/data`, jezeli tam masz Volume.

## Przed deployem

Sprawdz w Railway Variables:

- `API_FOOTBALL_KEY`
- `OPENAI_API_KEY`, jezeli GPT ma dzialac
- `PERSISTENT_DATA_DIR` albo `RAILWAY_VOLUME_MOUNT_PATH`, jezeli uzywasz Volume

Najlepiej ustaw:

`PERSISTENT_DATA_DIR=/data`

o ile Twoj Volume jest pod `/data`.

## Wdrozenie

1. Nie kasuj Volume.
2. Nie kasuj katalogu danych.
3. Podmien tylko pliki kodu aplikacji zawartoscia ZIP-a.
4. Zrob redeploy.
5. W logach sprawdz:
   - czy scheduler startuje,
   - czy dashboard startuje,
   - czy `FETCHING MATCHES: main + low + risk` dziala,
   - czy `PREMATCH LOW` i `PREMATCH RISK` zapisuja typy.

## Jezeli po deployu dalej jest 0 typow

Sprawdz w logach linie:

- `RAW FIXTURES`
- `NORMALIZED MATCHES`
- `MECZE`
- `SKIP STATS`

Jezeli `Low` i `Risk` generuja typy, a `Prematch` ma 0, to problem jest w filtrach/top ligach glownego profilu, nie w stronie WWW.

Jezeli wszystkie trzy maja 0, najpierw sprawdz:

- czy `API_FOOTBALL_KEY` jest poprawny,
- czy API nie zwraca 0 fixtures,
- czy Volume jest widoczny,
- czy paczka nie nadpisala danych.
