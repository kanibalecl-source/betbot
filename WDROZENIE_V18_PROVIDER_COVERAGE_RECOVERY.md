# Wdrożenie V18 — Provider Coverage Recovery

Wgraj pliki z paczki do katalogu głównego repozytorium, zachowując strukturę
folderów, a następnie wykonaj zwykły redeploy usługi `betbot`.

## Zmienne Railway

Dla obecnego klucza pozostaw:

```text
BETBOT_SPORTRADAR_ODDS_API_VARIANT=legacy_rowt1
BETBOT_HANDBALL_LOOKAHEAD_DAYS=7
BETBOT_HANDBALL_MAX_ODDS_REQUESTS_PER_CYCLE=80
BETBOT_HANDBALL_EMPTY_ODDS_RETRY_HOURS=6
```

Nie ustawiaj `prematch_v2`, dopóki produkt Sportradar Odds Comparison Prematch
v2 nie zostanie aktywowany dla klucza. Test uprawnień obecnego klucza zwrócił
HTTP 403.

## Oczekiwane logi

Po wyczerpaniu limitu Sportradar:

```text
runtime_version=1.1
status=LIMITED_BY_PROVIDER
odds_rate_limited=true
retry_storm_prevented=true
```

To oznacza, że pobieranie zdarzeń nadal działa, a zapytania o kursy zostały
bezpiecznie zatrzymane do następnego cyklu.

Dla piłki ręcznej:

```text
runtime_version=12.1
lookahead_days=7
maximum_odds_requests_per_cycle=80
empty_odds_retry_hours=6
```

`odds_empty_responses` może być większe od zera, jeśli dostawca nie wystawia
kursów dla danej ligi. Takie mecze nie tworzą typów i nie trafiają do uczenia.

## Ochrona danych

Wdrożenie nie zawiera ani nie usuwa danych z `/data`. Server Data Guard powinien
utworzyć backup przed uruchomieniem nowych procesów.
