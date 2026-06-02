# Raport: wdrozenie zakladki CZAT GPT

## Zakres

Zakladka `CZAT GPT` zostala przebudowana na trzy niezalezne profile:

- `Prematch`
- `Low`
- `Risk`

Kazdy profil ma osobne:

- metryki kontekstu,
- `Czat analityczny`,
- `Analiza AI/GPT`,
- klucze formularzy Streamlit,
- raport GPT zapisany do osobnego pliku.

## Pliki raportow GPT

Nowe analizy GPT zapisuja sie osobno:

- `data/gpt_analysis_report_prematch.json`
- `data/gpt_analysis_report_low.json`
- `data/gpt_analysis_report_risk.json`

Dla kompatybilnosci profil `Prematch` aktualizuje rowniez stary plik:

- `data/gpt_analysis_report.json`

## Zrodla danych

Profile GPT korzystaja z tych samych zrodel, co reszta panelu:

- `Prematch` -> `auto_all_picks.csv`
- `Low` -> `auto_low_picks.csv`
- `Risk` -> `auto_risk_picks.csv`

## Bezpieczenstwo logiki

Zmiana nie modyfikuje logiki typowania bota.

GPT:

- czyta dane aktywnego profilu,
- analizuje dane,
- zapisuje odpowiedzi i raporty GPT,
- nie kasuje historii,
- nie nadpisuje typow,
- nie zmienia filtrow bota.

## Pliki zmienione

- `dashboard_streamlit.py`
- `gpt_betting_assistant.py`
- `gpt_streamlit_panel.py`
- `gpt_match_value_engine.py`
