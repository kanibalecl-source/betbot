# Instrukcja wdrozenia - Etap 5 Wyglad WWW

## Co zmienia paczka

Etap 5 zmienia warstwe wizualna panelu WWW na podstawie zaakceptowanego renderu 1:1.

Zachowane:

- obecna kolorystyka KANIBAL,
- logika bota,
- scheduler,
- API,
- historia append-only,
- zakladki i dane z Etapu 4.

Dodane:

- pelny baner z nazwa na kazdej glownej zakladce,
- banery podstron w Prematch, History, Moje Zaklady i GPT,
- bardziej profesjonalny wyglad kart, tabel, ramek i przestrzeni,
- czytelniejszy uklad strony jak w profesjonalnym serwisie analitycznym.

## Wdrozenie

1. Zachowaj backup poprzedniej dzialajacej paczki.
2. Wgraj ZIP Etapu 5.
3. Nie usuwaj katalogu `/data` na serwerze.
4. Zrob redeploy/restart.
5. Sprawdz panel WWW:
   - kazda glowna zakladka ma pelny baner,
   - podzakladki maja banery sekcji,
   - dane i tabele laduja sie jak w Etapie 4.

## Cofniecie

Wgraj ZIP Etapu 4 albo Etapu 3D i zrestartuj aplikacje. Etap 5 nie zmienia formatu danych ani logiki typowania.

