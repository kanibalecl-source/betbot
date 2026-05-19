# BetBot Pro — pakiet dużego upgrade'u 10/10

## Co zostało naprawione

1. **Chaos repozytorium** — usunięto cache, pyc, backupi i prywatny `.env` z paczki.
2. **Brak produkcyjnego API** — dodano FastAPI w `app/main.py` z wersjonowanym `/api/v1`.
3. **Brak walidacji danych** — dodano Pydantic schema dla predykcji, healthchecków i wejść bettingowych.
4. **Brak bezpieczeństwa API** — dodano opcjonalny `X-API-Key` przez `API_KEY`.
5. **Brak centralnej konfiguracji** — dodano `app/core/config.py` i `.env.example`.
6. **Brak structured logging baseline** — dodano centralne ustawienie logowania.
7. **Brak CI/CD** — dodano GitHub Actions.
8. **Brak testów smoke/API** — dodano testy w `tests/test_api.py`.
9. **Brak nowoczesnego deploymentu** — dodano nowy Dockerfile, docker-compose i Procfile.
10. **Ryzyko utraty starej logiki** — nowy `PredictionService` mostkuje się ze starym `MasterPredictionEngine`.

## Jak uruchomić

```bash
cp .env.example .env
make install
make test
make run
```

API:

```bash
curl http://localhost:8080/api/v1/health
```

Predykcja:

```bash
curl -X POST http://localhost:8080/api/v1/predict \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: change-me-long-random-secret' \
  -d '{"home_team":"Alpha FC","away_team":"Beta FC","market":"Over 2.5","odds":2.1,"probability":0.55}'
```

## Kolejny poziom, aby realnie utrzymać 10/10

- PostgreSQL zamiast SQLite w produkcji.
- Redis + kolejki dla live feedów.
- Backtesting walk-forward jako obowiązkowy gate przed aktywacją modelu.
- CLV tracking jako główny KPI jakości modelu.
- Monitoring: Prometheus/Grafana albo OpenTelemetry.
- Oddzielić `legacy/` od nowego `app/` po przejściu testów regresji.

## Zasada jakości

Nie dodawać kolejnych engine'ów bez testu: ROI, CLV, kalibracja, leakage check, stabilność na out-of-sample.
