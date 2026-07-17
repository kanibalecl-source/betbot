# Raport odzyskania historii i nauki

Pierwszy przekazany ZIP zawierał 318 plików kodu, ale nie zawierał katalogu `data`, plików CSV historii, baz SQLite ani zapisanych modeli.

Dane zostały odzyskane z dwóch lokalnych katalogów uruchomieniowych i scalone bez usuwania źródeł:

- kanoniczna baza historii: 194 unikalne rekordy;
- statusy: 194 `OPEN/PENDING`, 0 `CLOSED`;
- feature store AI: 9 rekordów;
- feature store AI LOW: 73 rekordy;
- feature store AI RISK: 13 rekordów;
- razem w trzech feature store: 95 rekordów.

Brak wygranych, profitu i ROI jest obecnie prawidłowy: żaden z odzyskanych typów nie ma jeszcze potwierdzonego wyniku końcowego. Otwarte typy nie są traktowane jako przegrane ani jako próbki treningowe.

## Zabezpieczenie kolejnych wersji

Moduł `legacy_data_migration.py` automatycznie wykrywa starsze lokalne katalogi `betbot-main/data`, scala rekordy po trwałych identyfikatorach i zapisuje kopie w `data/legacy_backups`.

Zasady migracji:

- źródłowe pliki pozostają bez zmian;
- rekord `CLOSED` nigdy nie jest zastępowany rekordem `OPEN`;
- istniejące rekordy nie są dublowane;
- pliki historii append-only są scalane po `event_id` lub stabilnym skrócie;
- starsze modele są zachowywane jako kopie, a nie nadpisywane;
- na Railway automatyczne skanowanie lokalnych katalogów jest wyłączone.

Dashboard pokazuje teraz osobno liczbę wszystkich zapisanych rekordów, rekordów rozliczonych i otwartych. Wczytuje również archiwa `auto_*_picks_history.csv` oraz wszystkie trzy profile nauki AI.
