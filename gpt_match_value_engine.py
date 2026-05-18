"""GPT + web-search match value engine.

This module does NOT ask the bot's internal model for team context. It sends only
basic fixture + proposed bet data to OpenAI and lets the model search the public
web for current context: form, injuries, lineups, morale, playing style, schedule,
weather/motivation signals, and recent news.

Safety note: this is a decision-support layer. It never places bets.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - allows app to run without openai installed
    OpenAI = None  # type: ignore

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
GPT_CACHE_FILE = DATA_DIR / "gpt_match_value_cache.json"
GPT_EVAL_FILE = DATA_DIR / "gpt_match_evaluations.csv"

DEFAULT_MODEL = os.getenv("OPENAI_MATCH_MODEL", "gpt-4.1-mini")
DEFAULT_MAX_MATCHES = int(os.getenv("GPT_MAX_MATCHES", "20"))
DEFAULT_SLEEP_SECONDS = float(os.getenv("GPT_MATCH_SLEEP_SECONDS", "0.3"))


@dataclass
class MatchBetInput:
    match: str
    market: str
    odds: float
    league: str = ""
    country: str = ""
    match_date: str = ""
    bookmaker: str = ""
    bot_confidence: Optional[float] = None
    bot_edge: Optional[float] = None
    bot_ev: Optional[float] = None


EVALUATION_SCHEMA: Dict[str, Any] = {
    "name": "match_bet_evaluation",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "play": {"type": "boolean"},
            "ako_candidate": {"type": "boolean"},
            "single_candidate": {"type": "boolean"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 100},
            "value_rating": {"type": "number", "minimum": 0, "maximum": 10},
            "risk": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "NO_BET"]},
            "recommended_action": {"type": "string", "enum": ["PLAY", "SMALL_STAKE", "ONLY_SINGLE", "SKIP"]},
            "fair_odds_estimate": {"type": "number"},
            "model_probability_estimate": {"type": "number", "minimum": 0, "maximum": 1},
            "context_summary": {"type": "string"},
            "positive_factors": {"type": "array", "items": {"type": "string"}},
            "negative_factors": {"type": "array", "items": {"type": "string"}},
            "missing_info": {"type": "array", "items": {"type": "string"}},
            "reason": {"type": "string"},
            "sources_used": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "play", "ako_candidate", "single_candidate", "confidence", "value_rating", "risk",
            "recommended_action", "fair_odds_estimate", "model_probability_estimate",
            "context_summary", "positive_factors", "negative_factors", "missing_info",
            "reason", "sources_used",
        ],
    },
    "strict": True,
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_cache() -> Dict[str, Any]:
    if GPT_CACHE_FILE.exists():
        try:
            return json.loads(GPT_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_cache(cache: Dict[str, Any]) -> None:
    GPT_CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _cache_key(item: MatchBetInput) -> str:
    # Date prefix prevents using stale context forever while still saving cost during a run.
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    raw = f"{day}|{item.league}|{item.match}|{item.market}|{item.odds}"
    return re.sub(r"\s+", " ", raw.strip().lower())


def _json_from_response(resp: Any) -> Dict[str, Any]:
    # New SDK exposes output_text. Fallback handles dict-like / message content shapes.
    text = getattr(resp, "output_text", None)
    if not text:
        try:
            text = resp.output[0].content[0].text
        except Exception:
            text = str(resp)
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def _fallback_no_api(item: MatchBetInput, reason: str) -> Dict[str, Any]:
    return {
        "play": False,
        "ako_candidate": False,
        "single_candidate": False,
        "confidence": 0,
        "value_rating": 0,
        "risk": "NO_BET",
        "recommended_action": "SKIP",
        "fair_odds_estimate": 0,
        "model_probability_estimate": 0,
        "context_summary": "Analiza GPT-web nie została wykonana.",
        "positive_factors": [],
        "negative_factors": [reason],
        "missing_info": ["Brak aktualnej analizy kontekstowej z internetu."],
        "reason": reason,
        "sources_used": [],
        "evaluated_at": now_iso(),
        "match": item.match,
        "market": item.market,
        "odds": item.odds,
        "league": item.league,
    }


def evaluate_match_bet(item: MatchBetInput, *, model: str = DEFAULT_MODEL, use_cache: bool = True) -> Dict[str, Any]:
    """Evaluate one proposed bet using OpenAI web search.

    Requires OPENAI_API_KEY. Returns a JSON-serializable dict.
    """
    if OpenAI is None:
        return _fallback_no_api(item, "Biblioteka openai nie jest zainstalowana. Dodaj `openai` do requirements.txt.")
    if not os.getenv("OPENAI_API_KEY"):
        return _fallback_no_api(item, "Brak OPENAI_API_KEY w zmiennych środowiskowych.")

    cache = _load_cache() if use_cache else {}
    key = _cache_key(item)
    if use_cache and key in cache:
        cached = dict(cache[key])
        cached["cache_hit"] = True
        return cached

    client = OpenAI()
    payload = asdict(item)
    prompt = f"""
Jesteś konserwatywnym analitykiem piłkarskim i risk managerem zakładów sportowych.
Masz ocenić JEDEN zaproponowany zakład na podstawie aktualnych publicznych informacji z internetu, NIE na podstawie wewnętrznych statystyk bota.

Zadanie:
1. Wyszukaj aktualny kontekst meczu: forma drużyn, styl gry, kontuzje, zawieszenia, przewidywane składy, rotacje, terminarz, motywacja, atmosfera/news, H2H tylko pomocniczo, pogoda jeśli istotna.
2. Oceń, czy konkretny zakład ma value przy podanym kursie.
3. Bądź ostrożny: jeśli brakuje świeżych informacji, obniż confidence i wpisz to w missing_info.
4. Nie obiecuj zysku. Nie traktuj kursu jako dowodu, tylko jako cenę do oceny value.
5. Zwróć wyłącznie JSON zgodny ze schematem.

Dane zakładu:
{json.dumps(payload, ensure_ascii=False, indent=2)}
""".strip()

    resp = client.responses.create(
        model=model,
        input=prompt,
        tools=[{"type": "web_search"}],
        text={"format": {"type": "json_schema", **EVALUATION_SCHEMA}},
    )
    data = _json_from_response(resp)
    data.update({
        "evaluated_at": now_iso(),
        "match": item.match,
        "market": item.market,
        "odds": item.odds,
        "league": item.league,
        "country": item.country,
        "match_date": item.match_date,
        "bookmaker": item.bookmaker,
        "cache_hit": False,
    })
    if use_cache:
        cache[key] = data
        _save_cache(cache)
    return data


def evaluate_many(items: Iterable[MatchBetInput], *, limit: int = DEFAULT_MAX_MATCHES, model: str = DEFAULT_MODEL) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for idx, item in enumerate(list(items)[:limit]):
        results.append(evaluate_match_bet(item, model=model))
        if idx < limit - 1 and DEFAULT_SLEEP_SECONDS > 0:
            time.sleep(DEFAULT_SLEEP_SECONDS)
    return results
