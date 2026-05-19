FINAL RUN FIX

NAPRAWIONO:
- Railway uruchamiał z błędnym STREAMLIT_SERVER_PORT="$PORT".
- Dodano start.sh, który usuwa błędny env STREAMLIT_SERVER_PORT.
- Port jest teraz liczony bezpiecznie:
  - Railway PORT -> używany automatycznie
  - brak PORT -> fallback 8501
- Procfile wskazuje tylko: sh start.sh
- railway.json wskazuje tylko: sh start.sh
- nixpacks.toml wskazuje tylko: sh start.sh
- usunięto __pycache__
- ustawiono Python 3.11.9
- dodano .streamlit/config.toml bez wymuszania portu.

KONTROLA:
dashboard_streamlit.py syntax OK: True


WDROŻENIE NA RAILWAY:
1. Wgraj całą paczkę.
2. Railway -> Variables:
   USUŃ zmienną STREAMLIT_SERVER_PORT jeśli istnieje.
   Nie ustawiaj jej ręcznie.
3. Railway -> Settings -> Deploy:
   usuń ręczny Start Command jeśli masz tam stary gunicorn albo streamlit z $PORT.
4. Redeploy.

PO POPRAWNYM WDROŻENIU:
- nie zobaczysz już JSON FastAPI,
- nie będzie błędu "$PORT is not a valid integer",
- uruchomi się dashboard_streamlit.py.
