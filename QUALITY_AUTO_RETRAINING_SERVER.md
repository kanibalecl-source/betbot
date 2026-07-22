# Kontrolowany automatyczny retrening QUALITY SHADOW

## Gwarancje bezpieczeństwa

- Proces czyta wyłącznie rozliczone CSV i SQLite w trybie read-only.
- Hashe źródeł są porównywane przed i po ekstrakcji.
- Retrening uruchamia się dopiero po zebraniu wymaganej liczby nowych rekordów.
- Każdy kandydat jest wersjonowany w `/data/quality_retraining/candidates`.
- Walidacja porównuje kandydata z aktywnym stanem i obecnym modelem na holdoucie.
- Proces nigdy nie zapisuje do `BETBOT_QUALITY_STATE` ani `quality_shadow_state.json`.
- Nawet kandydat z `POSITIVE_VALIDATION` wymaga ręcznej promocji operatora.

## Zmienne Railway

Po wdrożeniu kodu ustaw:

```text
BETBOT_QUALITY_RETRAIN_ENABLED=1
BETBOT_QUALITY_RETRAIN_CHECK_MINUTES=60
BETBOT_QUALITY_RETRAIN_MIN_HOURS=24
BETBOT_QUALITY_RETRAIN_MIN_NEW_ROWS=300
BETBOT_QUALITY_RETRAIN_MIN_BRIER_IMPROVEMENT=0.0002
BETBOT_QUALITY_RETRAIN_MIN_LOGLOSS_IMPROVEMENT=0.0002
```

Ustaw komendę startową usługi Railway na:

```text
python -u app_launcher_quality.py
```

Wrapper uruchamia niezmieniony `app_launcher.py` oraz oddzielny proces jakości.

## Pliki tworzone na Volume

Proces zapisuje tylko dane pochodne:

- `/data/quality_retraining/quality_training.latest.csv`;
- `/data/quality_retraining/quality_training.latest.meta.json`;
- `/data/quality_retraining/control_state.json`;
- `/data/quality_retraining/retraining_events.jsonl`;
- `/data/quality_retraining/quality_shadow_state.candidate.latest.json`;
- wersjonowane pliki w `/data/quality_retraining/candidates/`.

Aktywny `/data/quality_shadow_state.json` pozostaje nienaruszony.

## Ręczne sprawdzenie

Jednorazowa kontrola bez omijania progów:

```bash
python quality_auto_retraining.py --once
```

`--force` może wymusić utworzenie kandydata, ale nadal nie może go aktywować.

## Rollback

Ustaw `BETBOT_QUALITY_RETRAIN_ENABLED=0` albo przywróć komendę startową
`python -u app_launcher.py`, a następnie wykonaj redeploy. Nie usuwaj Volume.
Istniejące dane treningowe oraz kandydaci mogą pozostać jako historia audytowa.
