WDROŻENIE:
1. Nadpisz pliki z paczki w repo GitHub.
2. Szczególnie:
   - bot.py
   - dashboard_streamlit.py
3. Commit:
   git add .
   git commit -m "odds 1-250 and best pick highlight"
   git push

CO ZMIENIONO:
- Bot zapisuje tylko typy z kursem 1.00–2.50.
- Dashboard pokazuje tylko typy z kursem 1.00–2.50.
- Dodano ai_pick_score.
- Dodano best_pick / best_pick_label.
- Najlepsze typy są zielono oznaczone jako BEST PICK.
- Zachowana obecna kolorystyka i wygląd tabeli.
