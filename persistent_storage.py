from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from storage_paths import DATA_DIR

BASE_DIR = Path(__file__).resolve().parent


def _data_dir() -> Path:
    # Najpierw trwały volume Railway, jeśli użytkownik go podłączył.
    for env_name in ("PERSISTENT_DATA_DIR", "RAILWAY_VOLUME_MOUNT_PATH"):
        value = os.getenv(env_name)
        if value:
            path = Path(value)
            path.mkdir(parents=True, exist_ok=True)
            return path
    # Fallback: obecny folder data. Działa od razu, ale na Railway bez volume może znikać po redeploy.
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


DATA_DIR = _data_dir()
DB_FILE = DATA_DIR / "betbot_memory.sqlite3"
HEALTH_FILE = DATA_DIR / "storage_health.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def storage_mode() -> str:
    if os.getenv("PERSISTENT_DATA_DIR"):
        return "PERSISTENT_DATA_DIR"
    if os.getenv("RAILWAY_VOLUME_MOUNT_PATH"):
        return "RAILWAY_VOLUME_MOUNT_PATH"
    return "LOCAL_DATA_FALLBACK"


def get_conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_storage() -> None:
    conn = get_conn()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS picks (
        pick_key TEXT PRIMARY KEY,
        created_at TEXT,
        updated_at TEXT,
        source TEXT,
        league TEXT,
        match_name TEXT,
        market TEXT,
        bet_name TEXT,
        odds REAL,
        confidence REAL,
        edge REAL,
        ev REAL,
        risk TEXT,
        status TEXT DEFAULT 'OPEN',
        result TEXT DEFAULT 'PENDING',
        profit REAL DEFAULT 0,
        roi REAL DEFAULT 0,
        fixture_id TEXT,
        match_date TEXT,
        raw_json TEXT
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS gpt_analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        question TEXT,
        answer TEXT,
        model TEXT,
        context_json TEXT
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS learning_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        event_type TEXT,
        payload_json TEXT
    )
    """)
    conn.commit()
    conn.close()
    write_health()


def write_health() -> None:
    payload = {
        "updated_at": now_iso(),
        "db_file": str(DB_FILE),
        "storage_mode": storage_mode(),
        "persistent": storage_mode() != "LOCAL_DATA_FALLBACK",
        "note": "Aby dane nie ginely po redeploy na Railway, ustaw PERSISTENT_DATA_DIR albo podlacz Railway Volume.",
    }
    try:
        HEALTH_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(value)
    except Exception:
        return default


def _first(row: Dict[str, Any], names: Iterable[str], default: Any = "") -> Any:
    for name in names:
        if name in row and row.get(name) not in (None, ""):
            return row.get(name)
    return default


def make_pick_key(row: Dict[str, Any], source: str = "") -> str:
    raw = "|".join([
        str(_first(row, ["fixture_id", "id", "event_id"], "")),
        str(_first(row, ["match", "mecz", "match_name"], "")),
        str(_first(row, ["market", "kod_rynku", "typ", "bet"], "")),
        str(_first(row, ["kurs_buk", "odds", "odd"], "")),
        source,
    ])
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:32]


def upsert_pick(row: Dict[str, Any], source: str = "UNKNOWN") -> str:
    init_storage()
    pick_key = str(_first(row, ["pick_key", "ai_id"], "")) or make_pick_key(row, source)
    payload = {
        "pick_key": pick_key,
        "created_at": str(_first(row, ["created_at", "date", "timestamp"], now_iso())),
        "updated_at": now_iso(),
        "source": source,
        "league": str(_first(row, ["league", "liga"], "")),
        "match_name": str(_first(row, ["match", "mecz", "match_name"], "")),
        "market": str(_first(row, ["market", "kod_rynku", "typ"], "")),
        "bet_name": str(_first(row, ["bet_name", "typ", "pick"], "")),
        "odds": _safe_float(_first(row, ["kurs_buk", "odds", "odd"], 0)),
        "confidence": _safe_float(_first(row, ["confidence", "advanced_confidence", "ai_pick_score"], 0)),
        "edge": _safe_float(_first(row, ["edge"], 0)),
        "ev": _safe_float(_first(row, ["ev", "value"], 0)),
        "risk": str(_first(row, ["risk", "risk_level"], "")),
        "fixture_id": str(_first(row, ["fixture_id", "id"], "")),
        "match_date": str(_first(row, ["match_date", "date", "kickoff"], "")),
        "raw_json": json.dumps(row, ensure_ascii=False, default=str),
    }
    conn = get_conn()
    conn.execute("""
    INSERT INTO picks (
        pick_key, created_at, updated_at, source, league, match_name, market,
        bet_name, odds, confidence, edge, ev, risk, fixture_id, match_date, raw_json
    )
    VALUES (
        :pick_key, :created_at, :updated_at, :source, :league, :match_name, :market,
        :bet_name, :odds, :confidence, :edge, :ev, :risk, :fixture_id, :match_date, :raw_json
    )
    ON CONFLICT(pick_key) DO UPDATE SET
        updated_at=excluded.updated_at,
        source=excluded.source,
        league=excluded.league,
        match_name=excluded.match_name,
        market=excluded.market,
        bet_name=excluded.bet_name,
        odds=excluded.odds,
        confidence=excluded.confidence,
        edge=excluded.edge,
        ev=excluded.ev,
        risk=excluded.risk,
        fixture_id=excluded.fixture_id,
        match_date=excluded.match_date,
        raw_json=excluded.raw_json
    """, payload)
    conn.commit()
    conn.close()
    return pick_key


def save_gpt_analysis(question: str, answer: str, model: str, context: Dict[str, Any]) -> None:
    init_storage()
    conn = get_conn()
    conn.execute("""
    INSERT INTO gpt_analyses (created_at, question, answer, model, context_json)
    VALUES (?, ?, ?, ?, ?)
    """, (now_iso(), question, answer, model, json.dumps(context, ensure_ascii=False, default=str)))
    conn.commit()
    conn.close()


def log_learning_event(event_type: str, payload: Dict[str, Any]) -> None:
    init_storage()
    conn = get_conn()
    conn.execute("""
    INSERT INTO learning_events (created_at, event_type, payload_json)
    VALUES (?, ?, ?)
    """, (now_iso(), event_type, json.dumps(payload, ensure_ascii=False, default=str)))
    conn.commit()
    conn.close()


def fetch_recent_picks(limit: int = 50) -> List[Dict[str, Any]]:
    init_storage()
    conn = get_conn()
    rows = conn.execute("""
    SELECT * FROM picks
    ORDER BY updated_at DESC
    LIMIT ?
    """, (int(limit),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def summary() -> Dict[str, Any]:
    init_storage()
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) AS c FROM picks").fetchone()["c"]
    open_count = conn.execute("SELECT COUNT(*) AS c FROM picks WHERE status='OPEN'").fetchone()["c"]
    gpt_count = conn.execute("SELECT COUNT(*) AS c FROM gpt_analyses").fetchone()["c"]
    avg_conf = conn.execute("SELECT AVG(confidence) AS v FROM picks").fetchone()["v"]
    conn.close()
    return {
        "total_picks": int(total or 0),
        "open_picks": int(open_count or 0),
        "gpt_analyses": int(gpt_count or 0),
        "avg_confidence": round(float(avg_conf or 0), 2),
        "storage_mode": storage_mode(),
        "db_file": str(DB_FILE),
        "persistent": storage_mode() != "LOCAL_DATA_FALLBACK",
    }
