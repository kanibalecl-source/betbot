from __future__ import annotations

import csv
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from ako_coupon_builder import build_ako_coupons
from gpt_prompts import build_hidden_match_analysis_prompt

try:
    from betbot.storage.append_only_history import append_event, append_records
except Exception:
    def append_event(*args, **kwargs):
        return None
    def append_records(*args, **kwargs):
        return 0

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

REPORT_FILE = Path("data/gpt_analysis_report.json")
CACHE_DIR = Path("cache/gpt_analysis")
PROMPT_VERSION = "v2"
try:
    from storage_paths import DATA_DIR as SHARED_DATA_DIR
except Exception:
    SHARED_DATA_DIR = None


def _read_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return [dict(r) for r in csv.DictReader(f)]
    except Exception:
        return []


def _profile_slug(profile: str | None) -> str:
    text = str(profile or "prematch").strip().lower()
    text = re.sub(r"[^a-z0-9_-]+", "_", text)
    return text or "prematch"


def _report_file(profile: str | None = None) -> Path:
    slug = _profile_slug(profile)
    if slug in {"", "prematch", "standard", "main"}:
        return Path("data/gpt_analysis_report_prematch.json")
    return Path(f"data/gpt_analysis_report_{slug}.json")


def _report_path(base_dir: Path, profile: str | None = None) -> Path:
    report_name = _report_file(profile).name
    if SHARED_DATA_DIR is not None:
        return Path(SHARED_DATA_DIR) / report_name
    return Path(base_dir) / "data" / report_name


def load_candidate_matches(base_dir: Path, limit: int | None = None, source_files: List[Path] | None = None, profile: str | None = None) -> List[Dict[str, Any]]:
    shared_files = []
    if SHARED_DATA_DIR is not None:
        shared_files = [
            Path(SHARED_DATA_DIR) / "auto_all_picks.csv",
            Path(SHARED_DATA_DIR) / "live_matches.csv",
        ]
    files = list(source_files or []) + shared_files + [
        base_dir / "data" / "auto_all_picks.csv",
        base_dir / "data" / "live_matches.csv",
        base_dir / "auto_all_picks.csv",
        base_dir / "live_matches.csv",
    ]
    rows: List[Dict[str, Any]] = []
    seen = set()
    for file in files:
        for r in _read_csv(file):
            match = _first(r, ["match", "mecz", "fixture", "game", "teams", "home_away"])
            home = _first(r, ["home", "home_team", "gospodarze"])
            away = _first(r, ["away", "away_team", "goscie", "goście"])
            if not match and (home or away):
                match = f"{home} vs {away}".strip()
            bet = _first(r, ["bet", "pick", "type", "typ", "market", "selection"])
            odds = _first(r, ["odds", "kurs", "price"])
            if not match or not bet:
                continue
            key = (match.lower(), bet.lower(), str(odds))
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "match": match,
                "bet": bet,
                "odds": odds or "",
                "league": _first(r, ["league", "liga"]),
                "time": _first(r, ["time", "start", "date", "kickoff"]),
                "profile": _profile_slug(profile),
                "source_row": r,
            })
            if limit and len(rows) >= limit:
                return rows
    return rows


def _first(row: Dict[str, Any], keys: List[str]) -> str:
    lower = {str(k).lower(): v for k, v in row.items()}
    for k in keys:
        v = lower.get(k.lower())
        if v not in (None, "", "nan"):
            return str(v)
    return ""


def _safe_name(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_-]+", "_", text)[:120]
    return text or "match"


def _cache_path(base_dir: Path, item: Dict[str, Any]) -> Path:
    profile = _safe_name(str(item.get("profile") or "prematch"))
    return base_dir / CACHE_DIR / f"{PROMPT_VERSION}_{profile}_{_safe_name(item.get('match',''))}_{_safe_name(item.get('bet',''))}.json"


def _load_cache(base_dir: Path, item: Dict[str, Any], ttl_seconds: int = 1800):
    p = _cache_path(base_dir, item)
    if not p.exists():
        return None
    try:
        if time.time() - p.stat().st_mtime > ttl_seconds:
            return None
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_cache(base_dir: Path, item: Dict[str, Any], data: Dict[str, Any]):
    p = _cache_path(base_dir, item)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _prompt(item: Dict[str, Any]) -> str:
    return build_hidden_match_analysis_prompt(item)


def _fallback_analysis(item: Dict[str, Any], reason: str = "") -> Dict[str, Any]:
    return {
        "match": item.get("match", ""),
        "bet": item.get("bet", ""),
        "odds": item.get("odds", ""),
        "league": item.get("league", ""),
        "time": item.get("time", ""),
        "decision": "SKIP",
        "confidence": 0,
        "value_score": 0,
        "risk": "high",
        "summary": "Brak pełnej analizy GPT — sprawdź OPENAI_API_KEY albo uruchom analizę ponownie.",
        "analysis": {
            "forma": "Analiza nie została wykonana.",
            "kontuzje_kadra": "Brak danych GPT.",
            "styl_matchup": "Brak danych GPT.",
            "motywacja_atmosfera": "Brak danych GPT.",
            "value_kurs": "Brak danych GPT.",
            "ryzyka": reason or "Brak odpowiedzi modelu.",
            "rekomendacja": "Nie grać bez ręcznej weryfikacji.",
        },
    }


def analyze_match_with_gpt(base_dir: Path, item: Dict[str, Any]) -> Dict[str, Any]:
    cached = _load_cache(base_dir, item)
    if cached:
        return cached

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        data = _fallback_analysis(item, "Nie ustawiono OPENAI_API_KEY w .env / zmiennych środowiskowych.")
        _save_cache(base_dir, item, data)
        return data

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        model = os.getenv("GPT_ANALYSIS_MODEL", os.getenv("OPENAI_MODEL", "gpt-5.2-chat-latest")).strip() or "gpt-5.2-chat-latest"
        prompt = _prompt(item)

        # Najpierw próbujemy z web search, bo użytkownik chce analizę formy, kontuzji i newsów.
        # Jeśli konto/model nie obsłuży web_search_preview, robimy drugi bezpieczny fallback bez narzędzia,
        # żeby zakładka GPT nie wywróciła całego dashboardu.
        response = client.responses.create(
            model=model,
            tools=[{"type": "web_search_preview"}],
            input=prompt,
        )

        text = getattr(response, "output_text", "") or ""
        parsed = _parse_json(text)
        data = {
            "match": item.get("match", ""),
            "bet": item.get("bet", ""),
            "odds": item.get("odds", ""),
            "league": item.get("league", ""),
            "time": item.get("time", ""),
            **parsed,
        }
        data["confidence"] = int(float(data.get("confidence", 0) or 0))
        data["value_score"] = float(data.get("value_score", 0) or 0)
        data["quality_score"] = float(data.get("quality_score", 0) or 0)
        data["decision"] = str(data.get("decision", "SKIP")).upper()
        data["profile"] = str(item.get("profile") or "")
        data["data_provenance"] = "OPENAI_WEB_SEARCH"
        _save_cache(base_dir, item, data)
        return data
    except Exception as e:
        data = _fallback_analysis(item, str(e))
        _save_cache(base_dir, item, data)
        return data


def _parse_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if m:
            return json.loads(m.group(0))
        raise ValueError("Model nie zwrócił poprawnego JSON.")


def run_full_gpt_analysis(base_dir: Path, limit: int | None = None, profile: str | None = None, source_files: List[Path] | None = None) -> Dict[str, Any]:
    base_dir = Path(base_dir)
    profile_name = _profile_slug(profile)
    candidates = load_candidate_matches(base_dir, limit=limit, source_files=source_files, profile=profile_name)
    analyses = [analyze_match_with_gpt(base_dir, item) for item in candidates]
    coupons = build_ako_coupons(analyses)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "profile": profile_name,
        "count": len(analyses),
        "analyses": analyses,
        "coupons": coupons,
    }
    out = _report_path(base_dir, profile_name)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if profile_name in {"prematch", "standard", "main"}:
        legacy = _report_path(base_dir, "legacy").with_name(REPORT_FILE.name)
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    append_records("gpt_analyses", analyses, source="gpt_match_value_engine.py")
    append_records("gpt_coupons", coupons, source="gpt_match_value_engine.py")
    append_event("gpt_analysis_report", {"profile": profile_name, "count": len(analyses), "coupons": len(coupons), "file": str(out)}, source="gpt_match_value_engine.py")
    try:
        from agi_storage import upsert_gpt_analysis
        for item in analyses:
            upsert_gpt_analysis(item)
    except Exception:
        pass
    return report


def _same_analysis(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return (
        str(a.get("match", "")).lower() == str(b.get("match", "")).lower()
        and str(a.get("bet", "")).lower() == str(b.get("bet", "")).lower()
        and str(a.get("odds", "")) == str(b.get("odds", ""))
    )


def run_single_gpt_analysis(
    base_dir: Path,
    index: int,
    limit: int | None = None,
    profile: str | None = None,
    source_files: List[Path] | None = None,
) -> Dict[str, Any]:
    base_dir = Path(base_dir)
    profile_name = _profile_slug(profile)
    candidates = load_candidate_matches(base_dir, limit=limit, source_files=source_files, profile=profile_name)
    if not candidates:
        return load_latest_report(base_dir, profile=profile_name, source_files=source_files)
    safe_index = max(0, min(int(index), len(candidates) - 1))
    analysis = analyze_match_with_gpt(base_dir, candidates[safe_index])

    report = load_latest_report(base_dir, profile=profile_name, source_files=source_files)
    analyses = list(report.get("analyses", []) or [])
    replaced = False
    for pos, existing in enumerate(analyses):
        if _same_analysis(existing, analysis):
            analyses[pos] = analysis
            replaced = True
            break
    if not replaced:
        analyses.insert(0, analysis)

    coupons = build_ako_coupons(analyses)
    updated = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "profile": profile_name,
        "count": len(analyses),
        "analyses": analyses,
        "coupons": coupons,
    }
    out = _report_path(base_dir, profile_name)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    if profile_name in {"prematch", "standard", "main"}:
        legacy = _report_path(base_dir, "legacy").with_name(REPORT_FILE.name)
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    append_records("gpt_analyses", [analysis], source="gpt_match_value_engine.py")
    append_event("gpt_single_analysis", {"profile": profile_name, "match": analysis.get("match"), "bet": analysis.get("bet"), "file": str(out)}, source="gpt_match_value_engine.py")
    try:
        from agi_storage import upsert_gpt_analysis
        upsert_gpt_analysis(analysis)
    except Exception:
        pass
    return updated


def load_latest_report(base_dir: Path, profile: str | None = None, source_files: List[Path] | None = None) -> Dict[str, Any]:
    profile_name = _profile_slug(profile)
    path = _report_path(Path(base_dir), profile_name)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    if profile_name in {"prematch", "standard", "main"}:
        legacy = _report_path(Path(base_dir), "legacy").with_name(REPORT_FILE.name)
        if legacy.exists():
            try:
                return json.loads(legacy.read_text(encoding="utf-8"))
            except Exception:
                pass
    candidates = load_candidate_matches(Path(base_dir), limit=25, source_files=source_files, profile=profile_name)
    return {
        "generated_at": None,
        "profile": profile_name,
        "count": 0,
        "analyses": [],
        "coupons": [],
        "message": "Brak gotowej analizy. Kliknij 'Uruchom analizę GPT'.",
        "candidates_found": len(candidates),
    }


if __name__ == "__main__":
    print(json.dumps(run_full_gpt_analysis(Path(__file__).resolve().parent), ensure_ascii=False, indent=2))
