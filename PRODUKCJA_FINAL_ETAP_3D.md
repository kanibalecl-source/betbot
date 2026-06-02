# Etap 3D - Produkcja Final

Ta paczka scala Etapy 3A, 3B i 3C:

- profesjonalna struktura modu??w `betbot/*`,
- append-only historia w `data/history`,
- wydzielony serwis danych dashboardu,
- zachowana dotychczasowa logika i entrypointy.

## Zasada dalszego rozwoju

- UI zmieniamy w `dashboard_streamlit.py` i `betbot/dashboard/*`.
- Historia i trwa?o?? danych w `betbot/storage/*`, `agi_storage.py`, `persistence_runtime.py`.
- Prematch i filtry w `bot.py`, docelowo `betbot/prematch/*`.
- Live w `live_pipeline_runtime.py`, docelowo `betbot/live/*`.
- Manual betting w `manual_betting.py`, docelowo `betbot/manual/*`.
- GPT w plikach `gpt_*`, docelowo `betbot/gpt/*`.

## Dane produkcyjne

Paczka nie zawiera produkcyjnej historii ani `.env`. Nie nadpisuj `/data` na serwerze.
