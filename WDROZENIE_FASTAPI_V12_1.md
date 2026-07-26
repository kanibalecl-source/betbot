# BetBot V12.1 — osobny serwis FastAPI

## Najważniejsza zasada

FastAPI uruchamiamy jako **drugi serwis Railway** z tego samego repozytorium.
Nie zmieniamy komendy startowej istniejącego serwisu BetBot. Główny serwis
nadal uruchamia `app_launcher.py` i zachowuje dashboard, harmonogram,
rozliczanie oraz autonomiczne uczenie.

## Pliki

- `Dockerfile.api` — odseparowany obraz API;
- `railway-api.toml` — konfiguracja budowy i healthchecku API;
- `scripts/start_fastapi.sh` — bezpieczny start Uvicorn;
- `app/` — aplikacja FastAPI;
- `FASTAPI_RAILWAY_ENV.example` — lista wymaganych zmiennych bez sekretów.

## Utworzenie drugiego serwisu

1. W Railway utwórz nowy serwis z tego samego repozytorium i tej samej gałęzi.
2. Nazwij go np. `betbot-api`.
3. W ustawieniach nowego serwisu ustaw ścieżkę pliku konfiguracyjnego:
   `/railway-api.toml`.
4. Nie podłączaj do niego woluminu głównego bota.
5. Dodaj zmienne:

```text
ENVIRONMENT=production
API_KEY=<unikalny sekret minimum 32 znaki>
BETTING_ENABLED=false
REALTIME_ENABLED=false
API_WORKERS=1
```

6. Wygeneruj domenę publiczną dla `betbot-api`.
7. Healthcheck ma wskazywać `/api/v1/health`.

Jeżeli Railway nie korzysta ze wskazanego pliku konfiguracyjnego, ustaw
`Dockerfile Path` ręcznie na `Dockerfile.api`. Komendy startowej nie trzeba
nadpisywać, ponieważ znajduje się w tym Dockerfile.

## Weryfikacja

Publiczny test zdrowia:

```text
GET https://<domena-api>/api/v1/health
```

Oczekiwany status: `200`.

Predykcja wymaga nagłówka `x-api-key`:

```powershell
$headers = @{ "x-api-key" = "<API_KEY>" }
$body = @{
  home_team = "Alpha FC"
  away_team = "Beta FC"
  market = "Over 2.5"
  odds = 2.10
  probability = 0.55
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "https://<domena-api>/api/v1/predict" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $body
```

Bez prawidłowego klucza endpoint predykcji musi zwrócić `401`.

## Bezpieczeństwo i dane

- instalacja nie aktywuje obstawiania;
- API nie podmienia aktywnego modelu;
- API nie otrzymuje woluminu z historią produkcyjną;
- paczka nie zawiera klucza API ani innych sekretów;
- dokumentacja `/docs` pozostaje wyłączona w produkcji;
- `REALTIME_ENABLED=false` zapobiega tworzeniu niezależnych snapshotów i bazy
  zdarzeń w drugim serwisie;
- API może wykonywać predykcje na podstawie danych przekazanych w żądaniu.

Jeżeli w przyszłości API ma czytać pełny stan produkcyjny, należy wdrożyć
wspólny PostgreSQL/Redis albo kontrolowane wewnętrzne API. Nie należy
udostępniać równocześnie tego samego pliku SQLite dwóm serwisom.
