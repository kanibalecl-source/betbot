GPTTAB - gotowa zakładka ANALIZA GPT

CO JEST W PACZCE:
- app.py z minimalnym dopisaniem route'ów ANALIZA GPT
- gpt_analysis_tab.py
- gpt_match_value_engine.py
- ako_coupon_builder.py
- gpt_ako_runtime.py
- templates/gpt_analysis.html
- static/js/gpt_analysis.js
- static/css/gpt_analysis.css

JAK WGRAC:
1. Rozpakuj ZIP na serwerze w katalogu projektu bota.
2. Pozwól nadpisać app.py.
3. Upewnij się, że masz w .env:
   OPENAI_API_KEY=sk-proj-...
4. Zainstaluj zależności:
   pip install -r requirements.txt
   pip install openai
5. Uruchom bota jak dotychczas.
6. Wejdź w przeglądarce:
   /gpt-analysis

UWAGA:
- Zakładka nie zmienia istniejących silników bota.
- Czyta typy z data/auto_all_picks.csv, data/live_matches.csv, auto_all_picks.csv albo live_matches.csv.
- Wyniki zapisuje do data/gpt_analysis_report.json.
- Cache analiz jest w cache/gpt_analysis.

MODEL:
Domyślnie używa GPT_ANALYSIS_MODEL=gpt-4.1-mini.
Możesz dodać do .env np.:
GPT_ANALYSIS_MODEL=gpt-5.5

Jeśli OpenAI nie ma dostępu do wybranego modelu, ustaw model dostępny na Twoim koncie.
