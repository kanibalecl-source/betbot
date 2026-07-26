# BetBot Multisport Quality V12

## Cel

V12 podnosi jakość modeli w trzech całkowicie odseparowanych dyscyplinach:
piłce nożnej, siatkówce i piłce ręcznej. Zmiana nie nadpisuje historii,
aktywnych modeli ani ustawień Railway. Nowe warianty zaczynają jako kandydaci
i mogą awansować dopiero po własnym walk-forward oraz live shadow.

## Piłka nożna

- model prawdopodobieństwa nie wykorzystuje kursu bukmachera jako cechy;
- kurs jest używany wyłącznie po zamrożeniu predykcji jako benchmark no-vig,
  do pomiaru edge i CLV;
- niezależny challenger łączy dotychczasowy model, Dixon-Coles i formę;
- brakujące dane nie są wymyślane: kandydat może wykonać `ABSTAIN`;
- próg potwierdzenia jakości pozostaje prowadzony przez istniejący
  Champion-Challenger i Statistical Evidence Scorecard.

## Siatkówka

- Elo pozostaje kompatybilnym championem;
- challenger dodaje siłę setową, jakość próby i kalibrację temperatury;
- parametry ensemble są wybierane chronologicznie bez kursów bukmachera;
- kandydat powstaje od 250 zakończonych spotkań;
- automatyczna promocja wymaga minimum 750 spotkań, 240 obserwacji
  out-of-time i 180 rozliczeń live shadow;
- obowiązuje stabilność segmentów ligowych i brak krytycznego driftu.

## Piłka ręczna

- Elo pozostaje kompatybilnym championem;
- remisy nie są już wyrzucane z uczenia siły drużyn;
- remis aktualizuje Elo celem 0.5, ale nie jest fałszywie etykietowany jako
  zwycięstwo gości w walidacji rynku no-draw;
- challenger dodaje siłę bramkową, estymację remisu, prawdopodobieństwa 1X2
  w trybie shadow i kalibrację temperatury;
- kandydat powstaje od 300 zakończonych spotkań;
- automatyczna promocja wymaga minimum 850 spotkań, 260 obserwacji
  out-of-time i 200 rozliczeń live shadow.

## Dane i kursy

- snapshoty otrzymują etapy OPENING, T-24H, T-12H, T-6H, T-3H, T-60M i CLOSING;
- po wejściu w nowy etap kurs jest pobierany niezależnie od zwykłego interwału;
- w ostatniej godzinie dopuszczony jest zapis co 15 minut, faktyczna częstość
  nadal zależy od interwału procesu (obecnie 30 minut);
- kurs po rozpoczęciu meczu jest oznaczany `POST_KICKOFF_REJECT`;
- audyt V12 raportuje coverage kursu zamknięcia, kalibrację i klasy lig.

## Klasy jakości lig

- A: wysoka kompletność identyfikacji, rozliczeń i kursów zamknięcia;
- B: dane wystarczające do treningu;
- C: dane obserwacyjne, bez automatycznej publikacji;
- QUARANTINE: dane niedojrzałe lub niewiarygodne.

Ocena dotyczy jakości danych, nie popularności ani oczekiwanej rentowności ligi.

## Bezpieczeństwo wdrożenia

- aktywny model nie jest podmieniany przez instalację paczki;
- historyczne pliki CSV i bazy SQLite nie znajdują się w paczce;
- istniejące modele Elo są zgodne wstecznie (`form_weight=0`,
  `calibration_temperature=1`);
- siatkówka i piłka ręczna pozostają `shadow_only`;
- V12 nie uruchamia obstawiania realnym kapitałem;
- audyt otwiera sportowe bazy w trybie tylko do odczytu;
- raporty V12 są plikami pochodnymi i mogą być odtworzone.

## Po wdrożeniu

Nie trzeba dodawać nowych zmiennych Railway. Po restarcie w logach powinny
pozostać aktywne procesy:

- `autonomous_quality_v11` (z komponentem `multisport_v12`);
- `volleyball_shadow`;
- `handball_shadow`;
- dashboard i pozostałe procesy produkcyjne.

Raport będzie tworzony w:

`data/quality_retraining/multisport_v12_audit.json`

