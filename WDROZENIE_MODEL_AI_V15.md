# KANIBAL Model AI V15 — bezpieczne wdrożenie nakładkowe

## Zakres

- zastępuje pozycje `AI` i `Czat GPT` jedną pozycją `Model AI`;
- pozostawia istniejący silnik AI, bramki jakości, modele i automatykę bez zmian;
- pokazuje liczbę kandydatów, zaakceptowanych i odrzuconych przez bramki;
- dodaje filtry ligi, rynku i statusu;
- zachowuje paginację po 10 typów;
- uruchamia pełną analizę GPT dopiero po kliknięciu przy konkretnym meczu;
- używa pełnego promptu `model_ai_analysis_prompt_v2.txt`;
- raport GPT jest oddzielony od typów, historii uczącej i aktywnego modelu.

## Wdrożenie

Wgraj zawartość ZIP do katalogu głównego istniejącego repozytorium, zachowując
strukturę plików. Nie usuwaj woluminu `/data` i nie zastępuj jego zawartości.
Następnie wykonaj zwykły redeploy usługi.

## Ochrona danych

Paczka nie zawiera katalogu `data`, baz SQLite, plików CSV historii, modeli,
cache, sekretów ani plików `.env`. Jest nakładką kodową na aktualną wersję.

## Wymagane zmienne

Pełna analiza na żądanie wymaga istniejącej zmiennej `OPENAI_API_KEY`.
Brak klucza nie zatrzymuje zakładki ani generowania typów — blokuje tylko
zewnętrzną analizę GPT.
