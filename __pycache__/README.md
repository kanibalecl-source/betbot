# FINAL PATCH PACK — BetBot Winning Version

To jest końcowa, poprawiona paczka lokalnego bota z najważniejszymi łatami:
- mocniejsza selekcja
- twardy filtr `true_edge >= 0.05`
- ograniczenie do top lig
- zakres kursów 1.60–3.50
- timing engine
- odds quality / value gap
- opening / current / closing odds
- CLV log
- settlement wyników
- live watchlist
- portfolio limity
- prosty dashboard Streamlit

## Instalacja
python -m venv venv

Windows:
venv\Scripts\activate

Mac / Linux:
source venv/bin/activate

pip install -r requirements.txt

## Konfiguracja
Skopiuj `.env.example` do `.env` i wpisz klucze.

## Jednorazowe uruchomienie
python main.py once

## Praca w pętli
python main.py loop

## Dashboard
streamlit run dashboard.py
