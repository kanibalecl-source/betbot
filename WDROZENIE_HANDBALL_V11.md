# Piłka ręczna v11 — wdrożenie serwerowe

## Zakres

Moduł piłki ręcznej jest trzecim, całkowicie izolowanym sportem. Korzysta z
oddzielnego procesu, katalogu danych i bazy:

`/data/handball/handball_shadow.sqlite3`

Nie zapisuje do baz piłki nożnej ani siatkówki. Działa wyłącznie w trybie
`SHADOW`, bez możliwości wykonania zakładu realnym kapitałem.

## Funkcje autonomiczne

- pobieranie terminarza i wyników,
- historyczny backfill,
- pobieranie kursów,
- kontrola tożsamości meczu, ligi i drużyn,
- kwarantanna błędnych rekordów,
- konsensus kursów minimum dwóch bukmacherów,
- generowanie typów shadow,
- automatyczne rozliczanie i ponowny audyt rozliczeń,
- zapis closing line i CLV,
- chronologiczny zbiór treningowy bez przecieku przyszłości,
- automatyczne tworzenie odtwarzalnego kandydata,
- walk-forward Champion–Challenger,
- live shadow,
- automatyczna promocja wyłącznie modelu handball shadow,
- automatyczny rollback po negatywnych raportach lub dryfie.

## Bezpieczny rynek początkowy

Moduł przyjmuje wyłącznie dwudrożny rynek zwycięzcy bez opcji remisowej,
oznaczony wewnętrznie jako `MATCH_WINNER_NO_DRAW`.

Rynek 1X2 zawierający `Draw`, `X`, `Tie` lub `Remis` jest automatycznie
odrzucany. Zapobiega to fałszywemu value powstałemu przez usunięcie kursu na
remis z rynku trójdrożnego.

Remis w zakończonym meczu zamyka istniejący typ dwudrożny jako `VOID` i nie
trafia do treningu modelu binarnego.

## Zmienne Railway

```text
BETBOT_HANDBALL_ENABLED=1
BETBOT_HANDBALL_SHADOW_ONLY=1
HANDBALL_API_SPORTS_KEY=<klucz API-Sports Handball>
HANDBALL_API_SPORTS_BASE_URL=https://v1.handball.api-sports.io
BETBOT_HANDBALL_TIMEZONE=Europe/Warsaw
BETBOT_HANDBALL_POLL_MINUTES=30
BETBOT_HANDBALL_BACKFILL_DAYS=30
BETBOT_HANDBALL_AUTONOMOUS_GOVERNOR_ENABLED=1
```

Pozostałe progi mają bezpieczne wartości domyślne zapisane w `.env.example`.

## Kolejność uruchomienia

1. Wgrać pliki z paczki jako nakładkę na istniejący kod.
2. Nie usuwać i nie zastępować katalogu `/data`.
3. Ustawić zmienne Railway.
4. Wykonać redeploy.
5. Sprawdzić log `HANDBALL v11.0 SHADOW START`.
6. Sprawdzić pierwszy `HANDBALL_SHADOW_CYCLE` ze statusem `HEALTHY`.
7. Otworzyć zakładkę `Piłka ręczna`.

## Warunek bezpieczeństwa

Nie ustawiaj `BETBOT_HANDBALL_SHADOW_ONLY=0`. Konfiguracja odrzuci taki start.
Aktywne modele piłki nożnej i siatkówki nie są modyfikowane.

