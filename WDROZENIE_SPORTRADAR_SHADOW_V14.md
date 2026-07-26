# Sportradar Shadow Adapters v14

## Cel

Pakiet uruchamia niezależny kolektor danych Sportradar dla piłki nożnej,
siatkówki i piłki ręcznej. Dane są zapisywane wyłącznie w osobnym magazynie:

`/data/sportradar_shadow/sportradar_shadow.sqlite3`

Warstwa nie publikuje typów, nie zasila treningu, nie zmienia aktywnego modelu
i nie może uruchomić gry realnym kapitałem.

## Bezpieczne wdrożenie

1. Wgraj pliki z paczki, zachowując ich katalogi.
2. Nie usuwaj ani nie zastępuj katalogu `/data`.
3. Zaczekaj na poprawne zakończenie redeploy.
4. Ustaw w Railway:

```text
BETBOT_SPORTRADAR_SHADOW_ENABLED=1
BETBOT_SPORTRADAR_SHADOW_ONLY=1
BETBOT_SPORTRADAR_ACCESS_LEVEL=trial
BETBOT_SPORTRADAR_LANGUAGE=en
BETBOT_SPORTRADAR_POLL_MINUTES=30
BETBOT_SPORTRADAR_LOOKBACK_DAYS=1
BETBOT_SPORTRADAR_LOOKAHEAD_DAYS=1
BETBOT_SPORTRADAR_TIMEOUT_SECONDS=20
BETBOT_SPORTRADAR_REQUEST_INTERVAL_SECONDS=1.1
BETBOT_SPORTRADAR_MAX_RETRIES=2
BETBOT_SPORTRADAR_ODDS_ENABLED=1
BETBOT_SPORTRADAR_ODDS_MAX_EVENTS_PER_CYCLE=6
```

`SPORTRADAR_API_KEY` musi pozostać sekretną zmienną Railway. Nie należy
wpisywać klucza do pliku, repozytorium ani paczki ZIP.

## Oczekiwane logi

Po restarcie powinny pojawić się:

```text
START sportradar_shadow: ... -m sportradar_shadow.runtime
SPORTRADAR_SHADOW_START
SPORTRADAR_SHADOW_CYCLE
```

Pierwszy cykl może mieć status `DEGRADED`, jeśli plan próbny nie obejmuje
któregoś produktu. Pozostałe źródła nadal są zbierane; niedostępna odpowiedź
nie jest wpuszczana do danych treningowych.

## Kryteria przejścia z shadow

Ta wersja celowo nie ma automatycznego przejścia do produkcji. Integracja może
być oceniona dopiero po zebraniu reprezentatywnych danych i sprawdzeniu:

- kompletności identyfikatorów wydarzeń i drużyn;
- zgodności czasu, statusów i wyników;
- świeżości oraz pokrycia kursów;
- zgodności kursów z dozwolonymi bukmacherami;
- poziomu odrzuceń i przyczyn kwarantanny;
- stabilności źródła w każdej dyscyplinie.

Do tego czasu `active_model_modified=false`,
`automatic_training_admission=false` oraz
`automatic_model_promotion_allowed=false`.
