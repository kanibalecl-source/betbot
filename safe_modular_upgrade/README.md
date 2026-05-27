# Safe Modular Upgrade for BetBot

Ten katalog jest celowo odseparowany od obecnego runtime bota.

## Główna zasada

Moduły tutaj:
- nie są importowane przez `bot.py`,
- nie zmieniają dashboardu,
- nie zmieniają API,
- nie zmieniają schedulerów,
- nie zmieniają obecnej logiki BET/PASS,
- nie zmieniają stakingu,
- nie nadpisują danych produkcyjnych.

## Jak działają

Każdy moduł działa jako osobny analizator uruchamiany ręcznie lub przez osobny proces.
Domyślnie zapisuje wyniki wyłącznie do:

`data/safe_modular_upgrade/`

## Uruchomienie pełnego audytu offline

```bash
python safe_modular_upgrade/run_all.py
```

## Uruchomienie pojedynczego modułu

```bash
python safe_modular_upgrade/modules/confidence_audit.py
python safe_modular_upgrade/modules/league_profile_audit.py
python safe_modular_upgrade/modules/clv_audit.py
python safe_modular_upgrade/modules/market_movement_audit.py
python safe_modular_upgrade/modules/risk_audit.py
python safe_modular_upgrade/modules/self_learning_audit.py
```

## Ważne

To jest upgrade diagnostyczno-analityczny, a nie runtime integration.
Dzięki temu nie ma wpływu na działanie obecnej wersji bota.
