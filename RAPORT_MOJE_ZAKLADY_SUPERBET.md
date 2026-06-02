# Raport: Moje zaklady - profile i kursy

## Zakres wdrozenia

Zakladka `MOJE ZAKLADY` zostala podzielona na trzy niezalezne profile:

- `Standard` - korzysta z glownej selekcji bota.
- `Niskie ryzyko` - korzysta z selekcji low.
- `Duze ryzyko` - korzysta z selekcji risk.

W kazdym profilu sa cztery podzakladki:

- `Zaklad pojedynczy`
- `Kupon multi`
- `Historia`
- `Statystyki`

## Kursy

Panel probuje automatycznie pobrac kurs dla wybranego meczu i rynku przez feed kursowy API-Football, wybierajac bukmachera zawierajacego w nazwie `superbet`.

Jezeli feed nie zwroci kursu Superbet dla danego rynku, panel nie blokuje pracy. Uzywa kursu z typu bota jako uzupelnienia i pokazuje zrodlo `Superbet (kurs z bota)`.

Nie zostalo dodane skrobanie strony Superbet, aby nie uzalezniac bota od logowania, geolokalizacji, zmian HTML strony i blokad antybotowych.

## Zapis i rozliczenia

Zapis singli i kuponow multi korzysta z istniejacego modulu `manual_betting.py`:

- zapisuje kazdy kupon do lokalnej bazy SQLite,
- sprawdza wynik po `fixture_id`,
- rozlicza wygrana/przegrana,
- liczy profit i ROI,
- zapisuje statystyki wedlug ligi i typu zakladu.

Nowe profile sa oznaczane w polu `note`, np. `Tryb: low | Niskie ryzyko`, dzieki czemu historia i statystyki w panelu moga byc filtrowane osobno dla kazdego profilu.

## Pliki zmienione

- `dashboard_streamlit.py`
- `data_api.py`

Logika selekcji typow bota nie zostala zmieniona.
