# BetBot Pro 10/10 Upgrade

Ta paczka dodaje produkcyjny szkielet systemu bez niszczenia starej logiki predykcyjnej.

Najważniejsze wejście: `app/main.py`  
Endpointy: `/api/v1/health`, `/api/v1/predict`  
Instrukcja: `docs/UPGRADE_10_10.md`

## Szybki start

```bash
cp .env.example .env
make install
make test
make run
```
