ULTRA PORT FIX

BŁĄD:
STREAMLIT_SERVER_PORT miał wartość dosłownie "$PORT"
zamiast liczby.

Railway automatycznie ustawia PORT.
Streamlit także automatycznie go odczytuje.

Problem powodowało ręczne:
--server.port=$PORT

NAPRAWA:
Usunięto całkowicie:
--server.port=$PORT

NOWY START:
streamlit run dashboard_streamlit.py --server.address=0.0.0.0

WDROŻENIE:
1. Wgraj Procfile i railway.json do ROOT projektu.
2. Railway -> Variables:
   usuń:
   STREAMLIT_SERVER_PORT
   jeśli istnieje.
3. Railway -> Settings:
   usuń stary Start Command jeśli istnieje.
4. Redeploy.

To naprawia:
- Invalid value for '--server.port'
- Application failed to respond
- restart loop
- failed healthcheck
