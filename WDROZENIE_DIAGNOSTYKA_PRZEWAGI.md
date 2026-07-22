# Wdrożenie diagnostyki przewagi i selekcji jakościowej

## Zakres

Pakiet dodaje:

- raport integralności i jakości rozliczonych danych;
- ROI/yield, drawdown, CLV, Brier Score, Log Loss i kalibrację;
- rankingi oraz decyzje dla rynków, lig, par rynek–liga i przedziałów kursowych;
- kontrolę kompletności danych, świeżości kursów i rozbieżności modeli;
- segmentowe modele kandydujące z bezpiecznym fallbackiem do modelu globalnego;
- rozszerzone bramki walk-forward i live shadow;
- prezentację raportu w zakładce Analityka.

## Ochrona produkcji

- Historia i dane źródłowe są otwierane tylko do odczytu.
- Raporty powstają wyłącznie w `/data/quality_retraining/`.
- Aktywny model nie jest automatycznie zastępowany.
- Polityka selekcji działa fail-open, dopóki nie ma minimum 300 poprawnych
  rozliczonych rekordów i audyt integralności nie jest pozytywny.
- Nawet po osiągnięciu gotowości filtr może tylko odrzucić niepewny typ; nie
  zmienia prawdopodobieństwa ani kursu własnego bota.
- `BETTING_ENABLED` pozostaje `false`.

## Pliki pochodne na wolumenie

- `/data/quality_retraining/diagnostic_advantage_report.json`
- `/data/quality_retraining/quality_selection_policy.json`

Nie wolno dodawać tych plików do repozytorium ani paczki wdrożeniowej.

## Kontrola po redeployu

1. Potwierdź `PERSISTENT_DATA_DIR=/data` i podłączony Railway Volume.
2. Potwierdź pozytywny komunikat `SERVER DATA GUARD`.
3. Sprawdź heartbeat procesów schedulera, settlementu, retreningu i panelu.
4. W zakładce Analityka sprawdź sekcję `RAPORT DIAGNOSTYCZNY PRZEWAGI`.
5. Do czasu osiągnięcia wymaganej próby raport powinien pokazywać
   `ZBIERANIE DANYCH`; jest to prawidłowe zachowanie.
6. Promocja Challengera nadal wymaga pozytywnego walk-forward, pozytywnego
   live shadow oraz ręcznego potwierdzenia identyfikatora.
