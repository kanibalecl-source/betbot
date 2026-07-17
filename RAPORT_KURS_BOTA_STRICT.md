# Kurs bota — wersja STRICT DATA

## Zasada

`kurs_bota = 1 / prawdopodobieństwo_modelu`

Prawdopodobieństwo modelu powstaje z empirycznych średnich bramek obliczonych
wyłącznie z zakończonych spotkań (`FT`, `AET`, `PEN`) i przejrzystego modelu
Poissona. Kurs bukmachera nie jest wejściem do własnego kursu. Jest używany
dopiero do porównania wartości:

- `edge = p_modelu - (1 / kurs_bukmachera)`,
- `EV = p_modelu * kurs_bukmachera - 1`.

## Usunięte luki

- usunięto mieszanie prawdopodobieństwa modelu z prawdopodobieństwem bukmachera,
- usunięto ręczną „kalibrację” bez rozliczonej próby uczącej,
- usunięto stałą korektę Dixon–Coles `rho=-0.10`,
- usunięto sztuczne ograniczanie wejściowych średnich do `0.3–4.2`,
- brak danych nie tworzy już `50%`, kursu `2.00`, `999` ani neutralnej marży,
- wymagane jest minimum pięć prawdziwych zakończonych spotkań każdej drużyny,
- mecze nierozliczone nie trafiają do średnich bramek,
- marża jest liczona tylko z pełnego rynku jednego bukmachera; brak pełnego
  rynku jest oznaczany jako brak danych,
- dashboard nie pokazuje już przykładowych, wpisanych na stałe kursów,
  prawdopodobieństw ani „xG” przy brakującym polu,
- dane wejściowe są opisane zgodnie z prawdą jako empiryczne tempo bramek,
  a nie xG dostarczone przez zewnętrznego dostawcę.

## Zachowanie danych

Zmiana nie modyfikuje schematu ani zawartości historii, rozliczeń i nauki.
Paczka lokalna zawiera odzyskany katalog `data`, aby redeploy nie wyzerował
zgromadzonego stanu.
