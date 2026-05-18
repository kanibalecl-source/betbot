# GPT-web AKO Integration

## Co zostało dodane

Nowa warstwa działa tak:

1. Bot dalej znajduje mecze i proponowane typy w `data/auto_all_picks.csv` albo `data/live_matches.csv`.
2. `gpt_ako_runtime.py` bierze najlepszych kandydatów.
3. `gpt_match_value_engine.py` wysyła każdy mecz + typ + kurs do OpenAI Responses API z narzędziem `web_search`.
4. GPT sam sprawdza aktualny kontekst publiczny: forma, kontuzje, składy, styl gry, terminarz, motywacja, atmosfera/news itd.
5. Każdy zakład dostaje ocenę JSON: play / skip, confidence, value, risk, powody, minusy, brakujące informacje.
6. `ako_coupon_builder.py` układa kupony:
   - `SAFE_AKO`
   - `BALANCED_AKO`
   - `AGGRESSIVE_AKO`

## Pliki wyjściowe

Po uruchomieniu cyklu powstaną:

- `data/gpt_match_evaluations.csv` — ocena każdego meczu i typu
- `data/gpt_ako_coupons.json` — gotowe kupony AKO
- `data/gpt_ako_report.md` — czytelny raport
- `data/gpt_match_value_cache.json` — cache, żeby nie płacić kilka razy za tę samą analizę tego samego dnia

## Konfiguracja

W `.env` dodaj:

```env
OPENAI_API_KEY=twój_klucz
OPENAI_MATCH_MODEL=gpt-4.1-mini
GPT_MAX_MATCHES=20
GPT_MATCH_SLEEP_SECONDS=0.3
```

W `requirements.txt` dodano:

```txt
openai
```

## Uruchomienie

Najpierw normalnie wygeneruj typy bota:

```bash
python bot.py
```

Potem uruchom analizę GPT + kupony AKO:

```bash
python gpt_ako_runtime.py
```

Albo z Pythona:

```python
from gpt_ako_runtime import run_gpt_ako_cycle

result = run_gpt_ako_cycle(limit=20)
print(result)
```

## Ważne

To nie jest system gwarantujący zysk. GPT ma być filtrem jakościowym i risk managerem, który odrzuca mecze z niepewnym kontekstem lub brakiem value. Najlepsza praktyka to: bot robi prefilter, GPT ocenia kontekst, a AKO grać niższą stawką niż single.
