# Autonomous Learning Governor v7 — bezpieczne wdrożenie

## Co robi v7

1. Co 24 godziny (lub po wymaganej liczbie nowych rozliczeń) tworzy kandydatów
   z okien 100%, 75% i 50% historii.
2. Wybiera najlepszy wariant na chronologicznym holdoucie.
3. Ponownie sprawdza go w expanding walk-forward bez przecieku przyszłości.
4. Zbiera przyszłe wyniki w live shadow i wymaga kompletu bramek jakości.
5. Przechodzi etapy evidence-canary 10/25/50/100 na nowych rozliczeniach.
6. Dopiero wtedy może atomowo awansować challengera.
7. Zachowuje poprzedniego championa i po 3 kolejnych alarmach Guardian wykonuje rollback.

## Zmienne Railway

Pierwsze uruchomienie kontrolne:

```text
BETBOT_AUTONOMOUS_GOVERNOR_ENABLED=1
BETBOT_AUTONOMOUS_PROMOTION_ENABLED=0
BETBOT_AUTONOMOUS_ROLLBACK_ENABLED=1
BETBOT_GOVERNOR_ROLLBACK_FAILURES=3
BETBOT_QUALITY_CANDIDATE_WINDOWS=1.0,0.75,0.50
```

Po potwierdzeniu heartbeat `quality_governor_v7=true` i braku błędów:

```text
BETBOT_AUTONOMOUS_PROMOTION_ENABLED=1
```

Ta zmiana nie oznacza natychmiastowej podmiany. Odblokowuje ją dopiero po
spełnieniu wszystkich bramek i ukończeniu canary.

## Pliki trwałe tworzone wyłącznie na Volume

- `/data/quality_retraining/autonomous_governor_v7.json`
- `/data/quality_retraining/autonomous_governor_events.jsonl`
- `/data/quality_retraining/candidates/*.json`
- `/data/quality_retraining/registry/champion_before_auto_*.json`
- `/data/quality_retraining/registry/promotion_audit.jsonl`

Nie wolno kopiować lokalnego katalogu `data` na serwer.
