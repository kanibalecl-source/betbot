# Football Model Council v17

## Zakres

Rada modeli działa wyłącznie dla piłki nożnej i zawiera:

1. bieżący model produkcyjny jako jedynego aktywnego Championa,
2. niezależny model Poissona,
3. model Dixon–Coles,
4. bivariate Poisson,
5. CatBoost uczony na cechach dostępnych przed meczem,
6. hierarchiczny model empirical Bayes z częściowym poolingiem ligi i drużyn.

## Granica bezpieczeństwa

- `challengers_have_decision_authority=false`
- żaden wynik rady nie zmienia `prawd_final`, typu, stawki ani publikacji,
- kurs bukmachera nie jest cechą żadnego modelu rady,
- CatBoost jest używany tylko po utworzeniu artefaktu i walidacji shadow,
- aktywny model nie jest automatycznie podmieniany.

## Automatyczne uczenie

Kontrolowany retrening tworzy stan:

`data/football_model_council/shadow_state.json`

Dopiero po minimum 500 poprawnie rozliczonych rekordach piłkarskich:

- dobierany jest wspólny składnik bivariate Poisson,
- uczone są priory ligowe i drużynowe,
- CatBoost przechodzi chronologiczny podział train / early stopping / test,
- wagi diagnostycznego konsensusu są uczone bez kursów bukmachera.

Brak odpowiedniej liczby danych kończy się statusem
`WAITING_FOR_SETTLED_DATA` i nie powoduje zmiany aktywnego modelu.

## Pola audytowe

Każdy nowy typ piłkarski zapisuje m.in.:

- `football_council_models_json`
- `football_council_consensus`
- `football_council_disagreement`
- `football_council_gate`
- `football_council_decision_authority`

## Wdrożenie

Wgrać wyłącznie pliki z paczki serwerowej, bez katalogu `data`.
Po wdrożeniu wykonać redeploy. Nie trzeba ręcznie uruchamiać treningu:
rada zostanie obsłużona przez istniejący kontrolowany cykl retreningu.

