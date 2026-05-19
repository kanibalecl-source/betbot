WDROŻENIE NA SERWERZE — WERSJA 24/7

Polecana opcja:
- VPS Ubuntu
- Docker + Docker Compose
- folder data/ montowany jako wolumen, żeby baza i CSV nie znikały po restarcie

Kroki:
1. Skopiuj cały folder bota na serwer.
2. Uzupełnij klucze w .env albo secrets_config.py, jeśli nie są już w Twoim data_api.py.
3. Uruchom:
   docker compose up -d --build

Panel:
   http://IP_SERWERA:8000

Logi:
   docker logs betbot-web
   docker logs betbot-loop
   docker logs betbot-settle

Restart:
   docker compose restart

Stop:
   docker compose down

Backup najważniejszych danych:
- data/bot_tracker.sqlite3
- data/auto_all_picks.csv
- data/auto_all_picks_history.csv
- reports/
