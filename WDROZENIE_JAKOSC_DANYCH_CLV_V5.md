# KANIBAL — jakość danych, CLV i selekcja v5

## Cel

Aktualizacja poprawia materiał uczący i selekcję rekomendacji. Nie zmienia
algorytmu wyliczającego prawdopodobieństwo i nie uruchamia automatycznej
promocji challengera.

## Wdrożone mechanizmy

- niezmienny ledger danych dostępnych w chwili decyzji,
- zapis wersji strategii i modelu oraz skrótu SHA-256 snapshotu,
- jawny zapis brakujących cech bez zastępowania ich zerami,
- pobieranie kursu blisko rozpoczęcia meczu i prawidłowy CLV,
- adaptacyjny wymagany edge zależny od rynku, ligi, kursu i jakości danych,
- automatyczna kwarantanna ostatnio pogarszających się segmentów,
- jeden typ na mecz, blokada korelacji drużyna–dzień i wspólny limit dzienny,
- walidacja Brier/Log Loss/CLV/yield/drawdown z przedziałami ufności,
- wymóg stabilności w wielu foldach i co najmniej 80% pokrycia closing odds,
- wyłącznie ręczna promocja modelu po przejściu wszystkich bramek.

## Dane trwałe

Nowe dane są zapisywane wyłącznie na istniejącym wolumenie `/data`:

- `/data/quality_retraining/prediction_evidence.sqlite3`,
- rozszerzone kolumny tabeli `picks_history` w istniejącej bazie SQLite.

Migracja używa `ALTER TABLE ... ADD COLUMN` tylko dla brakujących kolumn. Nie
usuwa tabel, rekordów ani plików historii.

## Ustawienia domyślne

```text
BETBOT_MAX_DAILY_RECOMMENDATIONS=12
BETBOT_CLOSING_ODDS_WINDOW_MINUTES=45
BETBOT_QUALITY_MIN_CLOSING_COVERAGE=0.80
BETBOT_QUALITY_MIN_CLV_SAMPLES=100
BETBOT_QUALITY_QUARANTINE_WINDOW=100
BETBOT_MODEL_VERSION=champion-current
```

## Kryteria promocji

Challenger pozostaje kandydatem i nie może zostać aktywowany automatycznie.
Pozytywna walidacja wymaga między innymi dodatnich przedziałów ufności dla
Brier i Log Loss, dodatniego CLV z wystarczającej próby, odpowiedniego pokrycia
closing odds, braku pogorszenia kalibracji i drawdownu oraz stabilności foldów
i segmentów.

