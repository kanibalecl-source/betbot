# ULTRA REALTIME ENTERPRISE VERSION

## Co dodano

Ten upgrade dodaje warstwę realtime enterprise bez usuwania obecnego AI stacku.

### Nowe endpointy

- `GET /api/v1/realtime/health`
- `GET /api/v1/realtime/snapshot`
- `POST /api/v1/realtime/publish`
- `WS /api/v1/realtime/ws`
- `GET /api/v1/realtime/sse`

### Nowe moduły

- `app/realtime/event_bus.py`
- `app/realtime/cache.py`
- `app/realtime/storage.py`
- `app/realtime/routes.py`
- `app/realtime/worker.py`

### Co to daje

- realtime event bus,
- WebSocket live stream,
- SSE stream,
- snapshot API,
- pamięć eventów w SQLite,
- cache live danych,
- background worker publikujący stan `live_matches.csv` i `ai_picks.csv`,
- baza pod Redis/PostgreSQL bez wymuszania tych usług od razu.

## Wdrożenie

1. Wgraj paczkę na serwer.
2. Upewnij się, że startujesz FastAPI przez Procfile:
   `web: gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --workers 2 --timeout 60`
3. Zrestartuj deploy.
4. Sprawdź:
   `/api/v1/realtime/health`
5. Podłącz frontend/Streamlit do:
   `/api/v1/realtime/snapshot`
   albo websocket:
   `/api/v1/realtime/ws`

## Opcjonalne zmienne ENV

- `REALTIME_ENABLED=true`
- `REALTIME_TICK_SECONDS=1.0`
- `REALTIME_CACHE_TTL_SECONDS=30`
- `REALTIME_MAX_EVENTS=500`
- `REDIS_URL=...` przyszłościowo
- `POSTGRES_DSN=...` przyszłościowo

## Ważne

To nie kasuje starej logiki. Dodaje warstwę realtime obok obecnego bota.
