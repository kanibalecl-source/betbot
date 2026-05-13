ULTRA FINAL AUDIT

WALIDACJA SKŁADNI:
{
  "bot.py": "OK",
  "data_api.py": "OK",
  "model_goals.py": "OK",
  "dashboard_streamlit.py": "OK",
  "scheduler_engine.py": "OK",
  "stage_a_value_layer.py": "OK",
  "stage_b_model_layer.py": "OK",
  "stage_c_meta_layer.py": "OK",
  "auto_optimizer_v2.py": "OK"
}

CHECKLISTA INTEGRACJI:
{
  "bot_target_markets": true,
  "bot_double_1x": true,
  "bot_btts_no": true,
  "bot_over_4_5": true,
  "bot_under_4_5": true,
  "bot_stage_a": true,
  "bot_stage_b": true,
  "bot_stage_c": true,
  "bot_ranking": true,
  "data_api_double_chance": true,
  "data_api_total_lines": true,
  "model_double": true,
  "model_over_under_all": true,
  "dashboard_ai_tab": true,
  "dashboard_native_badge": true,
  "config_all_markets": true
}

NAPRAWIONE OBSZARY:
1. data_api.py:
   - dodano Double Chance: DOUBLE_1X, DOUBLE_X2, DOUBLE_12
   - dodano pełne Over/Under 0.5–4.5
   - dodano BTTS Yes/No
   - loguje ODDS MARKETS

2. model_goals.py:
   - model liczy 1X / X2 / 12
   - model liczy BTTS Yes/No
   - model liczy Over/Under 0.5, 1.5, 2.5, 3.5, 4.5

3. bot.py:
   - target markets tylko:
     DOUBLE_1X, DOUBLE_X2, DOUBLE_12,
     BTTS_YES, BTTS_NO,
     OVER_0.5–OVER_4.5,
     UNDER_0.5–UNDER_4.5
   - Stage A/B/C zachowane
   - ranking AI zachowany
   - nie wycina wszystkich typów błędnym string-matchingiem
   - margin nie odrzuca double chance błędnym klasycznym marginesem

4. dashboard_streamlit.py:
   - zachowana obecna kolorystyka
   - tabela PREMATCH zostaje
   - AI przeniesione do osobnej zakładki 🧠 AI
   - badge są natywne Streamlit, bez ryzykownego HTML:
     🟣 ULTRA ELITE
     🟢 TOP PICK
     🟩 BEST PICK
     🟨 VALUE PICK
     ⚪ STANDARD

WDROŻENIE:
1. Rozpakuj ZIP.
2. Nadpisz pliki w repo GitHub.
3. Commit:
   git add .
   git commit -m "ultra final market and AI fix"
   git push
4. Railway zrobi deploy automatycznie.

PO DEPLOY W LOGACH SPRAWDŹ:
- bot.py compile nie powinien sypać błędów
- ODDS MARKETS: [...]
- BOT EXECUTED | CODE=0
- typów zapisanych > 0, jeśli API zwróci kursy i filtry EV/risk przepuszczą typy
