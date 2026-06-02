# Etap 3 - Architektura Produkcyjna

Celem Etapu 3 jest uporz?dkowanie bota w modu?y bez zmiany logiki typowania.

## Granice modu??w

- `betbot/config` - konfiguracja, profile filtr?w, zmienne ?rodowiskowe.
- `betbot/core` - wsp?lne typy, walidacja, helpery.
- `betbot/providers` - integracje z API-Football, The Odds API i OpenAI.
- `betbot/prematch` - typowanie prematch, filtry, EV, risk, stake.
- `betbot/live` - live pipeline.
- `betbot/settlement` - rozliczanie wynik?w.
- `betbot/storage` - trwa?y zapis historii, append-only, SQLite/CSV/JSONL.
- `betbot/learning` - AI self-learning, feature store, retraining.
- `betbot/manual` - Moje Zak?ady, single i AKO.
- `betbot/gpt` - GPT chat, GPT analysis, GPT AKO.
- `betbot/dashboard` - panel www, UI, widoki i style.
- `betbot/runtime` - launcher, scheduler, procesy produkcyjne.

## Zasada zachowania logiki

Root-level entrypointy (`app_launcher.py`, `scheduler_engine.py`, `bot.py`, `dashboard_streamlit.py`) zostaj?, aby wdro?enie dzia?a?o tak jak wcze?niej. Nowa struktura jest warstw? produkcyjn? i miejscem dalszej migracji.
