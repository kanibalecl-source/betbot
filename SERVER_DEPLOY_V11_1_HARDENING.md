# BetBot v11.1 — bezpieczne wdrożenie uszczelnienia automatyzacji

Paczka zawiera wyłącznie kod automatyzacji jakości. Nie zawiera katalogów
`data`, woluminu Railway, historii, modeli, plików użytkowników, sekretów ani
artefaktów uczenia.

## Działanie po wdrożeniu

- dane niespełniające reguł trafiają do kwarantanny;
- nieweryfikowalny dowód rozliczenia blokuje dopuszczenie rekordu;
- konflikt między źródłami usuwa zdarzenie ze zbioru treningowego;
- raz dopuszczony rekord nie może zostać po cichu zmieniony;
- brak zwalidowanej polityki działa fail-closed;
- retrening jest blokowany przy błędzie integralności lub krytycznym dryfie;
- walk-forward używa poprawnego czasu UTC, grup fixture oraz embargo;
- wariant kandydata jest wybierany na nietkniętym zbiorze czasowym;
- po promocji nowy model jest porównywany z kopią poprzedniego championa;
- potwierdzone pogorszenie uruchamia audytowalny rollback.

## Ważne ustawienia

W produkcji pozostawić:

```text
BETBOT_QUALITY_ALLOW_UNVERIFIED_CSV=0
BETBOT_QUALITY_EXPECTED_SPORT=football
BETBOT_QUALITY_MIN_DATA_QUALITY=0.65
BETBOT_QUALITY_WF_EMBARGO_HOURS=1
BETBOT_GOVERNOR_POST_PROMOTION_MIN_SAMPLES=100
BETBOT_AUTONOMOUS_ROLLBACK_ENABLED=1
```

Nie należy włączać `BETBOT_QUALITY_ALLOW_UNVERIFIED_CSV=1` na serwerze. Opcja
istnieje wyłącznie dla izolowanych testów starych plików.

## Pierwszy cykl po wdrożeniu

Starsze rekordy bez kompletnego snapshotu, wersji modelu lub zweryfikowanego
dowodu rozliczenia zostaną odrzucone. Jest to działanie zamierzone. Aktywny
model pozostanie bez zmian, dopóki nie zostanie zebrana wystarczająca liczba
nowych, w pełni zweryfikowanych rekordów.

Nowe artefakty są tworzone wyłącznie na woluminie:

- `quality_retraining/training_admission_ledger.sqlite3`
- `quality_retraining/quality_training.quarantine.jsonl`

Wdrożenie nie usuwa ani nie zastępuje istniejącej historii.
