FINALNA POPRAWKA GPT DO STREAMLIT DASHBOARD

Co naprawia:
1. Przywraca oryginalny wyglad bota z dashboard_streamlit.py.audit_backup.
2. Dodaje prawdziwa zakladke: 🤖 GPT.
3. Nie usuwa ani nie zmienia zakladek LIVE / PREMATCH / AI / ANALYTICS / HISTORY / RANKING / ALERTS.
4. Zakladka GPT korzysta z gpt_match_value_engine.py.
5. GPT analizuje mecze znalezione przez bota w:
   - data/auto_all_picks.csv
   - data/live_matches.csv
   - auto_all_picks.csv
   - live_matches.csv
6. Wyniki zapisuje do:
   - data/gpt_analysis_report.json
7. Buduje kupony AKO przez ako_coupon_builder.py.

Jak wgrac:
1. Wgraj wszystkie pliki z tej paczki do glownego folderu bota.
2. Nadpisz obecne pliki.
3. Upewnij sie, ze w Railway Variables masz OPENAI_API_KEY.
4. Zrob deploy/restart.
5. Otworz dashboard i wejdz w zakladke 🤖 GPT.
6. Kliknij: Uruchom analize GPT.

Bezpieczenstwo:
- Nie dodawaj klucza OpenAI do kodu.
- Trzymaj go tylko w Railway Variables.
- Ta paczka nie zawiera .env ani kluczy.

Sprawdzone technicznie:
- dashboard_streamlit.py kompiluje sie poprawnie.
- gpt_match_value_engine.py kompiluje sie poprawnie.
- ako_coupon_builder.py kompiluje sie poprawnie.
