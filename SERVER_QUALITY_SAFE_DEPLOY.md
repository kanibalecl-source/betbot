# Bezpieczne wdrożenie QUALITY SHADOW na produkcji

## Zweryfikowany stan Railway

- właściwy projekt dashboardu to `bot`, usługa `betbot`;
- osobny projekt `betbot-live` uruchamia `live_bot.py` i nie jest celem tej paczki;
- produkcyjny Volume `betbot-volume` jest zamontowany pod `/data`;
- `RAILWAY_VOLUME_MOUNT_PATH=/data` jest przekazywane automatycznie;
- start produkcji: `python -u app_launcher.py` z `railway.json`;
- aktywny commit bazowy: `cf5e6b6b8a96d24158160af22bcf2fccfb02744f`;
- `BETBOT_QUALITY_SHADOW` i `BETBOT_QUALITY_STATE` są obecnie nieustawione.

## Zasada nadrzędna

Paczka jest nakładką kodową. Nie wolno zastępować nią całego repozytorium ani
kopiować do niej katalogu `data`. Paczka celowo nie zawiera plików startowych,
storage ani guarda, dzięki czemu zachowuje działającą ochronę produkcyjną.

## Kolejność

1. Nałóż wyłącznie pliki z paczki na dokładny kod produkcyjny.
2. Pozostaw `BETBOT_QUALITY_SHADOW` wyłączone.
3. Wykonaj redeploy i sprawdź heartbeat: scheduler, settlement i dashboard.
4. Sprawdź log `SERVER DATA GUARD` oraz dostępność strony.
5. Dopiero po regresji uruchom odczytowy audyt `python server_readonly_audit.py`.
6. Nie aktywuj żadnego stanu uczonego przed analizą holdoutu.

## Budowa danych treningowych

`python build_quality_training_from_history.py`

Generator otwiera źródłowe CSV i SQLite tylko do odczytu, kontroluje ich hashe
przed i po ekstrakcji i tworzy atomowo wyłącznie:

- `/data/quality_training.csv`;
- `/data/quality_training.meta.json`.

Jeżeli plik wynikowy już istnieje, generator kończy pracę bez nadpisania.

## Trening

`python train_quality_shadow.py`

Trening tworzy wyłącznie `/data/quality_shadow_state.candidate.json`. Kandydat
nie jest stanem aktywnym i runtime nie odczytuje go automatycznie.

## Rollback

1. Ustaw lub pozostaw `BETBOT_QUALITY_SHADOW=0`.
2. Cofnij wyłącznie deployment kodu w Railway.
3. Nie usuwaj, nie czyść i nie przywracaj Volume.
4. Nie kopiuj żadnych plików `data` z paczki, bo paczka ich nie zawiera.
