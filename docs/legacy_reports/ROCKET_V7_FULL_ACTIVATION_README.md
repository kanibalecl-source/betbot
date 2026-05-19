# ROCKET V7 FULL ACTIVATION

Ta paczka zastępuje puste/stubowe moduły V6 realnymi modułami wykonawczymi.

## Uruchomienie testu aktywacji

```bash
python v7_activation.py
```

Po udanym starcie powstanie:

```text
data/enterprise/v7_activation_report.json
```

## Co jest teraz realnie zaimplementowane

- `ml_training_pipeline.py` — realny online logistic ML, zapis wag, inferencja, raport treningu.
- `auto_retraining_runtime.py` — runtime retrainingu z harmonogramem, stanem i raportami.
- `multi_source_ingestion.py` — API-Football + lokalne snapshoty providerów + cache + merge.
- `source_quality_engine.py` — scoring jakości danych: completeness, freshness, consistency, coverage.
- `gpu_optimizer.py` — szybkie vectorized Monte Carlo, automatycznie NumPy albo CuPy/CUDA.
- `walk_forward_lab.py` — rolling walk-forward validation z ROI, hit rate, Brier, drawdown.
- `advanced_calibration_analytics.py` — Brier, ECE, reliability bins, persistent calibration offsets.
- `rocket_v7_enterprise_orchestrator.py` — jeden pipeline łączący V7.

## Ważne

Pełne działanie multi-source zależy od kluczy API oraz jakości danych historycznych.
Jeżeli nie ma `API_KEY`, system nie pada — zwraca status źródła i działa dalej na lokalnych snapshotach/manualnych danych.
