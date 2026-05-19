KANIBAL BOT — BEZPIECZNY UPGRADE GPT + HISTORIA + STORAGE

Co zmienia ta paczka:
1. NIE zmienia wygladu dashboardu poza dodaniem zakladki 🤖 GPT.
2. NIE rusza logiki typowania ani obecnych silnikow AI.
3. Dodaje osobny modul GPT: gpt_streamlit_panel.py.
4. Dodaje storage historii typow: agi_storage.py.
5. Dodaje runtime synchronizacji i rozliczania: persistence_runtime.py.
6. Dodaje result updater dla typow z fixture_id: result_updater_unified.py.
7. Dashboard HISTORIA moze czytac dane rowniez ze storage.
8. app_launcher uruchamia persistence runtime obok schedulera, settlementu, retrainingu i dashboardu.

Wazne o trwalosci danych na Railway:
- Lokalny SQLite dziala od razu, ale Railway moze kasowac lokalne pliki po redeployu.
- Aby dane NIGDY nie ginely, dodaj Railway Volume albo PostgreSQL/Supabase i pozniej mozna podlaczyc DATABASE_URL.
- Ta paczka zabezpiecza pipeline zapisu, ale fizyczna trwalosc zalezy od storage dostepnego na serwerze.

Zmienne srodowiskowe:
OPENAI_API_KEY — wymagane do prawdziwej analizy GPT.
GPT_ANALYSIS_MODEL — opcjonalnie, domyslnie gpt-4.1-mini.
APISPORTS_KEY / FOOTBALL_API_KEY / API_FOOTBALL_KEY — wymagane do automatycznego rozliczania wynikow po fixture_id.

Jak wdrozyc:
1. Wgraj wszystkie pliki z paczki do glownego folderu bota.
2. Nadpisz istniejace pliki.
3. Railway zrobi deploy.
4. Po uruchomieniu sprawdz zakladki: LIVE, PREMATCH, AI, ANALYTICS, HISTORY, RANKING, ALERTS, SETTINGS, 🤖 GPT.
5. W GPT kliknij "Uruchom analizę GPT".

Co sprawdzono:
- py_compile dla plikow Python w paczce.
- Dashboard zachowuje require_login().
- Zakladka GPT jest dodana jako dziewiata zakladka, bez usuwania pozostalych.
