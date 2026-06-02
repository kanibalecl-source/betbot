# RAPORT AI LOW/RISK FIX

## Co naprawiono

- AI nie korzysta juz tylko z `data/auto_all_picks.csv`.
- Dodano trzy niezalezne tryby AI:
  - `main` -> `data/ai_picks.csv`
  - `low` -> `data/ai_low_picks.csv`
  - `risk` -> `data/ai_risk_picks.csv`
- Scheduler lokalny i produkcyjny uruchamia teraz kolejno:
  - Prematch / Prematch LOW / Prematch RISK
  - AI / AI LOW / AI RISK
- Zakladka AI pokazuje trzy osobne tabele:
  - AI
  - AI LOW
  - AI RISK
- GPT Chat dostaje polaczony kontekst ze wszystkich trzech tabel AI.
- Historia append-only zostala rozszerzona o `ai_low_picks` i `ai_risk_picks`.

## Czego nie zmieniono

- Nie zmieniono zasad stawiania zakladow.
- Nie zmieniono historii rozliczen.
- Nie dodano polaczenia z kontem bukmachera.
- Nie naruszono glownego pliku `.env` ani danych serwerowych.

## Jak sprawdzic w logach

Po uruchomieniu pelnego trybu lokalnego powinny pojawic sie linie:

```text
START LOCAL PREMATCH BOT
START LOCAL PREMATCH LOW BOT
START LOCAL PREMATCH RISK BOT
AI SELF-LEARNING LOOP OK
AI LOW SELF-LEARNING LOOP OK
AI RISK SELF-LEARNING LOOP OK
```

Jesli nadal jest 0 typow, trzeba patrzec na statystyki odrzucen w logach bota: `league_not_top`, `no_odds`, `no_xg`, `odds_range`, `edge_ev`, `filter_rejected`.
