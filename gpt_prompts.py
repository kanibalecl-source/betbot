from __future__ import annotations

import json
from typing import Any, Dict


def _first(source: Dict[str, Any], *names: str, default: str = "") -> str:
    for name in names:
        value = source.get(name)
        if value not in (None, ""):
            return str(value)
    return default


def build_hidden_match_analysis_prompt(item: Dict[str, Any]) -> str:
    """Build the hidden prompt executed for one match after clicking Analyze."""
    source_row = item.get("source_row") if isinstance(item.get("source_row"), dict) else {}
    match = _first(item, "match", default=_first(source_row, "match", "mecz", default="brak danych"))
    league = _first(item, "league", default=_first(source_row, "league", "liga", default="brak danych"))
    kickoff = _first(item, "time", default=_first(source_row, "match_date", "date", "kickoff", default="brak danych"))
    venue = _first(source_row, "stadium", "venue", "miejsce", default="brak potwierdzonych danych")

    system_context = {
        "profil_ryzyka": item.get("profile", "prematch"),
        "typ_bota": item.get("bet", ""),
        "kurs": item.get("odds", ""),
        "dane_bota": source_row,
    }

    return f"""
Przygotuj profesjonalną, niezależną analizę meczu piłkarskiego:

Mecz: {match}
Rozgrywki: {league}
Data i godzina: {kickoff}
Miejsce: {venue}
Cel analizy: ocena sportowa oraz oszacowanie prawdopodobieństwa wyników.

Przeprowadź aktualne badanie internetu. Wszystkie dane sprawdź na moment
sporządzania raportu. Preferuj źródła pierwotne i wiarygodne: oficjalne
strony ligi, klubów i federacji, komunikaty dotyczące składów oraz uznane
serwisy statystyczne.

Zbadaj:

1. Formę obu drużyn:
   - ostatnie 10 spotkań;
   - osobno mecze domowe i wyjazdowe;
   - siłę przeciwników;
   - wyniki, bramki, xG i xGA.

2. Statystyki:
   - strzały i strzały celne;
   - duże okazje;
   - posiadanie piłki;
   - stałe fragmenty;
   - PPDA lub inne dane dotyczące pressingu;
   - gole oczekiwane z gry i ze stałych fragmentów;
   - częstotliwość BTTS oraz over/under 1,5, 2,5 i 3,5 gola.

3. Sytuację kadrową:
   - potwierdzone kontuzje i zawieszenia;
   - zawodników niepewnych występu;
   - przewidywane składy;
   - możliwą rotację;
   - znaczenie brakujących piłkarzy.
   Wyraźnie oddziel informacje potwierdzone od przypuszczeń.

4. Taktykę:
   - prawdopodobne ustawienia;
   - styl gry;
   - pressing, budowanie ataku i obronę przejściową;
   - słabe i mocne strony;
   - najważniejsze pojedynki pozycyjne;
   - wzajemne dopasowanie stylów.

5. Czynniki zewnętrzne:
   - odpoczynek od poprzedniego meczu;
   - napięcie terminarza i podróże;
   - pogodę i stan boiska;
   - znaczenie spotkania oraz motywację;
   - sędziego i jego aktualne statystyki, jeżeli są wiarygodnie dostępne.

6. Bezpośrednie spotkania:
   - uwzględnij tylko te mecze, które nadal mają znaczenie;
   - nie przeceniaj starych wyników po zmianach trenerów lub składów.

Zasady:

- Nie wymyślaj żadnych danych.
- Każdą istotną aktualną informację opatrz linkiem do źródła.
- Podaj datę i godzinę dostępu do danych.
- Przy sprzecznych danych pokaż rozbieżności i oceń wiarygodność źródeł.
- Wskaż dane niedostępne albo niepewne.
- Nie wyciągaj wniosków wyłącznie z tabeli ligowej lub wyników H2H.
- Oddziel fakty, własne wnioski i prognozy.
- Nie traktuj kursów bukmacherskich jako dowodu sportowego.

Na końcu przedstaw:

A. Krótkie podsumowanie najważniejszych faktów.
B. Mocne i słabe strony obu zespołów.
C. Trzy najbardziej prawdopodobne scenariusze meczu.
D. Prawdopodobieństwa:
   - wygrana gospodarzy;
   - remis;
   - wygrana gości;
   - over/under 2,5 gola;
   - BTTS tak/nie.
   W każdej parze wartości muszą sumować się do 100%.
E. Trzy najbardziej prawdopodobne dokładne wyniki.
F. Ocenę pewności prognozy w skali 1–10.
G. Najważniejsze ryzyka, które mogą zmienić prognozę.
H. Listę wykorzystanych źródeł wraz z oceną ich jakości.

Jeżeli oficjalne składy nie zostały jeszcze ogłoszone, przygotuj analizę
wstępną i napisz, które elementy trzeba ponownie sprawdzić 60–75 minut
przed rozpoczęciem spotkania.

Dodatkowy kontekst przekazany przez system:
{json.dumps(system_context, ensure_ascii=False, default=str)}

Wymóg techniczny panelu: zwróć WYŁĄCZNIE poprawny JSON bez markdownu.
Nie pomijaj wymaganych wyżej sekcji A–H. Użyj dokładnie tej struktury:
{{
  "decision": "PLAY albo WATCH albo SKIP",
  "confidence": 0,
  "value_score": 0,
  "risk": "low albo medium albo high albo very_high",
  "quality_score": 0,
  "main_reason": "jednozdaniowy główny wniosek po polsku",
  "summary": "sekcja A: krótkie podsumowanie najważniejszych faktów",
  "analysis": {{
    "najwazniejsze_dane": "zweryfikowane fakty z linkami do źródeł",
    "forma": "forma obu drużyn z ostatnich 10 spotkań",
    "statystyki": "xG, xGA, strzały, duże okazje, posiadanie, PPDA i trendy bramkowe",
    "kontuzje_kadra": "potwierdzone braki, niepewni zawodnicy, składy i rotacje",
    "styl_matchup": "taktyka, ustawienia i dopasowanie stylów",
    "czynniki_zewnetrzne": "odpoczynek, terminarz, podróże, pogoda, boisko i sędzia",
    "h2h": "wyłącznie nadal istotne bezpośrednie spotkania",
    "mocne_slabe_strony": "sekcja B dla obu zespołów",
    "scenariusze": ["scenariusz 1", "scenariusz 2", "scenariusz 3"],
    "prawdopodobienstwa": {{
      "wygrana_gospodarzy": 0,
      "remis": 0,
      "wygrana_gosci": 0,
      "over_2_5": 0,
      "under_2_5": 0,
      "btts_tak": 0,
      "btts_nie": 0
    }},
    "dokladne_wyniki": ["wynik 1", "wynik 2", "wynik 3"],
    "pewnosc_1_10": 0,
    "ryzyka": "sekcja G: czynniki mogące zmienić prognozę",
    "elementy_do_sprawdzenia": "co sprawdzić ponownie 60–75 minut przed meczem",
    "zrodla": [
      {{"nazwa": "źródło", "url": "https://...", "jakosc": "wysoka/średnia/niska", "dostep": "data i godzina"}}
    ],
    "value_kurs": "kurs oceniaj dopiero po analizie sportowej; nie traktuj go jako dowodu",
    "argumenty_za": "najważniejsze argumenty za typem systemu",
    "argumenty_przeciw": "najważniejsze argumenty przeciw typowi systemu",
    "alternatywa": "lepsza alternatywa dla tego meczu albo brak",
    "rekomendacja": "końcowa rekomendacja po polsku"
  }}
}}

Warunki walidacji liczb:
- wygrana_gospodarzy + remis + wygrana_gosci = 100;
- over_2_5 + under_2_5 = 100;
- btts_tak + btts_nie = 100;
- confidence i value_score podaj w skali 0–100, a pewnosc_1_10 w skali 1–10.
""".strip()
