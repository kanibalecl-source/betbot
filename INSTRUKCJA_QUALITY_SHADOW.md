# Lokalny test algorytmów jakości

## Bezpieczeństwo

Warstwa działa tylko po ustawieniu BETBOT_QUALITY_SHADOW=1. Domyślnie jest
wyłączona. Nie zmienia prawdopodobieństwa, rekomendacji, ryzyka ani stawki.
Wyniki porównawcze zapisuje lokalnie do data/shadow_upgrade_events.jsonl.

Nie wykonuje wdrożenia na Railway ani zapisu na serwer.

## Uruchomienie

1. Uruchom wcześniej INSTALL_LOCAL_WINDOWS.bat, jeśli nie ma .venv.
2. Skonfiguruj lokalny .env.local.
3. Uruchom START_LOCAL_QUALITY_SHADOW.bat.
4. Dashboard będzie dostępny pod http://127.0.0.1:8503.
5. Zbieraj wyniki shadow bez zmiany bieżących typów.

## Aktywne algorytmy

- Dixon–Coles z korektą niskich wyników;
- usuwanie marży metodą power;
- ensemble z wagami możliwymi do nauczenia;
- beta calibration;
- niepewność wynikająca z rozbieżności modeli i jakości danych;
- konserwatywna dolna granica prawdopodobieństwa;
- decyzja shadow ACCEPT, REVIEW albo PASS.
- detekcja driftu PSI z poziomami STABLE, WARNING i ALERT;
- portfelowy fractional Kelly z limitem pojedynczego typu, całego portfela
  i skorelowanych typów z tego samego meczu.

## Uczenie wag bez przecieku

Plik data/quality_training.csv musi zawierać chronologiczne rekordy:

current_probability,dixon_coles_probability,market_probability,target

target przyjmuje 1 dla wygranej i 0 dla przegranej. Następnie uruchom
TRAIN_QUALITY_SHADOW.bat. Dane są dzielone kolejno na trening, kalibrację i
końcowy holdout. Holdout nie uczestniczy w uczeniu.

Nie wolno używać w cechach informacji poznanych po wystawieniu typu, np.
closing odds lub CLV, jeśli nie były dostępne w chwili predykcji.
