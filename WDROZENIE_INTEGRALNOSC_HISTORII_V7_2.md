# BetBot v7.2 — integralność historii i rozliczeń

## Zakres

- zamknięte typy są niezmienne na poziomie SQLite (UPDATE i DELETE są blokowane),
- synchronizacja CSV pomija rekordy `CLOSED`,
- `results_history.csv` zawiera pełną historię, bez limitu 5000 rekordów,
- każde rozliczenie zapisuje wynik bramkowy i źródło,
- surowa odpowiedź dostawcy otrzymuje SHA-256,
- dowody rozliczeń tworzą niezmienny łańcuch hashy,
- zapis wyniku i dowodu odbywa się w jednej transakcji,
- zależności `requirements.txt` i `pyproject.toml` są zgodne,
- pliki konfiguracji administratora są wyłączone z obrazu Docker.

## Bezpieczeństwo wdrożenia

Paczka nie zawiera katalogu `data`, baz SQLite, CSV, historii, modeli, `.env`,
`users.json` ani danych Railway Volume. Migracja tworzy wyłącznie nowe kolumny,
tabelę dowodów oraz triggery ochronne. Istniejące rekordy nie są usuwane ani
przepisywane.

Po uruchomieniu `init_storage()` zmiany schematu są wykonywane idempotentnie.
Pierwsze nowe rozliczenie utworzy pierwszy wpis w `settlement_evidence`.
