# ULTRA UPGRADE V3 — niezależny silnik obliczeniowy

Ten upgrade dodaje warstwę V3, której zasada jest prosta:

**bukmacher nie tworzy predykcji. Bukmacher służy tylko do porównania kursu, EV, edge i CLV.**

## Nowe moduły

- `probability_utils.py` — jeden standard prawdopodobieństw 0.00–1.00, EV, edge, fair odds, no-vig.
- `feature_builder_v3.py` — buduje dane wejściowe i xG bez kursów bukmachera.
- `core_predictive_engine_v3.py` — niezależny model Poisson/score matrix dla 1X2, double chance, BTTS, over/under.
- `market_comparison_engine_v3.py` — jedyne miejsce, gdzie wolno użyć kursu bukmachera.
- `adaptive_learning_engine_v3.py` — automatyczna kalibracja po rozliczonych wynikach.
- `settlement_engine_v3.py` — rozliczanie picków po wyniku meczu.
- `full_auto_pipeline_v3.py` — pełny pipeline: dane → model → kalibracja → porównanie z bukmacherem → decyzja.

## Jak używać

```python
from full_auto_pipeline_v3 import FullAutoPipelineV3

pipeline = FullAutoPipelineV3()
result = pipeline.analyze_pick(match, market_code="OVER_2_5", bookmaker_odds=1.95)
print(result)
```

## Najważniejsza zmiana

Stary kierunek:

```text
kurs bukmachera → model → final probability
```

Nowy kierunek:

```text
dane meczowe → własny model → model probability → porównanie z bukmacherem → EV/value
```

## Co dalej, aby wejść na najwyższy poziom

1. Zbierać prawdziwe xG, strzały, SOT, big chances, dangerous attacks, składy, kontuzje i pogodę.
2. Zapisywać każdy pick przed meczem z `model_probability`, `odds`, `stake`, `market`, `league`, `fixture_id`.
3. Po meczu używać `settlement_engine_v3.py` do rozliczania.
4. Uruchamiać `AdaptiveLearningEngineV3().build_calibration_table()` po każdej serii rozliczeń.
5. Trzymać kurs bukmachera wyłącznie w `market_comparison_engine_v3.py`.
