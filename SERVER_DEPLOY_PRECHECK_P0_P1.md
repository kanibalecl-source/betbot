# Precheck wdrożenia P0/P1

## Przed redeployem

1. Nie usuwaj ani nie zastępuj Railway Volume. `PERSISTENT_DATA_DIR` musi wskazywać `/data`.
2. Pozostaw `BETTING_ENABLED=false`.
3. Ustaw `BETBOT_ADMIN_USERNAME` na nazwę administratora.
4. Ustaw `BETBOT_ADMIN_PASSWORD_HASH` na hash Argon2id. Hash można wygenerować po instalacji zależności poleceniem:

   `python setup_secure_admin.py`

5. Jeżeli uruchamiane jest API FastAPI, ustaw losowy `API_KEY` długości minimum 32 znaków.
6. Nie ustawiaj `BETBOT_SERVER_BACKUP_REUSE_HOURS` powyżej `0`; zalecane `BETBOT_SERVER_BACKUP_KEEP=5`.

## Zachowanie po wdrożeniu

- Start jest blokowany, gdy nie ma zewnętrznego persistent storage albo nie można utworzyć backupu deploymentu.
- Dawne hasła jawne i SHA-256 nie są akceptowane.
- Double chance nie jest automatycznie rekomendowane.
- Brak pełnego rynku jednego bukmachera kończy się `SKIP`.
- QUALITY SHADOW i Champion–Challenger nadal działają, ale nie promują modelu automatycznie.
- Żaden moduł w paczce nie usuwa ani nie zastępuje aktywnego modelu, historii lub danych treningowych.

## Smoke test po wdrożeniu

1. Sprawdź `SERVER DATA GUARD: BACKUP_CREATED` albo `ALREADY_BACKED_UP` dla tego samego deployment ID.
2. Sprawdź logowanie nowym administratorem Argon2id.
3. Potwierdź `BETTING_ENABLED=false`.
4. Sprawdź, że rekomendacje mają `bookmaker_used_in_own_odds=false` i `margin_bookmaker`.
5. Pozostaw system w shadow/paper do czasu zebrania wystarczającej liczby przyszłych rozliczeń.
