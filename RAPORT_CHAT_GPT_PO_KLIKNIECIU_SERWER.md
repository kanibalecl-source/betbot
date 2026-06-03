# Chat GPT po kliknięciu - paczka serwerowa

## Zakres zmiany

Ta wersja wdrożeniowa zawiera przebudowaną zakładkę `Czat GPT`.

Najważniejsze zmiany:

- prompt GPT jest ukryty w kodzie,
- prompt nie wykonuje się automatycznie dla wszystkich meczów,
- analiza uruchamia się tylko po kliknięciu przycisku `Analizuj GPT` przy konkretnym meczu,
- wynik zapisuje się osobno dla profili `Prematch`, `Low`, `Risk`,
- widok zakładki ma układ 1:1 według zaakceptowanego projektu:
  - jeden baner,
  - karty statusu,
  - przełączniki profili,
  - tabela po lewej,
  - szczegóły analizy po prawej,
  - propozycje AKO GPT na dole.

## Bezpieczeństwo danych

Paczka nie zawiera:

- `data`,
- `learning_data`,
- `.env`,
- `.env.local`,
- `.git`,
- `.venv`,
- `__pycache__`,
- cache GPT.

Dzięki temu wdrożenie nie powinno nadpisać historii ani danych uczących na Railway.

## Ważne

Ta paczka zachowuje wariant przetestowany lokalnie: logowanie jest wyłączone w `dashboard_streamlit.py`.

Jeżeli logowanie ma wrócić na serwer, należy ponownie włączyć `require_login()` przed wdrożeniem.
