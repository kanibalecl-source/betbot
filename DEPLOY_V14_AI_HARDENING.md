# BetBot V14 — AI Hardening

## Zakres

- AI zachowuje dokładny rynek, kurs i konsensus rekordu źródłowego.
- Brak możliwości przeniesienia kursu lub EV pomiędzy rynkami.
- Rekord jest odrzucany, gdy brakuje identyfikatora meczu lub typu.
- Wymagany jest świeży kurs, zweryfikowany bukmacher z polskiej allowlisty,
  pełny rynek, status integralności `PASS` i konsensus co najmniej dwóch
  bukmacherów.
- Wymagane jest pozytywne przejście aktywnej bramki jakości.
- Brakujące dane nie są zastępowane przykładowymi wartościami.
- Identyfikator obserwacji jest deterministyczny.
- Feature store deduplikuje obserwacje i nie zwiększa próby przy każdym cyklu.
- Dla jednego meczu publikowany jest najwyżej jeden, najlepiej oceniony rynek.

## Bezpieczeństwo danych

Paczka nie zawiera katalogu `data`, historii, rozliczeń, modeli, baz SQLite,
plików środowiskowych ani sekretów. Wdrożenie nie usuwa i nie nadpisuje
istniejących danych na woluminie.

## Zachowanie fail-closed

Jeżeli wymagane pole jest nieobecne albo kurs jest nieaktualny, typ AI nie
zostanie opublikowany. Odrzucenie nie modyfikuje źródłowego typu głównego bota.
