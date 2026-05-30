from __future__ import annotations

from datetime import datetime

import pandas as pd

from api_results import get_match_result_by_id
from database import get_conn, init_db


MANUAL_MARKETS = [
    ("DOUBLE_1X", "1X"),
    ("DOUBLE_X2", "X2"),
    ("DOUBLE_12", "12"),
    ("BTTS_YES", "BTTS Yes"),
    ("BTTS_NO", "BTTS No"),
    ("OVER_0.5", "Over 0.5"),
    ("OVER_1.5", "Over 1.5"),
    ("OVER_2.5", "Over 2.5"),
    ("OVER_3.5", "Over 3.5"),
    ("OVER_4.5", "Over 4.5"),
    ("UNDER_0.5", "Under 0.5"),
    ("UNDER_1.5", "Under 1.5"),
    ("UNDER_2.5", "Under 2.5"),
    ("UNDER_3.5", "Under 3.5"),
    ("UNDER_4.5", "Under 4.5"),
]

MARKET_LABELS = dict(MANUAL_MARKETS)


def now_text() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def init_manual_db() -> None:
    init_db()
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS manual_bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            updated_at TEXT,
            fixture_id TEXT,
            odds_event_id TEXT,
            match_name TEXT,
            league TEXT,
            country TEXT,
            home_team TEXT,
            away_team TEXT,
            match_date TEXT,
            bot_market TEXT,
            bot_odds REAL,
            bot_edge REAL,
            bot_confidence REAL,
            manual_market TEXT,
            manual_market_label TEXT,
            odds REAL,
            stake REAL,
            bookmaker TEXT,
            note TEXT,
            status TEXT DEFAULT 'OPEN',
            result TEXT DEFAULT 'PENDING',
            home_goals INTEGER,
            away_goals INTEGER,
            score TEXT,
            profit REAL DEFAULT 0,
            roi REAL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS manual_ako_coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            updated_at TEXT,
            name TEXT,
            stake REAL,
            total_odds REAL,
            calculated_odds REAL,
            bookmaker TEXT,
            note TEXT,
            status TEXT DEFAULT 'OPEN',
            result TEXT DEFAULT 'PENDING',
            profit REAL DEFAULT 0,
            roi REAL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS manual_ako_legs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coupon_id INTEGER,
            fixture_id TEXT,
            odds_event_id TEXT,
            match_name TEXT,
            league TEXT,
            country TEXT,
            home_team TEXT,
            away_team TEXT,
            match_date TEXT,
            manual_market TEXT,
            manual_market_label TEXT,
            odds REAL,
            status TEXT DEFAULT 'OPEN',
            result TEXT DEFAULT 'PENDING',
            home_goals INTEGER,
            away_goals INTEGER,
            score TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def _pick_value(pick: dict, *keys, default=""):
    for key in keys:
        value = pick.get(key)
        if value not in (None, ""):
            return value
    return default


def _to_float(value, default=0.0) -> float:
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _pick_payload(pick: dict) -> dict:
    return {
        "fixture_id": str(_pick_value(pick, "fixture_id", "id")),
        "odds_event_id": str(_pick_value(pick, "odds_event_id", "event_id")),
        "match_name": str(_pick_value(pick, "mecz", "match")),
        "league": str(_pick_value(pick, "liga", "league")),
        "country": str(_pick_value(pick, "country")),
        "home_team": str(_pick_value(pick, "home_team", "home")),
        "away_team": str(_pick_value(pick, "away_team", "away")),
        "match_date": str(_pick_value(pick, "match_date", "date")),
        "bot_market": str(_pick_value(pick, "market", "typ")),
        "bot_odds": _to_float(_pick_value(pick, "kurs_buk", "odds")),
        "bot_edge": _to_float(_pick_value(pick, "edge")),
        "bot_confidence": _to_float(_pick_value(pick, "confidence", "prawd_final")),
    }


def add_manual_bet(
    pick: dict,
    manual_market: str,
    odds: float,
    stake: float,
    bookmaker: str = "",
    note: str = "",
) -> int:
    init_manual_db()
    market = str(manual_market or "").upper()
    if market not in MARKET_LABELS:
        raise ValueError("Nieznany rynek manualny")
    odds = _to_float(odds)
    stake = _to_float(stake)
    if odds <= 1:
        raise ValueError("Kurs musi byc wiekszy niz 1.00")
    if stake <= 0:
        raise ValueError("Stawka musi byc wieksza od 0")

    p = _pick_payload(pick)
    conn = get_conn()
    cur = conn.execute(
        """
        INSERT INTO manual_bets (
            created_at, updated_at, fixture_id, odds_event_id, match_name, league,
            country, home_team, away_team, match_date, bot_market, bot_odds,
            bot_edge, bot_confidence, manual_market, manual_market_label,
            odds, stake, bookmaker, note
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now_text(), now_text(), p["fixture_id"], p["odds_event_id"], p["match_name"],
            p["league"], p["country"], p["home_team"], p["away_team"], p["match_date"],
            p["bot_market"], p["bot_odds"], p["bot_edge"], p["bot_confidence"],
            market, MARKET_LABELS[market], odds, stake, str(bookmaker or ""), str(note or ""),
        ),
    )
    conn.commit()
    bet_id = int(cur.lastrowid)
    conn.close()
    return bet_id


def add_ako_coupon(
    legs: list[dict],
    stake: float,
    total_odds: float | None = None,
    name: str = "",
    bookmaker: str = "",
    note: str = "",
) -> int:
    init_manual_db()
    if len(legs) < 2:
        raise ValueError("Kupon AKO musi miec minimum 2 zdarzenia")
    stake = _to_float(stake)
    if stake <= 0:
        raise ValueError("Stawka kuponu musi byc wieksza od 0")

    calculated_odds = 1.0
    normalized = []
    for leg in legs:
        pick = leg.get("pick") or {}
        market = str(leg.get("manual_market") or "").upper()
        odds = _to_float(leg.get("odds"))
        if market not in MARKET_LABELS:
            raise ValueError("Nieznany rynek w kuponie AKO")
        if odds <= 1:
            raise ValueError("Kazdy kurs w kuponie AKO musi byc wiekszy niz 1.00")
        calculated_odds *= odds
        payload = _pick_payload(pick)
        payload.update({"manual_market": market, "manual_market_label": MARKET_LABELS[market], "odds": odds})
        normalized.append(payload)

    total_odds_value = _to_float(total_odds, calculated_odds)
    if total_odds_value <= 1:
        total_odds_value = calculated_odds

    conn = get_conn()
    cur = conn.execute(
        """
        INSERT INTO manual_ako_coupons (
            created_at, updated_at, name, stake, total_odds, calculated_odds,
            bookmaker, note
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now_text(), now_text(), str(name or "Kupon AKO"), stake,
            round(total_odds_value, 4), round(calculated_odds, 4),
            str(bookmaker or ""), str(note or ""),
        ),
    )
    coupon_id = int(cur.lastrowid)
    for payload in normalized:
        conn.execute(
            """
            INSERT INTO manual_ako_legs (
                coupon_id, fixture_id, odds_event_id, match_name, league, country,
                home_team, away_team, match_date, manual_market, manual_market_label, odds
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                coupon_id, payload["fixture_id"], payload["odds_event_id"], payload["match_name"],
                payload["league"], payload["country"], payload["home_team"], payload["away_team"],
                payload["match_date"], payload["manual_market"], payload["manual_market_label"],
                payload["odds"],
            ),
        )
    conn.commit()
    conn.close()
    return coupon_id


def evaluate_manual_market(market: str, home_goals: int, away_goals: int) -> bool | None:
    market = str(market or "").upper().replace(".", "_")
    hg = int(home_goals)
    ag = int(away_goals)
    total = hg + ag
    if market in {"DOUBLE_1X", "1X", "HOME_OR_DRAW"}:
        return hg >= ag
    if market in {"DOUBLE_X2", "X2", "AWAY_OR_DRAW"}:
        return ag >= hg
    if market in {"DOUBLE_12", "12", "HOME_OR_AWAY"}:
        return hg != ag
    if market == "BTTS_YES":
        return hg > 0 and ag > 0
    if market == "BTTS_NO":
        return hg == 0 or ag == 0
    if market.startswith("OVER_"):
        try:
            return total > float(market.split("_", 1)[1].replace("_", "."))
        except Exception:
            return None
    if market.startswith("UNDER_"):
        try:
            return total < float(market.split("_", 1)[1].replace("_", "."))
        except Exception:
            return None
    return None


def settle_manual_open_bets(limit: int = 300) -> int:
    init_manual_db()
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM manual_bets WHERE status='OPEN' AND fixture_id IS NOT NULL AND fixture_id != '' ORDER BY created_at ASC LIMIT ?",
        (limit,),
    ).fetchall()
    updated = 0
    for bet in rows:
        result = get_match_result_by_id(bet["fixture_id"])
        if not result or not result.get("finished"):
            continue
        home_goals = result.get("home_goals")
        away_goals = result.get("away_goals")
        won = evaluate_manual_market(bet["manual_market"], int(home_goals), int(away_goals))
        if won is None:
            continue
        stake = _to_float(bet["stake"])
        odds = _to_float(bet["odds"])
        profit = round(stake * (odds - 1), 2) if won else round(-stake, 2)
        roi = round((profit / stake) * 100, 2) if stake else 0
        conn.execute(
            """
            UPDATE manual_bets
            SET updated_at=?, status='CLOSED', result=?, home_goals=?, away_goals=?,
                score=?, profit=?, roi=?
            WHERE id=?
            """,
            (now_text(), "WIN" if won else "LOSS", int(home_goals), int(away_goals), f"{home_goals}:{away_goals}", profit, roi, bet["id"]),
        )
        updated += 1
    conn.commit()
    conn.close()
    return updated


def settle_ako_coupons(limit: int = 200) -> int:
    init_manual_db()
    conn = get_conn()
    coupons = conn.execute(
        "SELECT * FROM manual_ako_coupons WHERE status='OPEN' ORDER BY created_at ASC LIMIT ?",
        (limit,),
    ).fetchall()
    settled = 0
    for coupon in coupons:
        legs = conn.execute("SELECT * FROM manual_ako_legs WHERE coupon_id=? ORDER BY id ASC", (coupon["id"],)).fetchall()
        if not legs:
            continue
        any_pending = False
        any_lost = False
        all_won = True
        for leg in legs:
            if str(leg["status"]).upper() == "CLOSED":
                if str(leg["result"]).upper() != "WIN":
                    any_lost = True
                    all_won = False
                continue
            result = get_match_result_by_id(leg["fixture_id"])
            if not result or not result.get("finished"):
                any_pending = True
                all_won = False
                continue
            home_goals = int(result["home_goals"])
            away_goals = int(result["away_goals"])
            won = evaluate_manual_market(leg["manual_market"], home_goals, away_goals)
            if won is None:
                any_pending = True
                all_won = False
                continue
            conn.execute(
                """
                UPDATE manual_ako_legs
                SET status='CLOSED', result=?, home_goals=?, away_goals=?, score=?
                WHERE id=?
                """,
                ("WIN" if won else "LOSS", home_goals, away_goals, f"{home_goals}:{away_goals}", leg["id"]),
            )
            if won:
                pass
            else:
                any_lost = True
                all_won = False

        if any_pending:
            continue
        stake = _to_float(coupon["stake"])
        total_odds = _to_float(coupon["total_odds"])
        if any_lost:
            result_text = "LOSS"
            profit = round(-stake, 2)
        elif all_won:
            result_text = "WIN"
            profit = round(stake * (total_odds - 1), 2)
        else:
            continue
        roi = round((profit / stake) * 100, 2) if stake else 0
        conn.execute(
            """
            UPDATE manual_ako_coupons
            SET updated_at=?, status='CLOSED', result=?, profit=?, roi=?
            WHERE id=?
            """,
            (now_text(), result_text, profit, roi, coupon["id"]),
        )
        settled += 1
    conn.commit()
    conn.close()
    return settled


def settle_all_manual() -> dict:
    singles = settle_manual_open_bets()
    ako = settle_ako_coupons()
    return {"singles": singles, "ako": ako}


def manual_bets_dataframe(limit: int = 1000) -> pd.DataFrame:
    init_manual_db()
    conn = get_conn()
    rows = conn.execute("SELECT * FROM manual_bets ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return pd.DataFrame([dict(row) for row in rows])


def ako_coupons_dataframe(limit: int = 500) -> pd.DataFrame:
    init_manual_db()
    conn = get_conn()
    rows = conn.execute("SELECT * FROM manual_ako_coupons ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return pd.DataFrame([dict(row) for row in rows])


def ako_legs_dataframe(coupon_id: int | None = None) -> pd.DataFrame:
    init_manual_db()
    conn = get_conn()
    if coupon_id:
        rows = conn.execute("SELECT * FROM manual_ako_legs WHERE coupon_id=? ORDER BY id ASC", (coupon_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM manual_ako_legs ORDER BY id DESC").fetchall()
    conn.close()
    return pd.DataFrame([dict(row) for row in rows])


def manual_summary(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {"total": 0, "open": 0, "closed": 0, "wins": 0, "profit": 0.0, "stake": 0.0, "roi": 0.0, "winrate": 0.0}
    closed = df[df["status"].astype(str).str.upper() == "CLOSED"].copy()
    wins = int((closed["result"].astype(str).str.upper() == "WIN").sum()) if not closed.empty else 0
    stake_sum = float(pd.to_numeric(closed.get("stake"), errors="coerce").fillna(0).sum()) if not closed.empty else 0
    profit_sum = float(pd.to_numeric(closed.get("profit"), errors="coerce").fillna(0).sum()) if not closed.empty else 0
    closed_count = int(len(closed))
    return {
        "total": int(len(df)),
        "open": int((df["status"].astype(str).str.upper() == "OPEN").sum()),
        "closed": closed_count,
        "wins": wins,
        "profit": round(profit_sum, 2),
        "stake": round(stake_sum, 2),
        "roi": round((profit_sum / stake_sum) * 100, 2) if stake_sum else 0.0,
        "winrate": round((wins / closed_count) * 100, 2) if closed_count else 0.0,
    }


def grouped_manual_stats(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    if df is None or df.empty or group_col not in df.columns:
        return pd.DataFrame()
    closed = df[df["status"].astype(str).str.upper() == "CLOSED"].copy()
    if closed.empty:
        return pd.DataFrame()
    closed["stake_num"] = pd.to_numeric(closed["stake"], errors="coerce").fillna(0)
    closed["profit_num"] = pd.to_numeric(closed["profit"], errors="coerce").fillna(0)
    closed["win_num"] = (closed["result"].astype(str).str.upper() == "WIN").astype(int)
    grouped = closed.groupby(group_col, dropna=False).agg(
        bets=("id", "count"),
        wins=("win_num", "sum"),
        stake=("stake_num", "sum"),
        profit=("profit_num", "sum"),
    ).reset_index()
    grouped["winrate_%"] = (grouped["wins"] / grouped["bets"] * 100).round(2)
    grouped["roi_%"] = grouped.apply(lambda row: round((row["profit"] / row["stake"]) * 100, 2) if row["stake"] else 0.0, axis=1)
    grouped["profit"] = grouped["profit"].round(2)
    grouped["stake"] = grouped["stake"].round(2)
    return grouped.sort_values(["profit", "roi_%"], ascending=False)
