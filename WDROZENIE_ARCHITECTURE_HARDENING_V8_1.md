# Architecture Hardening v8.1

## Zakres

1. `quality_governance_v8` jest jedynym właścicielem kontrolowanego retreningu.
   Stary `auto_retraining_loop.py` pozostaje w repozytorium dla zgodności, ale
   launcher go nie uruchamia.
2. `app_launcher.py` nie uruchamia procesów podczas importu i może być bezpiecznie
   testowany.
3. `settings_v81.py` typuje oraz waliduje kluczową konfigurację przed backupem i
   startem procesów. Sprzeczne ustawienia kapitału blokują start.
4. `/data/runtime_health.json` zawiera wersjonowany stan wszystkich procesów,
   fingerprint niesekretnej konfiguracji, właściciela retreningu i stan egzekucji.
5. `/data/quality_retraining/quality_governance_health_v81.json` zapisuje wynik
   ostatniego cyklu, czas wykonania, Scorecard oraz etap kapitału.
6. Scorecard i Capital Governor mają jawne identyfikatory wersji schematu.

## Bezpieczne ustawienia po wdrożeniu

```text
BETTING_ENABLED=false
BETBOT_CAPITAL_REAL_ENABLED=0
BETBOT_AUTONOMOUS_PROMOTION_ENABLED=0
BETBOT_HEARTBEAT_SECONDS=30
```

Brak nowych zmiennych w Railway nie blokuje wdrożenia — używane są powyższe
bezpieczne wartości domyślne.

## Ochrona danych

- paczka nie zawiera `data`, CSV, SQLite, historii, modeli ani sekretów;
- pliki runtime są zapisywane atomowo wyłącznie na podłączonym woluminie `/data`;
- zmiana nie modyfikuje algorytmów typowania ani aktywnego modelu;
- przed startem nadal wykonywany jest backup wdrożeniowy;
- pierwszy start może przez około 2 minuty oczekiwać na wykonanie backupu.

## Oczekiwany log

```text
APP LAUNCHER v8.1 START
CONFIG VALID schema=betbot.runtime_settings.v8.1
START quality_governance_v8
QUALITY GOVERNANCE v8.1 START
HEARTBEAT v8.1 | ... quality_governance_v8=True ...
```

W heartbeat nie może występować osobny proces `retraining`.
