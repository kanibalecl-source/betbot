import sqlite3

from storage_paths import DATA_DIR

DATA_DIR.mkdir(exist_ok=True)
DB_FILE = DATA_DIR / "bot_tracker.sqlite3"


def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def _column_exists(conn, table, column):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in rows)


def _add_column_if_missing(conn, table, column, ddl):
    if not _column_exists(conn, table, column):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db():
    conn = get_conn()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS bets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pick_id TEXT,
        fixture_id TEXT,
        odds_event_id TEXT,
        created_at TEXT,
        match_name TEXT,
        league TEXT,
        home_team TEXT,
        away_team TEXT,
        match_date TEXT,
        market TEXT,
        bet_name TEXT,
        bookmaker TEXT,
        odds_api_market TEXT,
        closing_outcome_name TEXT,
        odds REAL,
        stake REAL,
        status TEXT DEFAULT 'OPEN',
        result TEXT DEFAULT 'PENDING',
        profit REAL DEFAULT 0,
        closing_odds REAL,
        clv REAL,
        edge REAL,
        ev REAL,
        probability REAL,
        risk_level TEXT,
        home_goals INTEGER,
        away_goals INTEGER,
        result_score TEXT,
        settlement_source TEXT,
        settled_at TEXT
    )
    """)

    # Future-proof migrations if user had older db.
    migrations = {
        "fixture_id": "TEXT",
        "odds_event_id": "TEXT",
        "home_team": "TEXT",
        "away_team": "TEXT",
        "match_date": "TEXT",
        "odds_api_market": "TEXT",
        "closing_outcome_name": "TEXT",
        "closing_odds": "REAL",
        "clv": "REAL",
        "risk_level": "TEXT",
        "home_goals": "INTEGER",
        "away_goals": "INTEGER",
        "result_score": "TEXT",
        "settlement_source": "TEXT",
        "settled_at": "TEXT",
    }

    for column, ddl in migrations.items():
        _add_column_if_missing(conn, "bets", column, ddl)

    conn.commit()
    conn.close()


def save_bet(pick, stake):
    init_db()
    conn = get_conn()

    conn.execute("""
    INSERT INTO bets (
        pick_id, fixture_id, odds_event_id, created_at, match_name, league,
        home_team, away_team, match_date, market, bet_name, bookmaker,
        odds_api_market, closing_outcome_name,
        odds, stake, edge, ev, probability, risk_level
    )
    VALUES (?, ?, ?, datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(pick.get("pick_id", "")),
        str(pick.get("fixture_id", "")),
        str(pick.get("odds_event_id", "")),
        str(pick.get("mecz", "")),
        str(pick.get("liga", "")),
        str(pick.get("home_team", "")),
        str(pick.get("away_team", "")),
        str(pick.get("match_date", "")),
        str(pick.get("market", "")),
        str(pick.get("typ", "")),
        str(pick.get("bookmaker", "")),
        str(pick.get("odds_api_market", "")),
        str(pick.get("closing_outcome_name", "")),
        float(pick.get("kurs_buk", 0)),
        float(stake),
        float(pick.get("edge", 0)),
        float(pick.get("ev", 0)),
        float(pick.get("prawd_final", 0)),
        str(pick.get("risk_level", "")),
    ))

    conn.commit()
    conn.close()


def list_bets(limit=500):
    init_db()
    conn = get_conn()
    rows = conn.execute("SELECT * FROM bets ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return rows
