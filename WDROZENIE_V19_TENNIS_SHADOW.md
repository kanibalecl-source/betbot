# Wdrożenie v19 — Tennis Shadow

Po wgraniu paczki kod pozostaje bezpiecznie wyłączony. Panel **Tenis** jest
widoczny i oczekuje na pierwszy cykl.

## Wymagane źródła

1. Aktywny produkt **Sportradar Tennis API v3** oraz istniejący
   `SPORTRADAR_API_KEY`.
2. Klucz The Odds API zapisany jako `THE_ODDS_API_KEY` albo istniejący
   `ODDS_API_KEY`.

## Aktywacja na Railway

Ustaw:

```text
BETBOT_TENNIS_ENABLED=1
BETBOT_TENNIS_SHADOW_ONLY=1
BETBOT_TENNIS_POLL_MINUTES=240
BETBOT_TENNIS_AUTONOMOUS_GOVERNOR_ENABLED=1
```

Następnie wykonaj redeploy. Oczekiwany log:

```text
TENNIS_SHADOW_START
TENNIS_SHADOW_CYCLE
```

## Bramki jakości

- minimum 1500 rozliczonych meczów;
- minimum 300 meczów na każdej używanej głównej nawierzchni;
- minimum 4 pozytywne foldy walk-forward;
- dodatnia poprawa Brier i log-loss;
- co najmniej 100 nowych wyników między walidacjami;
- kurs dopuszczany dopiero z co najmniej dwóch niezależnych bukmacherów.

Pozytywna walidacja może promować tylko challenger shadow tenisa. Nigdy nie
uruchamia zakładów i nie zmienia aktywnych modeli pozostałych dyscyplin.
