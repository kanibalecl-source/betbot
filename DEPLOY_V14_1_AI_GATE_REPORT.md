# BetBot V14.1 — raport bramek AI

## Zakres

- Nie zmienia progów, punktacji ani zasad publikowania typów.
- Nie zmienia aktywnego modelu i nie uruchamia promocji modelu.
- Zachowuje tryb `fail-closed`.
- Dodaje zbiorczy wpis `AI-SELF-LEARNING | GATE REPORT` do logów każdego
  cyklu AI.
- Raport podaje liczbę kandydatów, zaakceptowanych i odrzuconych rekordów.
- Powody odrzuceń są grupowane według kodu i etapu:
  `identity`, `validation`, `selection` albo `ranking`.
- Plik `data/ai_runtime_debug_main.json` zawiera szczegóły każdego odrzucenia:
  identyfikatory meczu i typu, rynek, status bukmachera, integralność rynku,
  konsensus, status bramki jakości, wiek kursu oraz wartości progowe.
- Raport nie zapisuje kluczy API, haseł ani innych sekretów.

## Bezpieczeństwo danych

Paczka nie zawiera katalogu `data`, historii, rozliczeń, modeli, baz danych,
plików środowiskowych ani sekretów. Wdrożenie nie usuwa i nie nadpisuje danych
zgromadzonych na woluminie.

## Oczekiwany log

Po cyklu pojawią się dwa wpisy:

```text
[AI-SELF-LEARNING] AI OK | picks=... | mode=... | settled=...
[AI-SELF-LEARNING] GATE REPORT | {"accepted": ..., "candidates": ...,
  "rejected": ..., "rejection_reasons": {...}, "fail_closed": true}
```

Jeżeli `picks=0`, drugi wpis pokaże dokładne kody powodów odrzucenia.
