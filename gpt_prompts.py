from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def build_hidden_match_analysis_prompt(item: Dict[str, Any]) -> str:
    """Full user-approved research prompt with a machine-readable envelope."""
    payload = {
        "profil_ryzyka": item.get("profile", "prematch"),
        "liga": item.get("league", ""),
        "mecz": item.get("match", ""),
        "termin": item.get("time", ""),
        "typ_bota": item.get("bet", ""),
        "kurs": item.get("odds", ""),
        "dane_bota": item.get("source_row", {}),
    }
    template_path = Path(__file__).with_name("model_ai_analysis_prompt_v2.txt")
    try:
        approved_prompt = template_path.read_text(encoding="utf-8").strip()
    except Exception:
        approved_prompt = "Przygotuj profesjonalną, niezależną analizę meczu piłkarskiego."
    approved_prompt = (
        approved_prompt
        .replace("[DRUŻYNA A] – [DRUŻYNA B]", str(payload["mecz"] or "brak danych"))
        .replace("[LIGA/PUCHAR]", str(payload["liga"] or "brak danych"))
        .replace("[DATA, GODZINA, STREFA CZASOWA]", str(payload["termin"] or "brak danych"))
    )
    return f"""
{approved_prompt}

DODATKOWY KONTEKST TYPU BOTA (nie zmieniaj danych źródłowych):
{json.dumps(payload, ensure_ascii=False, default=str)}

WYMÓG TECHNICZNY PANELU MODEL AI:
Zwróć WYŁĄCZNIE poprawny JSON, bez markdown. Zachowaj w polach tekstowych
wszystkie sekcje A–H, źródła, linki, czas dostępu, rozbieżności i braki danych.
{{
  "decision": "PLAY albo WATCH albo SKIP",
  "confidence": 0,
  "value_score": 0,
  "risk": "low albo medium albo high albo very_high",
  "quality_score": 0,
  "main_reason": "jednozdaniowy główny powód decyzji po polsku",
  "summary": "krótkie podsumowanie po polsku",
  "analysis": {{
    "najwazniejsze_dane": "sekcje A-H, konkretne dane, scenariusze i prawdopodobieństwa",
    "forma": "forma obu drużyn",
    "styl_matchup": "styl gry i dopasowanie drużyn",
    "liga_rozgrywki": "charakterystyka ligi lub rozgrywek",
    "kontuzje_kadra": "kontuzje, zawieszenia, rotacje, składy lub brak danych",
    "motywacja_atmosfera": "motywacja, tabela, terminarz, znaczenie meczu",
    "value_kurs": "ocena kursu i value",
    "argumenty_za": "najważniejsze argumenty za typem",
    "argumenty_przeciw": "najważniejsze argumenty przeciw typowi",
    "ryzyka": "co może zepsuć typ",
    "dopasowanie_profilu": "czy typ pasuje do profilu ryzyka",
    "alternatywa": "lepsza alternatywa dla tego meczu albo brak",
    "rekomendacja": "końcowa rekomendacja po polsku",
    "zrodla": "lista źródeł z linkami, czasem dostępu i oceną jakości"
  }}
}}
""".strip()
