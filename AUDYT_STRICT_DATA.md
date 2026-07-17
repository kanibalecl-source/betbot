# Audyt prawdziwych danych, historii, rozliczeń i uczenia

## Naprawione ścieżki aktywnego launchera

- Prematch nie tworzy xG, gdy API nie zwróciło zakończonych meczów obu drużyn. Usunięto stałe `1.2`, średnią ligi `1.35` i ręczną przewagę gospodarza `1.08`.
- Tempo, presja, momentum i posiadanie nie są uzupełniane wartościami neutralnymi. Korekta LIVE działa tylko przy komplecie oznaczonych danych LIVE.
- AI nie wymyśla już innego rynku. Może wyłącznie uszeregować istniejący pick mający fixture ID, rynek, prawdziwy kurs, stawkę, confidence i edge/EV.
- AI nie podmienia kursu, rynku, stawki, edge ani EV. Każdy rekord zawiera `data_provenance` i liczbę rozliczonych próbek.
- Nauka odrzuca `OPEN`, `NEW` i `PENDING`. Źródłem jest wyłącznie kanoniczny eksport `results_history.csv` z bazy SQLite.
- Pipeline ML nie używa `auto_all_picks.csv` jako zbioru etykiet i nie podstawia xG/formy/tempa. Stary, potencjalnie skażony model jest zachowany jako `*_legacy_unverified_v1.json`, a nie kasowany.
- Rozliczenie zapisuje wynik bramkowy, źródło `API_FOOTBALL` i czas rozliczenia. Rekord zamknięty nie jest rozliczany ponownie.
- Brak rzeczywistej stawki albo kursu blokuje rozliczenie finansowe zamiast przyjęcia stawki `1`.
- Usunięto klucze API wpisane w kodzie. Klucze są pobierane wyłącznie ze zmiennych środowiskowych.
- Analiza GPT aktualnych newsów nie ma fallbacku bez wyszukiwania WWW; awaria daje `SKIP`, nie pozorną analizę.

## Trwałość

Wszystkie aktywne bazy, historia append-only, picki, LIVE i modele uczenia korzystają ze wspólnego `DATA_DIR`. Na serwerze brak Volume blokuje start. Lokalnie używany jest osobny `local_data`.

Historia append-only zapisuje JSONL i CSV. Błędy zapisu nie są już bezgłośnie ignorowane. Istniejące rekordy `CLOSED` pozostają niezmienne, a migracja nie zastępuje niepustych plików docelowych.

## Świadome ograniczenie

Bot nadal jest modelem probabilistycznym: prawdopodobieństwa są obliczeniami na podstawie realnych wyników i kursów, nie faktami. Zmiana polega na usunięciu zmyślonych danych wejściowych i jednoznacznym odrzucaniu braków. Kod badawczy i nieuruchamiane przez `app_launcher.py` eksperymenty nie są źródłem picków produkcyjnych.
