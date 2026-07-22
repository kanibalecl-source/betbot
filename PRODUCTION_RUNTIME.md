# Kanoniczny runtime produkcyjny

Jedynym kanonicznym procesem webowym jest `start.sh`:

1. `server_start_guard.py` potwierdza zewnętrzny persistent storage i tworzy backup przypisany do deploymentu.
2. Dopiero po pozytywnej bramce uruchamiany jest `dashboard_streamlit.py` na porcie `PORT`.
3. Railway używa `nixpacks.toml -> sh start.sh`; Docker używa dokładnie tego samego `start.sh`.

`app_launcher.py`, `railway-live.json` i pozostałe launchery są warstwami historycznymi i nie są kanoniczną ścieżką wdrożenia panelu.

## Bezwzględne zmienne produkcyjne

- `PERSISTENT_DATA_DIR=/data`
- `KANIBAL_REQUIRE_PERSISTENT_STORAGE=1`
- `BETTING_ENABLED=false`
- `API_KEY` — co najmniej 32 losowe znaki, jeżeli uruchamiane jest API FastAPI
- `BETBOT_ADMIN_USERNAME`
- `BETBOT_ADMIN_PASSWORD_HASH` — Argon2id

Brak storage lub backupu blokuje start. Brak bezpiecznego klucza blokuje API staging/production. System nie zawiera adaptera automatycznie składającego zakłady.
