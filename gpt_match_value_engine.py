from __future__ import annotations

import csv
import hashlib
import json
import logging
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
MODEL_AI_PROMPT_VERSION = "v2.1-structured"
DEFAULT_ANALYSIS_MODEL = "gpt-5.6-terra"
DEFAULT_FALLBACK_MODEL = "gpt-4.1-mini"
LOGGER = logging.getLogger(__name__)

ANALYSIS_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["PLAY", "WATCH", "SKIP"]},
        "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
        "value_score": {"type": "number", "minimum": 0, "maximum": 10},
        "risk": {
            "type": "string",
            "enum": ["low", "medium", "high", "very_high"],
        },
        "quality_score": {"type": "number", "minimum": 0, "maximum": 10},
        "main_reason": {"type": "string"},
        "summary": {"type": "string"},
        "analysis": {
            "type": "object",
            "properties": {
                "najwazniejsze_dane": {"type": "string"},
                "forma": {"type": "string"},
                "styl_matchup": {"type": "string"},
                "liga_rozgrywki": {"type": "string"},
                "kontuzje_kadra": {"type": "string"},
                "motywacja_atmosfera": {"type": "string"},
                "value_kurs": {"type": "string"},
                "argumenty_za": {"type": "string"},
                "argumenty_przeciw": {"type": "string"},
                "ryzyka": {"type": "string"},
                "dopasowanie_profilu": {"type": "string"},
                "alternatywa": {"type": "string"},
                "rekomendacja": {"type": "string"},
                "zrodla": {"type": "string"},
            },
            "required": [
                "najwazniejsze_dane",
                "forma",
                "styl_matchup",
                "liga_rozgrywki",
                "kontuzje_kadra",
                "motywacja_atmosfera",
                "value_kurs",
                "argumenty_za",
                "argumenty_przeciw",
                "ryzyka",
                "dopasowanie_profilu",
                "alternatywa",
                "rekomendacja",
                "zrodla",
            ],
            "additionalProperties": False,
        },
    },
    "required": [
        "decision",
        "confidence",
        "value_score",
        "risk",
        "quality_score",
        "main_reason",
        "summary",
        "analysis",
    ],
    "additionalProperties": False,
}


class GPTAnalysisError(RuntimeError):
    """Raised when no provider attempt returns a validated analysis."""


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
                "kurs_buk": _first(r, ["kurs_buk", "bookmaker_odds", "book_odds", "odds", "kurs", "price"]),
                "kurs_model": _first(r, ["kurs_model", "model_odds", "fair_odds_model"]),
                "kurs_bota": _first(r, ["kurs_bota", "bot_odds", "fair_odds_final", "fair_odds"]),
                "prawd_model": _first(r, ["prawd_model", "model_probability", "model_prob"]),
                "prawd_final": _first(r, ["prawd_final", "final_probability", "final_prob"]),
                "closing_odds": _first(r, ["closing_odds", "close_odds", "closing_line_odds"]),
                "clv_percent": _first(r, ["clv_percent", "clv"]),
                "bookmaker": _first(r, ["bookmaker", "margin_bookmaker"]),
                "odds_observed_at": _first(r, ["odds_observed_at", "observed_at", "decision_at"]),
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


def _analysis_model() -> str:
    return (
        os.getenv("GPT_ANALYSIS_MODEL", DEFAULT_ANALYSIS_MODEL).strip()
        or DEFAULT_ANALYSIS_MODEL
    )


def _fallback_model() -> str:
    return (
        os.getenv("GPT_ANALYSIS_FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL).strip()
        or DEFAULT_FALLBACK_MODEL
    )


def _cache_path(
    base_dir: Path,
    item: Dict[str, Any],
    model: str | None = None,
) -> Path:
    profile = _safe_name(str(item.get("profile") or "prematch"))
    identity = {
        "prompt_version": MODEL_AI_PROMPT_VERSION,
        "model": model or _analysis_model(),
        "profile": item.get("profile", ""),
        "match": item.get("match", ""),
        "bet": item.get("bet", ""),
        "odds": item.get("odds", ""),
        "league": item.get("league", ""),
        "time": item.get("time", ""),
        "bookmaker": item.get("bookmaker", ""),
        "odds_observed_at": item.get("odds_observed_at", ""),
    }
    digest = hashlib.sha256(
        json.dumps(
            identity,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()[:20]
    return (
        base_dir
        / CACHE_DIR
        / f"{profile}_{_safe_name(str(item.get('match', '')))}_{digest}.json"
    )


def _cache_ttl_seconds() -> int:
    try:
        return max(0, int(os.getenv("GPT_ANALYSIS_CACHE_TTL_SECONDS", "1800")))
    except Exception:
        return 1800


def _request_timeout_seconds() -> float:
    try:
        return max(
            10.0,
            min(
                300.0,
                float(os.getenv("GPT_ANALYSIS_TIMEOUT_SECONDS", "120")),
            ),
        )
    except Exception:
        return 120.0


def _load_cache(
    base_dir: Path,
    item: Dict[str, Any],
    model: str | None = None,
    ttl_seconds: int | None = None,
):
    p = _cache_path(base_dir, item, model=model)
    if not p.exists():
        return None
    try:
        if ttl_seconds is None:
            ttl_seconds = _cache_ttl_seconds()
        if time.time() - p.stat().st_mtime > ttl_seconds:
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("execution_status") != "success":
            return None
        cached = dict(data)
        cached["cache_hit"] = True
        return cached
    except Exception:
        return None


def _save_cache(
    base_dir: Path,
    item: Dict[str, Any],
    data: Dict[str, Any],
    model: str | None = None,
):
    if data.get("execution_status") != "success":
        return
    p = _cache_path(base_dir, item, model=model)
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_suffix(f"{p.suffix}.tmp")
    temp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp.replace(p)


def _prompt(item: Dict[str, Any]) -> str:
    return build_hidden_match_analysis_prompt(item)


def _base_analysis(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "match": item.get("match", ""),
        "bet": item.get("bet", ""),
        "odds": item.get("odds", ""),
        "league": item.get("league", ""),
        "time": item.get("time", ""),
        "kurs_buk": item.get("kurs_buk", item.get("odds", "")),
        "kurs_model": item.get("kurs_model", ""),
        "kurs_bota": item.get("kurs_bota", ""),
        "prawd_model": item.get("prawd_model", ""),
        "prawd_final": item.get("prawd_final", ""),
        "closing_odds": item.get("closing_odds", ""),
        "clv_percent": item.get("clv_percent", ""),
        "bookmaker": item.get("bookmaker", ""),
        "odds_observed_at": item.get("odds_observed_at", ""),
    }


def _safe_error_text(exc: Exception) -> str:
    text = re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED]", str(exc))
    return " ".join(text.split())[:600] or type(exc).__name__


def _response_request_id(response: Any) -> str:
    return str(
        getattr(response, "_request_id", "")
        or getattr(response, "request_id", "")
        or ""
    )


def _validated_analysis(parsed: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(parsed, dict):
        raise ValueError("Odpowiedź modelu nie jest obiektem JSON.")
    analysis = parsed.get("analysis")
    if not isinstance(analysis, dict):
        raise ValueError("Odpowiedź modelu nie zawiera sekcji analysis.")
    decision = str(parsed.get("decision", "")).upper()
    if decision not in {"PLAY", "WATCH", "SKIP"}:
        raise ValueError("Nieprawidłowa decyzja modelu.")
    risk = str(parsed.get("risk", "")).lower()
    if risk not in {"low", "medium", "high", "very_high"}:
        raise ValueError("Nieprawidłowy poziom ryzyka modelu.")
    parsed = dict(parsed)
    parsed["decision"] = decision
    parsed["risk"] = risk
    parsed["confidence"] = max(
        0, min(100, int(float(parsed.get("confidence", 0) or 0)))
    )
    parsed["value_score"] = max(
        0.0, min(10.0, float(parsed.get("value_score", 0) or 0))
    )
    parsed["quality_score"] = max(
        0.0, min(10.0, float(parsed.get("quality_score", 0) or 0))
    )
    return parsed


def _provider_attempt(
    client: Any,
    *,
    model: str,
    prompt: str,
    use_web_search: bool,
) -> tuple[Dict[str, Any], Any]:
    kwargs: Dict[str, Any] = {
        "model": model,
        "input": prompt,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "betbot_match_analysis",
                "strict": True,
                "schema": ANALYSIS_JSON_SCHEMA,
            }
        },
    }
    if use_web_search:
        kwargs["tools"] = [{"type": "web_search"}]
    response = client.responses.create(**kwargs)
    status = str(getattr(response, "status", "completed") or "completed")
    if status != "completed":
        details = getattr(response, "incomplete_details", None)
        raise ValueError(f"Niepełna odpowiedź OpenAI: {status}; {details}")
    text = getattr(response, "output_text", "") or ""
    if not text.strip():
        raise ValueError("OpenAI zwróciło pustą odpowiedź tekstową.")
    return _validated_analysis(_parse_json(text)), response


def analyze_match_with_gpt(
    base_dir: Path,
    item: Dict[str, Any],
    *,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    model = _analysis_model()
    cached = None if force_refresh else _load_cache(base_dir, item, model=model)
    if cached:
        return cached

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise GPTAnalysisError(
            "Nie ustawiono OPENAI_API_KEY w zmiennych środowiskowych Railway."
        )

    try:
        from openai import OpenAI
    except Exception as exc:
        raise GPTAnalysisError(
            f"Nie można uruchomić biblioteki OpenAI: {_safe_error_text(exc)}"
        ) from exc

    client = OpenAI(
        api_key=api_key,
        timeout=_request_timeout_seconds(),
        max_retries=0,
    )
    prompt = _prompt(item)
    fallback = _fallback_model()
    attempts = [
        ("primary_web_search", model, True),
        ("primary_without_search", model, False),
    ]
    if fallback != model:
        attempts.append(("fallback_without_search", fallback, False))

    errors: List[Dict[str, str]] = []
    for attempt_number, (label, attempt_model, use_search) in enumerate(
        attempts, start=1
    ):
        try:
            parsed, response = _provider_attempt(
                client,
                model=attempt_model,
                prompt=prompt,
                use_web_search=use_search,
            )
            data = {
                **_base_analysis(item),
                **parsed,
                "profile": str(item.get("profile") or ""),
                "execution_status": "success",
                "cache_hit": False,
                "prompt_version": MODEL_AI_PROMPT_VERSION,
                "provider_model": attempt_model,
                "provider_attempt": label,
                "provider_attempt_number": attempt_number,
                "provider_request_id": _response_request_id(response),
                "web_search_used": use_search,
            }
            _save_cache(base_dir, item, data, model=model)
            LOGGER.info(
                "GPT analysis success match=%r bet=%r model=%s attempt=%s request_id=%s",
                item.get("match", ""),
                item.get("bet", ""),
                attempt_model,
                label,
                data["provider_request_id"],
            )
            return data
        except Exception as exc:
            error = {
                "attempt": label,
                "model": attempt_model,
                "error_type": type(exc).__name__,
                "message": _safe_error_text(exc),
            }
            errors.append(error)
            LOGGER.warning(
                "GPT analysis attempt failed match=%r bet=%r model=%s attempt=%s error_type=%s error=%s",
                item.get("match", ""),
                item.get("bet", ""),
                attempt_model,
                label,
                error["error_type"],
                error["message"],
            )

    summary = "; ".join(
        f"{error['attempt']} ({error['error_type']}): {error['message']}"
        for error in errors
    )
    raise GPTAnalysisError(
        f"Analiza GPT nie została wykonana po {len(errors)} próbach. {summary}"
    )


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
    analyses: List[Dict[str, Any]] = []
    failures: List[Dict[str, str]] = []
    for item in candidates:
        try:
            analyses.append(analyze_match_with_gpt(base_dir, item))
        except GPTAnalysisError as exc:
            failures.append(
                {
                    "match": str(item.get("match", "")),
                    "bet": str(item.get("bet", "")),
                    "error": _safe_error_text(exc),
                }
            )
    coupons = build_ako_coupons(analyses)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "profile": profile_name,
        "count": len(analyses),
        "failed_count": len(failures),
        "failures": failures,
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
    append_event(
        "gpt_analysis_report",
        {
            "profile": profile_name,
            "count": len(analyses),
            "failed_count": len(failures),
            "coupons": len(coupons),
            "file": str(out),
        },
        source="gpt_match_value_engine.py",
    )
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


def run_gpt_analysis_for_item(
    base_dir: Path,
    item: Dict[str, Any],
    profile: str | None = "model_ai",
) -> Dict[str, Any]:
    """Analyze one explicit UI candidate and update only the GPT report.

    The function deliberately does not write picks, training datasets or model
    state.  It is the safe bridge used by the unified Model AI screen.
    """
    base_dir = Path(base_dir)
    profile_name = _profile_slug(profile)
    candidate = dict(item or {})
    candidate["profile"] = profile_name
    analysis = analyze_match_with_gpt(base_dir, candidate)

    report = load_latest_report(base_dir, profile=profile_name, source_files=[])
    analyses = list(report.get("analyses", []) or [])
    for pos, existing in enumerate(analyses):
        if _same_analysis(existing, analysis):
            analyses[pos] = analysis
            break
    else:
        analyses.insert(0, analysis)

    updated = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "profile": profile_name,
        "count": len(analyses),
        "analyses": analyses,
        "coupons": build_ako_coupons(analyses),
    }
    out = _report_path(base_dir, profile_name)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    append_records("gpt_analyses", [analysis], source="gpt_match_value_engine.py")
    append_event(
        "gpt_single_analysis",
        {
            "profile": profile_name,
            "match": analysis.get("match"),
            "bet": analysis.get("bet"),
            "file": str(out),
        },
        source="gpt_match_value_engine.py",
    )
    try:
        from agi_storage import upsert_gpt_analysis
        upsert_gpt_analysis(analysis)
    except Exception:
        pass
    return analysis


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
