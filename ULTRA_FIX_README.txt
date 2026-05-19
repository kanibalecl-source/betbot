ULTRA FIX

Naprawiono:
- błędny start FastAPI zamiast Streamlit
- konflikty Railway start command
- usunięto uszkodzone pliki python ze składnią ERROR
- usunięto __pycache__
- wymuszono Python 3.11
- wymuszono Streamlit startup

WDROŻENIE:
1. Wgraj CAŁĄ paczkę.
2. Railway -> Settings -> Variables:
   usuń stary START COMMAND jeśli istnieje.
3. Redeploy.
4. Aplikacja uruchomi dashboard_streamlit.py
