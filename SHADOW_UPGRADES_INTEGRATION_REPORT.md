# Shadow Upgrades Integration Report

## Tryb integracji

Wdrożono wyłącznie **shadow mode**.

Oznacza to, że nowe moduły:

- liczą dodatkową ocenę jakości typu równolegle,
- zapisują wynik do `data/shadow_upgrade_events.jsonl`,
- nie zmieniają `BET/PASS`,
- nie zmieniają `stake_pct`,
- nie zmieniają `probability`,
- nie zmieniają `edge`,
- nie zmieniają `confidence`,
- nie zmieniają `risk_level`,
- nie zmieniają UI,
- nie zmieniają schematów API,
- nie zmieniają endpointów.

## Dodane elementy

Dodano katalog:

`app/services/safe_upgrades/`

Zawiera:

- `shadow_mode.py` — pasywna warstwa diagnostyczna,
- `__init__.py` — plik pakietu.

## Zmieniony plik

Zmieniono tylko:

`app/services/prediction_service.py`

Zmiana polega na dodaniu bezpiecznego wywołania shadow mode po wyliczeniu obecnego wyniku predykcji.

## Zabezpieczenie

Cały shadow mode działa w bloku `try/except`.

Jeżeli nowy moduł zwróci błąd, obecna predykcja działa dalej bez zmiany odpowiedzi.

## Cel

Ten etap pozwala zebrać dane do backtestu i walidacji bez ryzyka zmiany działania bota.

Dopiero po porównaniu wyników shadow score z realnymi rezultatami można zdecydować, czy włączyć wpływ nowych modułów na decyzję `BET/PASS`.
