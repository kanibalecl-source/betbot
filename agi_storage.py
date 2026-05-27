from shadow.shadow_logger import log_shadow_event
from __future__ import annotations

import csv
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_FILE = Path(os.getenv("KANIBAL_SQLITE_PATH", str(DATA_DIR / "kanibal_persistent.sqlite3")))

PICK_FILES = [
    DATA_DIR / "auto_all_picks.csv",
    DATA_DIR / "ai_picks.csv",
    DATA_DIR / "live_matches.csv",
    BASE_DIR / "auto_all_picks.csv",
    BASE_DIR / "live_matches.csv",
]
HISTORY_EXPORT = DATA_DIR / "results_history.csv"
GPT_EXPORT = DATA_DIR / "gpt_analysis_report.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    c = sqlite3.connect(DB_FILE)
    c.row_factory = sqlite3.Row
    return c


def init_storage() -> None:
    c = conn()
    c.execute("""
    CREATE TABLE IF NOT EXISTS picks_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pick_key TEXT UNIQUE,
        created_at TEXT,
        updated_at TEXT,
        source TEXT,
        fixture_id TEXT,
        league TEXT,
        match_name TEXT,
        home_team TEXT,
        away_team TEXT,
        match_date TEXT,
        market TEXT,
        bet_name TEXT,
        odds REAL,
        confidence REAL,
        edge REAL,
        ev REAL,
        probability REAL,
        stake REAL DEFAULT 1,
        status TEXT DEFAULT 'OPEN',
        result TEXT DEFAULT 'PENDING',
        profit REAL DEFAULT 0,
        roi REAL DEFAULT 0,
        raw_json TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS gpt_analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        analysis_key TEXT UNIQUE,
        created_at TEXT,
        updated_at TEXT,
        match_name TEXT,
        market TEXT,
        bet_name TEXT,
        odds REAL,
        decision TEXT,
        confidence REAL,
        value_score REAL,
        risk TEXT,
        summary TEXT,
        analysis_json TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS learning_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        event_type TEXT,
        payload_json TEXT
    )
    """)
    c.commit()
    c.close()


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        if path.exists() and path.stat().st_size > 0:
            return pd.read_csv(path)
    except Exception:
        try:
            return pd.read_csv(path, encoding="utf-8")
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def _first(row: Dict[str, Any], keys: Iterable[str], default: str = "") -> str:
    lower = {str(k).lower(): v for k, v in row.items()}
    for k in keys:
        v = lower.get(k.lower())
        if v is not None and str(v).strip() not in ("", "nan", "None"):
            return str(v).strip()
    return default


def _float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or str(v).strip() == "":
            return default
        return float(v)
    except Exception:
        return default


def _pick_key(row: Dict[str, Any]) -> str:
    fixture = _first(row, ["fixture_id", "id", "event_id"])
    match = _first(row, ["match", "mecz", "fixture", "home_away"])
    home = _first(row, ["home", "home_team", "gospodarze"])
    away = _first(row, ["away", "away_team", "goscie", "goście"])
    if not match and (home or away):
        match = f"{home} vs {away}".strip()
    market = _first(row, ["market", "typ", "bet", "pick", "signal"])
    odds = _first(row, ["kurs_buk", "odds", "kurs", "price"])
    date = _first(row, ["match_date", "date", "time", "kickoff"])
    return "|".join([fixture, match.lower(), market.upper(), odds, date])


def normalize_pick(row: Dict[str, Any], source: str) -> Optional[Dict[str, Any]]:
    match = _first(row, ["match", "mecz", "fixture", "home_away"])
    home = _first(row, ["home", "home_team", "gospodarze"])
    away = _first(row, ["away", "away_team", "goscie", "goście"])
    if not match and (home or away):
        match = f"{home} vs {away}".strip()
    market = _first(row, ["market", "typ", "bet", "pick", "signal"])
    if not match or not market:
        return None
    return {
        "pick_key": _pick_key(row),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "source": source,
        "fixture_id": _first(row, ["fixture_id", "id", "event_id"]),
        "league": _first(row, ["league", "liga"]),
        "match_name": match,
        "home_team": home,
        "away_team": away,
        "match_date": _first(row, ["match_date", "date", "time", "kickoff"]),
        "market": market,
        "bet_name": _first(row, ["bet", "pick", "typ", "selection", "signal"], market),
        "odds": _float(_first(row, ["kurs_buk", "odds", "kurs", "price"]), 0.0),
        "confidence": _float(_first(row, ["confidence", "advanced_confidence", "ai_pick_score", "score"]), 0.0),
        "edge": _float(_first(row, ["edge", "value"]), 0.0),
        "ev": _float(_first(row, ["ev", "value"]), 0.0),
        "probability": _float(_first(row, ["prawd_final", "probability", "prob"]), 0.0),
        "stake": _float(_first(row, ["stake", "stawka_pln"]), 1.0),
        "raw_json": json.dumps(row, ensure_ascii=False),
    }


def sync_picks_from_csv() -> Dict[str, int]:
    init_storage()
    inserted = 0
    updated = 0
    c = conn()
    for path in PICK_FILES:
        df = _read_csv(path)
        if df.empty:
            continue
        source = path.name
        for raw in df.fillna("").to_dict(orient="records"):
            pick = normalize_pick(raw, source)
            if not pick:
                continue
            exists = c.execute("SELECT id FROM picks_history WHERE pick_key=?", (pick["pick_key"],)).fetchone()
            if exists:
                c.execute("""
                    UPDATE picks_history SET updated_at=?, confidence=?, edge=?, ev=?, odds=?, raw_json=? WHERE pick_key=?
                """, (now_iso(), pick["confidence"], pick["edge"], pick["ev"], pick["odds"], pick["raw_json"], pick["pick_key"]))
                updated += 1
            else:
                c.execute("""
                    INSERT INTO picks_history (
                        pick_key, created_at, updated_at, source, fixture_id, league, match_name, home_team, away_team,
                        match_date, market, bet_name, odds, confidence, edge, ev, probability, stake, raw_json
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    pick["pick_key"], pick["created_at"], pick["updated_at"], pick["source"], pick["fixture_id"], pick["league"],
                    pick["match_name"], pick["home_team"], pick["away_team"], pick["match_date"], pick["market"], pick["bet_name"],
                    pick["odds"], pick["confidence"], pick["edge"], pick["ev"], pick["probability"], pick["stake"], pick["raw_json"]
                ))
                inserted += 1
    c.commit()
    c.close()
    export_history_csv()
    log_event("sync_picks", {"inserted": inserted, "updated": updated})
    return {"inserted": inserted, "updated": updated}


def upsert_gpt_analysis(item: Dict[str, Any]) -> None:
    init_storage()
    match = str(item.get("match") or item.get("match_name") or "")
    market = str(item.get("market") or item.get("bet") or "")
    key = f"{match.lower()}|{market.upper()}|{item.get('odds','')}"
    c = conn()
    exists = c.execute("SELECT id FROM gpt_analyses WHERE analysis_key=?", (key,)).fetchone()
    payload = json.dumps(item, ensure_ascii=False)
    vals = (
        now_iso(), match, market, str(item.get("bet") or market), _float(item.get("odds")), str(item.get("decision", "")),
        _float(item.get("confidence")), _float(item.get("value_score")), str(item.get("risk", "")), str(item.get("summary", "")), payload, key
    )
    if exists:
        c.execute("""
        UPDATE gpt_analyses SET updated_at=?, match_name=?, market=?, bet_name=?, odds=?, decision=?, confidence=?, value_score=?, risk=?, summary=?, analysis_json=?
        WHERE analysis_key=?
        """, vals)
    else:
        c.execute("""
        INSERT INTO gpt_analyses (created_at, updated_at, match_name, market, bet_name, odds, decision, confidence, value_score, risk, summary, analysis_json, analysis_key)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (now_iso(),) + vals)
    c.commit()
    c.close()


def load_history_dataframe() -> pd.DataFrame:
    init_storage()
    c = conn()
    try:
        df = pd.read_sql_query("SELECT * FROM picks_history ORDER BY created_at DESC LIMIT 5000", c)
    finally:
        c.close()
    if df.empty:
        return df
    out = df.copy()
    out["match"] = out.get("match_name", "")
    out["league"] = out.get("league", "")
    out["result"] = out.get("result", "PENDING")
    out["profit"] = pd.to_numeric(out.get("profit", 0), errors="coerce").fillna(0)
    out["roi"] = pd.to_numeric(out.get("roi", 0), errors="coerce").fillna(0)
    return out


def load_gpt_dataframe() -> pd.DataFrame:
    init_storage()
    c = conn()
    try:
        return pd.read_sql_query("SELECT * FROM gpt_analyses ORDER BY updated_at DESC LIMIT 1000", c)
    finally:
        c.close()


def export_history_csv() -> None:
    df = load_history_dataframe()
    HISTORY_EXPORT.parent.mkdir(exist_ok=True)
    if not df.empty:
        df.to_csv(HISTORY_EXPORT, index=False)


def log_event(event_type: str, payload: Dict[str, Any]) -> None:
    init_storage()
    c = conn()
    c.execute("INSERT INTO learning_events (created_at, event_type, payload_json) VALUES (?, ?, ?)", (now_iso(), event_type, json.dumps(payload, ensure_ascii=False)))
    c.commit()
    c.close()


if __name__ == "__main__":
    print(sync_picks_from_csv())
