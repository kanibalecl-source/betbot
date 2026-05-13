# ROCKET UPGRADE V5 — ML + Multi-source + Live + Auto-retraining

Ten etap dodaje profesjonalną warstwę `rocket_v5/`. Najważniejsza zasada:

```text
Bukmacher NIE jest wejściem modelu. Kurs jest używany dopiero na końcu do EV/edge.
```

## Co dodano

- `rocket_v5/multi_source.py` — hub do scalania danych z wielu źródeł i audyt jakości danych.
- `rocket_v5/advanced_xg.py` — advanced xG: shot/event xG, fallback na agregaty, korekty taktyczne/pogodowe/składowe.
- `rocket_v5/monte_carlo.py` — symulacja Monte Carlo dla rynków 1X2, overów, BTTS, double chance.
- `rocket_v5/ml_engine.py` — lekki ML online bez ciężkich zależności; gotowy pod zamianę na LightGBM/XGBoost.
- `rocket_v5/meta_model.py` — meta-model łączący symulację, ML, kalibrację, live signal.
- `rocket_v5/live_intelligence.py` — live intelligence: kartki, momentum, presja, game state.
- `rocket_v5/auto_retraining.py` — nocny retraining z pliku settlement.
- `rocket_v5/market_only_comparison.py` — bukmacher tylko do porównania value.
- `rocket_v5/rocket_pipeline.py` — pełny pipeline V5.
- `rocket_v5/cli.py` — CLI do testów.

## Test uruchomienia

```bash
python -m rocket_v5.cli providers
```

Analiza meczu z pliku JSON:

```bash
python -m rocket_v5.cli analyze --input sample_match_v5.json --market OVER_2_5 --odds 1.95 --runs 50000
```

Retraining:

```bash
python -m rocket_v5.cli retrain
```

## Docelowe źródła danych

Rekomendowane podpięcia:

1. API-Football — terminarz, wyniki, składy, statystyki.
2. Understat / dostawca xG — shot-based xG.
3. FotMob / SofaScore — live momentum, strzały, lineups, events.
4. Football-Data — backup wyników.
5. Open-Meteo — pogoda.
6. OddsAPI — wyłącznie kursy do końcowego EV/edge, nigdy do model probability.
7. Transfermarkt / injury feed — kontuzje i wartość/skład.

## Najważniejszy flow

```text
multi-source data
→ data quality audit
→ advanced xG
→ Monte Carlo
→ ML adjustment
→ live intelligence
→ meta-model AI
→ final probability
→ bookmaker comparison only for EV/edge
→ settlement
→ auto-retraining
```

## Format minimalnego wejścia

```json
{
  "match_id": "demo_001",
  "home_team": "Team A",
  "away_team": "Team B",
  "league": "Demo League",
  "kickoff": "2026-05-12T20:00:00",
  "home_xg": 1.65,
  "away_xg": 1.10,
  "home_shots": 14,
  "away_shots": 9,
  "home_sot": 5,
  "away_sot": 3,
  "home_big_chances": 2,
  "away_big_chances": 1,
  "tactical_openness": 1.08,
  "home_lineup_strength": 1.03,
  "away_lineup_strength": 0.96
}
```
