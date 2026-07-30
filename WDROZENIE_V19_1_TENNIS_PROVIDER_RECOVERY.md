# v19.1 — naprawa źródeł tenisa

Hotfix usuwa burzę ponowień Sportradar i dodaje bezpieczny fallback danych
z The Odds API. Nie zmienia aktywnego modelu żadnej dyscypliny.

## Zachowanie

- `401/403`: adapter zatrzymuje dalsze zapytania Sportradar w danym cyklu;
- `404/410/422`: data lub endpoint są oznaczane jako niedostępne, a nie jako
  awaria jakości danych;
- `429`: cykl chroni limit i nie wykonuje kolejnych kosztownych prób;
- harmonogram oraz wyniki ATP/WTA mogą zostać zapisane z The Odds API;
- kurs jest dopuszczany dopiero po konsensusie co najmniej dwóch bukmacherów;
- wszystkie rekordy fallback otrzymują stabilne identyfikatory i trafiają
  wyłącznie do `/data/tennis`.

## Zmienne opcjonalne

```text
BETBOT_TENNIS_SPORTRADAR_MAX_SCHEDULE_DAYS=7
BETBOT_TENNIS_ODDS_SCORES_DAYS=3
```

Domyślne wartości są bezpieczne i nie wymagają dodawania zmiennych na Railway.

## Oczekiwany log

```text
TENNIS_SHADOW_START
TENNIS_SHADOW_CYCLE
HEARTBEAT ... tennis_shadow=True
```

Status `HEALTHY_ODDS_FALLBACK` oznacza, że Sportradar był ograniczony, ale
zbieranie danych jest kontynuowane przez źródło awaryjne. Fallback nie omija
bramek jakości, nie uruchamia realnych zakładów i nie promuje modelu bez
pozytywnej walidacji walk-forward.
