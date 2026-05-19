RAILWAY STREAMLIT FIX

Problem:
Railway nadal uruchamia FastAPI:
gunicorn app.main:app

dlatego widzisz:
{"ok":true,"service":"BetBot Pro","version":"10.0.0"}

Naprawa:
1. Wgraj Procfile i railway.json do ROOT projektu.
2. Commit + redeploy.
3. W Railway:
   Settings -> Deploy
   usuń stary Start Command jeśli istnieje.
4. Redeploy aplikację.

Po restarcie uruchomi się:
streamlit run dashboard_streamlit.py
