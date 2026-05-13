# ROCKET UPGRADE V4 — autonomiczny silnik predykcyjny

Ten upgrade dodaje nową warstwę `rocket_v4`, która działa jak profesjonalny pipeline bettingowy:

```text
DANE -> DATA QUALITY -> FEATURE FACTORY -> xG ENGINE -> SIMULATION -> CALIBRATION -> MARKET COMPARISON -> RISK/STAKING
```

## Najważniejsza zasada

Bukmacher NIE jest używany do wyliczania prawdopodobieństwa. Kurs pojawia się dopiero na końcu w `MarketComparatorV4`, żeby policzyć:

- implied probability,
- fair odds,
- edge,
- EV,
- decyzję value/no value.

## Nowe moduły

- `rocket_v4/data_hub.py` — warstwa danych i ocena jakości danych.
- `rocket_v4/feature_factory.py` — budowa cech bez kursów.
- `rocket_v4/xg_engine.py` — xG ze strzałów albo z proxy feature modelu.
- `rocket_v4/simulation_engine.py` — rozkład wyników, over/under, BTTS, 1X2.
- `rocket_v4/learning_engine.py` — samokalibracja po rozliczonych typach.
- `rocket_v4/market_engine.py` — bukmacher tylko do porównania.
- `rocket_v4/risk_engine.py` — fractional Kelly + limity ryzyka.
- `rocket_v4/settlement.py` — automatyczne rozliczanie podstawowych rynków.
- `rocket_v4/backtest_engine.py` — backtest i aktualizacja nauki.
- `rocket_v4/orchestrator.py` — pełny pipeline.
- `rocket_v4_cli.py` — uruchamianie z terminala.

## Sposób użycia

```bash
python rocket_v4_cli.py providers
python rocket_v4_cli.py analyze --match-json sample_match.json --market OVER_2_5 --odds 1.95 --bankroll 1000
```

## Jakie źródła danych warto podpiąć

Priorytet 1:
- API-Football: mecze, wyniki, składy, eventy, statystyki.
- Źródło shot/xG: Understat, StatsBomb Open Data albo płatny dostawca z eventami strzałów.

Priorytet 2:
- Sofascore/FotMob/Flashscore jako uzupełnienie live momentum — tylko zgodnie z regulaminem.
- Open-Meteo do pogody.
- Football-Data jako backup fixtures/results.

Priorytet 3:
- kontuzje/składy, zawieszenia, terminarz, rest days, travel distance.

## Co robi bot po upgrade

1. Pobiera/łączy dane.
2. Ocenia jakość danych.
3. Liczy własne xG.
4. Symuluje rozkład wyników.
5. Wylicza prawdopodobieństwa rynków.
6. Kalibruje je na historii.
7. Dopiero wtedy porównuje z bukmacherem.
8. Jeżeli EV i edge są wystarczające, wylicza stake.
9. Po meczu settlement aktualizuje uczenie.

## Ważne

To jest potężna warstwa obliczeniowa, ale finalna jakość zależy od jakości danych. Największy skok da podpięcie prawdziwego event/shot feedu z xG albo danych pozwalających policzyć xG na poziomie strzału.
