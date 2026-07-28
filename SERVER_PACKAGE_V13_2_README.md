# BETBOT V13.2 — SINGLE-BOOK SHADOW CLASS C

## Cel

Pakiet pozwala siatkówce i piłce ręcznej zachowywać kompletne kursy z jednego
bukmachera jako obserwacje klasy C. Dane te są przeznaczone wyłącznie do
monitoringu shadow i budowania historii rynku.

## Gwarancje bezpieczeństwa

- minimum dwóch bukmacherów nadal obowiązuje dla typów;
- dane klasy C nie są dopuszczane do treningu ani promocji modelu;
- dane klasy C nie są używane jako kurs zamknięcia do obliczeń CLV;
- dane klasy C nie obniżają współczynnika jakości próbki A/B;
- automatyczna promocja na podstawie pojedynczego bukmachera jest zablokowana;
- pakiet nie zawiera plików `/data`, historii, baz SQLite ani modeli;
- piłka nożna nie jest modyfikowana.

## Nowe pola audytowe

- `market_quality_tier=C_SINGLE_BOOK_SHADOW`
- `shadow_observation_only=true`
- `training_eligible=false`
- `pick_eligible=false`
- `promotion_eligible=false`
- `single_book_shadow_observed`
- `single_book_shadow_saved`
- `single_book_training_admitted=0`
- `single_book_picks_created=0`
- `single_book_promotion_allowed=false`

## Wdrożenie

Wgraj zawartość ZIP do katalogu głównego repozytorium, zachowując strukturę
folderów, a następnie wykonaj zwykły redeploy. Nie są wymagane nowe zmienne
Railway.

## Kontrola po wdrożeniu

W logach `VOLLEYBALL_SHADOW_CYCLE` oraz `HANDBALL_SHADOW_CYCLE` sprawdź nowe
liczniki `single_book_*`. Wartość `single_book_shadow_observed > 0` oznacza
zapis obserwacji klasy C. Wartości `single_book_training_admitted`,
`single_book_picks_created` muszą pozostać równe zero, a
`single_book_promotion_allowed` musi pozostać `false`.

