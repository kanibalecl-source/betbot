# CHAT GPT AUTO ANALIZA - raport wdrożenia

## Co zmieniono

- Usunięto podzakładkę `Czat analityczny` z głównej zakładki `Czat GPT`.
- Po wejściu w `Czat GPT` użytkownik widzi od razu profile:
  - Prematch
  - Low
  - Risk
- W każdym profilu uruchamia się od razu automatyczna `Analiza GPT`.
- Prompt ekspercki został ukryty w kodzie w pliku `gpt_prompts.py`.
- Analiza GPT wykonuje się dla typów wygenerowanych przez bota i zapisuje wyniki osobno dla każdego profilu.
- Cache analiz jest osobny dla Prematch, Low i Risk, żeby profile nie mieszały wyników.
- Domyślny model analizy to `gpt-5.2-chat-latest`.
- Jeśli model nie będzie dostępny, kod schodzi awaryjnie do `gpt-4.1-mini`.

## Zasada bezpieczeństwa

Moduł GPT nie zmienia logiki bota, nie nadpisuje głównych typów i nie kasuje historii.

GPT zapisuje tylko swoje analizy:

- `gpt_analysis_report_prematch.json`
- `gpt_analysis_report_low.json`
- `gpt_analysis_report_risk.json`
- pamięć SQLite / AGI storage, jeśli jest dostępna

## Zmienne środowiskowe

Wymagane do pełnej analizy:

```text
OPENAI_API_KEY
```

Opcjonalnie:

```text
GPT_ANALYSIS_MODEL=gpt-5.2-chat-latest
GPT_ANALYSIS_FALLBACK_MODEL=gpt-4.1-mini
GPT_AUTO_ANALYSIS_LIMIT=50
```

## Test lokalny

1. Rozpakuj ZIP do osobnego folderu.
2. Nie wrzucaj go od razu na serwer.
3. Uruchom lokalnie:

```text
INSTALL_LOCAL_WINDOWS.bat
START_LOCAL_FULL.bat
```

4. Wejdź w zakładkę `Czat GPT`.
5. Sprawdź profile `Prematch`, `Low`, `Risk`.
6. Jeśli nie ma `OPENAI_API_KEY`, panel pokaże ostrzeżenie i nie wykona pełnej analizy GPT.

## Najważniejsze

Ten ZIP jest wersją testową zakładki GPT. Lokalny test nie zmienia serwera Railway, dopóki nie wykonasz commit/push/redeploy.
