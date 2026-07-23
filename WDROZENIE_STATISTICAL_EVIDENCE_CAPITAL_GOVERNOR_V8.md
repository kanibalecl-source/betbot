# Statistical Evidence Scorecard v8 + Staged Capital Governor v8

## Co zostało wdrożone

- score 0–10 oparty na rozliczonych próbkach, integralności, kalibracji,
  dodatnim CLV z 95% CI, walk-forward, live shadow i Data Quality Guardian;
- status `STATISTICAL_EDGE_CONFIRMED` wyłącznie po przejściu wszystkich bramek;
- osobna gotowość kapitałowa wymaga również dodatniego dolnego 95% CI dla yield;
- etapy `SHADOW -> PAPER -> CANARY -> LIMITED -> CONTROLLED`;
- natychmiastowy powrót do bezpieczniejszego etapu po utracie dowodów;
- Execution Guard wymaga świeżej zgody Capital Governora i stosuje niższy z
  limitów globalnych oraz limitów bieżącego etapu.

## Bezpieczny stan po wdrożeniu

Nie ustawiaj `BETTING_ENABLED=true`. Pozostaw:

```text
BETTING_ENABLED=false
BETBOT_CAPITAL_REAL_ENABLED=0
```

W tym stanie v8 liczy dowody, pokazuje wynik w Analityce i może dojść najwyżej
do etapu PAPER. Nie wysyła zakładów, nie zmienia aktywnego modelu, historii ani
ustawień środowiska.

## Pliki na woluminie

Raporty po pierwszym cyklu powstaną wyłącznie w `/data/quality_retraining/`:

- `statistical_evidence_scorecard_v8.json`
- `staged_capital_governor_v8.json`
- `staged_capital_governor_events_v8.jsonl`

Paczka wdrożeniowa nie zawiera katalogu `data`, baz, CSV, modeli ani sekretów.
Realne etapy są dodatkowo blokowane, dopóki adapter wykonawczy nie zapisze
świeżego `capital_runtime_evidence_v8.json` i operator osobno nie włączy obu
przełączników kapitału. Raport runtime musi zawierać aktualne pole `observed_at`;
domyślnie traci ważność po 7200 sekundach.
