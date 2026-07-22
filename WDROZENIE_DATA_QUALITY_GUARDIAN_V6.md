# KANIBAL Data Quality Guardian v6

## Zakres

- niezmienne snapshoty kursów T-24h, T-6h, T-1h i T-15m,
- osobny kurs zamknięcia i prawidłowy CLV,
- monitoring ledgeru, rozliczeń, closing odds, świeżości i błędów,
- kontekst: odpoczynek, natężenie terminarza, składy i kontuzje,
- raport wpływu nowych cech na Brier, yield i CLV.

## Bezpieczeństwo

- aktywny model i jego prawdopodobieństwa nie są zmieniane,
- nowe cechy mają `shadow_only=true` i nie są czytane przez `bot.py`,
- brak automatycznej promocji Challengera,
- Guardian ocenia wyłącznie rekordy z identyfikatorem snapshotu nowego pipeline;
  wtórne tabele AI i historia sprzed v5 nie zaniżają pokrycia,
- raporty są plikami pochodnymi w `/data/quality_retraining`,
- migracje SQLite są wyłącznie addytywne (`CREATE TABLE IF NOT EXISTS`),
- paczka wdrożeniowa nie może zawierać katalogu `data`, CSV, SQLite, modeli ani historii.

## Progi gotowości

- co najmniej 300 nowych rozliczonych obserwacji,
- pokrycie closing odds co najmniej 80%,
- pokrycie rozliczeń co najmniej 95%,
- następnie walk-forward i live shadow; promocja pozostaje ręczna.
