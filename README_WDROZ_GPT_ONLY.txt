INSTRUKCJA WDROŻENIA — GPT ONLY

1. Rozpakuj gpt_only_upgrade.zip.
2. Wgraj na serwer tylko pliki z paczki do głównego katalogu aplikacji:
   - dashboard_streamlit.py
   - gpt_betting_assistant.py
   - persistent_storage.py
3. Nie usuwaj żadnych obecnych plików.
4. Nie zmieniaj .env.
5. Zrestartuj aplikację.

Po wdrożeniu sprawdź:
- zakładka 🤖 GPT CHAT istnieje,
- w środku są podzakładki:
  - 💬 LIVE CHAT
  - 📊 AI ANALYSIS
- stare GPT analysis nadal działa w 📊 AI ANALYSIS,
- pozostałe zakładki wyglądają tak samo jak przed wdrożeniem.
