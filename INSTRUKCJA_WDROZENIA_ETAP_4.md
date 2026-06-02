# Instrukcja wdrozenia - Etap 4 Upgrade Zakladek

## Co zmienia paczka

Etap 4 zmienia tylko warstwe panelu WWW. Logika bota, scheduler, API, historia append-only i zapis typow zostaja bez zmian.

## Zakladki po zmianach

- LIVE: usuniete wykresy, usuniety problem `no signal`, tabela pokazuje typ zakladu.
- PREMATCH: usuniety wykres, dodane trzy tabele: Prematch, Prematch LOW, Prematch RISK.
- AI: usuniete wykresy, zostaje lista typow AI i szczegoly.
- ANALYTICS: przebudowane na centrum decyzyjne z tabelami skutecznosci lig, typow, ryzyka i nauki bota.
- HISTORY: przebudowane na czytelne tabele: historia, ligi, typy, decyzyjnosc.
- MOJE ZAKLADY: uproszczone zaznaczanie, domyslny bukmacher Superbet, kurs podstawiany z kursu bota i mozliwy do korekty.
- RANKING: ranking lig, typow i polaczen liga + typ zakladu.
- GPT CHAT: bardziej czytelny uklad z metrykami i dwoma podzakladkami.

Zakladki ALERTS i SETTINGS zostaly usuniete z menu.

## Wdrozenie

1. Zostaw backup obecnej dzialajacej wersji.
2. Wgraj zawartosc ZIP Etapu 4.
3. Nie usuwaj katalogu `/data` na serwerze.
4. Zrob redeploy/restart.
5. Sprawdz logi: `APP LAUNCHER START`, `BOT EXECUTED`, `PERSISTENCE/HISTORY OK`, `HEARTBEAT`.
6. Otworz panel WWW i sprawdz glowne zakladki.

## Cofniecie

Wgraj poprzedni ZIP Etapu 3D i zrestartuj aplikacje. Etap 4 nie zmienia formatu bazy ani logiki typowania.

