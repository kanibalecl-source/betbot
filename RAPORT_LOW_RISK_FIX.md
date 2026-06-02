# LOW/RISK Fix

## Problem

Zakladka PREMATCH miala trzy tabele, ale scheduler uruchamial tylko glowny tryb bota. Pliki:

- `data/auto_low_picks.csv`
- `data/auto_risk_picks.csv`

nie byly generowane.

## Poprawka

Dodano tryby pracy `bot.py`:

- `--mode main` -> `data/auto_all_picks.csv`
- `--mode low` -> `data/auto_low_picks.csv`
- `--mode risk` -> `data/auto_risk_picks.csv`

Scheduler lokalny i produkcyjny uruchamia teraz w jednym cyklu:

1. PREMATCH
2. PREMATCH LOW
3. PREMATCH RISK

## Dodatkowa roznica LOW/RISK

Glowny Prematch zostaje bez zmian.

LOW i RISK maja wlaczony szerszy skan lig przez:

```text
KANIBAL_INCLUDE_ALL_LEAGUES=1
```

Dzieki temu w dniach, gdy top ligi nie maja meczow, LOW/RISK nadal moga znalezc kandydatow w szerszym kalendarzu.

## Logika

Nie zmieniono matematyki typowania. Dodano tylko osobne tryby uruchamiania, osobne pliki wyjsciowe i szerszy skan lig dla LOW/RISK.

