# Paczka serwerowa — bezpieczna szata graficzna

## Przeznaczenie

Paczka łączy nową szatę graficzną z aktualną logiką bota i jest przeznaczona do wdrożenia na Railway po lokalnej akceptacji wyglądu.

## Zawartość danych

- paczka nie zawiera katalogu `data`,
- paczka nie zawiera baz SQLite, historii wyników ani plików nauki,
- dane serwera muszą pochodzić wyłącznie z podłączonego Railway Volume,
- kod zachowuje mechanizm kopii bezpieczeństwa wykonywanej przed startem deploymentu.

## Nienaruszona logika

- prawdziwe dane LIVE i ich walidacja,
- własne kursy i odrzucanie danych zastępczych,
- typowanie, rozliczanie, historia append-only i nauka AI,
- ukryty prompt analityczny,
- `storage_paths.py`, `server_data_guard.py` oraz obsługa `/data`.

## Zmiany wizualne

- nowy motyw KANIBAL Trading Desk,
- nowa strona logowania bez zmiany uwierzytelniania,
- pasek aplikacji, baner, ikony KPI i styl wszystkich zakładek.

## Warunek wdrożenia

Railway Volume musi pozostać zamontowany pod `/data`. Nie wolno usuwać ani zastępować istniejącego Volume podczas redeploy.
