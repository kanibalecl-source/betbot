FINAL MASTER ENGINE INTEGRATION — ETAPY 1–10

Ta paczka dodaje jeden centralny pipeline:
API / dane meczu
→ Tempo
→ Confidence calibration
→ xG / fair odds
→ Bayesian LIVE
→ Ensemble
→ EV
→ Market movement
→ Filter optimizer
→ Bankroll
→ CSV
→ Dashboard

PLIKI:
- master_prediction_engine.py
- prediction_pipeline_integration.py
- live_engine.py
- data/history.csv
- data/clv_history.csv
- data/results_history.csv
- README_MASTER_INTEGRATION.txt

WAŻNE:
To jest bezpieczny overlay. Nie kasuje Twojego dashboardu ani schedulera.

WDROŻENIE:
1. Rozpakuj ZIP.
2. Wgraj pliki do głównego folderu bota.
3. Jeśli masz już live_engine.py, nadpisz go.
4. Zrób commit i push do Railway:
   git add .
   git commit -m "master engine integration"
   git push

JAK SPRAWDZIĆ:
W logach szukaj:
- MASTER PIPELINE SAVED
- ACTIVE LIVE MATCHES
- PICKS COUNT

CSV:
- data/auto_all_picks.csv
- data/live_matches.csv

Dashboard:
LIVE i PREMATCH powinny czytać te pliki jak wcześniej.

JEŚLI BOT NADAL NIE KORZYSTA:
Znaczy, że Twój główny plik nie używa klasy LiveEngine.
Wtedy w miejscu gdzie bot ma listę `matches`, dodaj:

from prediction_pipeline_integration import process_and_save_matches
process_and_save_matches(matches)

To jest główna linia podpięcia całego pipeline.
