# BetBot V14.2 — wspólny trwały katalog danych AI

## Poprawka

Moduł `ai_self_learning_runtime.py` korzysta teraz z `get_data_dir()`,
czyli dokładnie tego samego katalogu danych co główny bot.

Na Railway oznacza to odczyt i zapis w zamontowanym woluminie `/data`.
AI odczytuje więc plik:

```text
/data/auto_all_picks.csv
```

zapisany wcześniej przez cykl prematch.

## Zakres bezpieczeństwa

- Brak zmiany progów i punktacji AI.
- Brak zmiany zasad publikowania typów.
- Brak automatycznej promocji modelu.
- Brak kasowania, przenoszenia lub nadpisywania historii.
- Brak plików danych, modeli, baz i sekretów w paczce.
- Raport `GATE REPORT` z V14.1 pozostaje aktywny.

Po wdrożeniu liczba `candidates` w raporcie powinna odpowiadać liczbie rekordów
dostępnych w aktualnym pliku prematch, zanim zostaną zastosowane bramki AI.
