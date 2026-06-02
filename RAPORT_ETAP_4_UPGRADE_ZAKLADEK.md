# Raport Etap 4 - Upgrade Zakladek

## Zakres

Zmiana dotyczy panelu WWW i pliku `dashboard_streamlit.py`. Nie zmieniano matematyki bota, filtracji typow, schedulerow, API ani modulow zapisu historii.

## Zmiany wykonane

- LIVE: tabela bez wykresow, kolumna `Typ zakladu`, czyszczenie wartosci `no signal`.
- PREMATCH: trzy tabele w podzakladkach: Prematch, Prematch LOW, Prematch RISK.
- AI: usuniete wykresy, zostawione typy i szczegoly AI.
- ANALYTICS: tabele decyzyjne aktualizowane na podstawie historii i danych learning.
- HISTORY: tabele historii, lig, typow i najlepszych rekordow decyzyjnych.
- MOJE ZAKLADY: uproszczone single/AKO, domyslnie Superbet, kurs domyslny z typu bota, mozliwa reczna korekta.
- RANKING: tabele skutecznosci lig, typow i kombinacji liga + typ.
- GPT CHAT: czytelniejszy ekran startowy, metryki, dwie podzakladki.
- ALERTS i SETTINGS: usuniete z menu glownego.

## Bezpieczenstwo

Paczka nie zawiera `.env`, cache Pythona ani produkcyjnych danych historii. Katalog `data` zawiera tylko pliki `.gitkeep`, zeby nie nadpisac historii na serwerze.

## Weryfikacja

Sprawdzono skladnie wszystkich plikow Python: 0 bledow.

