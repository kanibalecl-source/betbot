# BetBot FastAPI Quality Platform v12.2

## Cel

Oddzielona usługa FastAPI udostępnia kontrolowany, chroniony kluczem API
odczyt typów, stanu jakości i modeli dla football, volleyball oraz handball.
PostgreSQL pełni rolę kopii prezentacyjnej. Autorytatywna historia na Volume
pozostaje bez zmian.

## Bezpieczna kolejność aktywacji

1. Wgraj pliki paczki do repozytorium i poczekaj na poprawny deploy obu usług.
2. Dodaj w Railway PostgreSQL bez publicznego endpointu.
3. W `betbot-api` ustaw referencję `DATABASE_URL` do PostgreSQL oraz:
   `API_SYNC_ENABLED=1`.
4. W głównej usłudze ustaw:
   `BETBOT_FASTAPI_URL=https://betbot-api-production.up.railway.app`,
   `BETBOT_FASTAPI_API_KEY` jako referencję do tego samego sekretu,
   `BETBOT_FASTAPI_SYNC_ENABLED=1`,
   `BETBOT_FASTAPI_SYNC_MINUTES=30`.
5. Pozostaw `BETBOT_FASTAPI_READ_ENABLED=0` podczas testu zgodności.
6. Sprawdź `/api/v1/monitoring` i porównaj liczbę/treść typów z panelem.
7. Dopiero po zgodności ustaw `BETBOT_FASTAPI_READ_ENABLED=1`.

## Gwarancje

- synchronizator tylko czyta Volume;
- błędne rekordy nie trafiają do tabeli typów;
- odrzucenia są liczone w audycie;
- API nie uruchamia zakładów ani treningu;
- awaria API lub PostgreSQL powoduje fallback panelu do lokalnego CSV;
- aktywne modele, historia i pliki rozliczeń nie są modyfikowane.

## Endpointy

- `GET /api/v1/picks?discipline=football&page=1&page_size=10`
- `GET /api/v1/sports/{discipline}/summary`
- `GET /api/v1/quality/status?discipline=football`
- `GET /api/v1/models/status?discipline=football`
- `GET /api/v1/data-quality/report?discipline=football`
- `GET /api/v1/monitoring`
- `POST /api/v1/internal/sync` — tylko wewnętrzny synchronizator

Wszystkie powyższe endpointy poza `/api/v1/health` wymagają `x-api-key`.
