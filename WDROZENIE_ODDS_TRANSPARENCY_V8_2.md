# BetBot v8.2 — przejrzystość kursów

## Zakres

- Kurs modelu: `1 / surowe prawdopodobieństwo modelu`.
- Kurs bota: `1 / końcowe prawdopodobieństwo po ensemble i korektach`.
- Kurs bukmachera: rzeczywisty kurs zapisany przy decyzji.
- Value: wyliczane spójnie jako `(kurs_buk / kurs_bota - 1) * 100%`.
- Kurs zamknięcia i CLV: pokazywane tylko wtedy, gdy zostały rzeczywiście zebrane.
- Widoki: Na żywo, Przedmeczowe, AI, szczegóły AI i Czat GPT.

## Zasady bezpieczeństwa danych

- Brakujące dane pozostają jako `-` albo `oczekuje`.
- Interfejs nie tworzy zastępczych kursów.
- Starsze pliki CSV pozostają kompatybilne; nowe kolumny są opcjonalne.
- Paczka nie zawiera katalogu `data`, baz, historii, modeli, użytkowników ani sekretów.
- Zmiana nie wpływa na wybór typu, prawdopodobieństwo ani decyzję o stawce.

## Wdrożenie

Wgraj wyłącznie pliki zawarte w paczce, zachowując strukturę katalogów, a następnie
uruchom redeploy usługi. Nie usuwaj i nie zastępuj woluminu `/data`.

Po wdrożeniu nowe rekordy będą zawierały również `closing_odds`, jeśli źródło
udostępniło prawidłowy kurs zamknięcia. Dla aktywnych meczów pole zwykle pokazuje
`oczekuje`, co jest zachowaniem prawidłowym.
