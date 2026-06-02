# Raport: wdrozenie strony logowania

## Zakres

Zmieniono wyglad strony logowania na zaakceptowany projekt:

- lewa strona: duzy okrag z banerem KANIBAL ANALYTICS wysrodkowanym w kole,
- prawa strona: futurystyczny panel logowania,
- kolorystyka zgodna z panelem: czern, grafit, zielen KANIBAL,
- bez tekstow marketingowych po lewej stronie.

## Logika

Mechanizm logowania nie zostal zmieniony:

- uzytkownicy nadal sa czytani z `users.json`,
- hasla dzialaja jak poprzednio,
- po zalogowaniu uzytkownik trafia do dashboardu.

## Plik zmieniony

- `auth_manager.py`
