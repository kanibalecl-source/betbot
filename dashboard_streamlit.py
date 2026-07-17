import base64
import html
import json
import math
import os
from pathlib import Path
from typing import Iterable, List

import pandas as pd
import streamlit as st

try:
    from betbot.dashboard.data_service import read_csv_safe as modular_read_csv_safe
    from betbot.dashboard.data_service import normalize_streamlit_df as modular_streamlit_df
except Exception:
    modular_read_csv_safe = None
    modular_streamlit_df = None

try:
    from gpt_betting_assistant import render_gpt_chat_tab
except Exception:
    def render_gpt_chat_tab(picks=None, live=None, results=None):
        import streamlit as st
        st.warning("Moduł GPT nie został załadowany.")

try:
    from gpt_streamlit_panel import render_gpt_tab
except Exception:
    def render_gpt_tab(base_dir=None, *args, **kwargs):
        st.warning("Moduł GPT nie został załadowany.")


try:
    from auth_manager import require_login
except Exception:
    def require_login():
        return True


try:
    from manual_betting import (
        MANUAL_MARKETS, add_manual_bet, add_ako_coupon, ako_coupons_dataframe,
        ako_legs_dataframe, delete_ako_coupon, delete_manual_bet,
        grouped_manual_stats, manual_bets_dataframe,
        manual_summary, settle_all_manual,
    )
except Exception:
    MANUAL_MARKETS = []
    add_manual_bet = None
    add_ako_coupon = None
    ako_coupons_dataframe = None
    ako_legs_dataframe = None
    delete_ako_coupon = None
    delete_manual_bet = None
    grouped_manual_stats = None
    manual_bets_dataframe = None
    manual_summary = None
    settle_all_manual = None

st.set_page_config(page_title="KANIBAL ANALYTICS", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

BASE_DIR = Path(__file__).resolve().parent
try:
    from storage_paths import DATA_DIR
except Exception:
    DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
PICKS_FILE = DATA_DIR / "auto_all_picks.csv"
AI_PICKS_FILE = DATA_DIR / "ai_picks.csv"
LOW_AI_PICKS_FILE = DATA_DIR / "ai_low_picks.csv"
RISK_AI_PICKS_FILE = DATA_DIR / "ai_risk_picks.csv"
PICK_CANDIDATES = [DATA_DIR / "auto_all_picks.csv", BASE_DIR / "auto_all_picks.csv"]
LOW_PICK_CANDIDATES = [DATA_DIR / "auto_low_picks.csv", BASE_DIR / "auto_low_picks.csv"]
RISK_PICK_CANDIDATES = [DATA_DIR / "auto_risk_picks.csv", BASE_DIR / "auto_risk_picks.csv"]
LIVE_FILE = DATA_DIR / "live_matches.csv"
RESULTS_FILE = DATA_DIR / "results_history.csv"
HISTORY_FILE = DATA_DIR / "history.csv"
BANNER_FILE = BASE_DIR / "kanibal_banner.png"
CONFIG_FILE = BASE_DIR / "config_strategy.json"

DISPLAY_MARKETS = {
    "DOUBLE_1X": "1X", "DOUBLE_X2": "X2", "DOUBLE_12": "12",
    "BTTS_YES": "BTTS Tak", "BTTS_NO": "BTTS Nie",
    "OVER_0.5": "Over 0.5", "OVER_1.5": "Over 1.5", "OVER_2.5": "Over 2.5", "OVER_3.5": "Over 3.5", "OVER_4.5": "Over 4.5",
    "UNDER_0.5": "Under 0.5", "UNDER_1.5": "Under 1.5", "UNDER_2.5": "Under 2.5", "UNDER_3.5": "Under 3.5", "UNDER_4.5": "Under 4.5",
    "HOME_WIN": "Wygrana gospodarzy", "AWAY_WIN": "Wygrana gości", "DRAW": "Remis",
}
TARGET_MARKETS = set(DISPLAY_MARKETS)

DISPLAY_COLUMNS = {
    "created_at": "Data utworzenia",
    "updated_at": "Data aktualizacji",
    "written_at": "Data zapisu",
    "match_date": "Data meczu",
    "league": "Liga",
    "liga": "Liga",
    "match": "Mecz",
    "mecz": "Mecz",
    "match_name": "Mecz",
    "market": "Rynek",
    "typ": "Typ",
    "bet_name": "Nazwa zakładu",
    "manual_market_label": "Typ zakładu",
    "odds": "Kurs",
    "kurs_buk": "Kurs",
    "confidence": "Pewność",
    "advanced_confidence": "Pewność zaawansowana",
    "ai_pick_score": "Wynik AI",
    "edge": "Przewaga",
    "ev": "EV",
    "value": "Wartość",
    "stake": "Stawka",
    "status": "Status",
    "result": "Wynik",
    "profit": "Zysk",
    "roi": "ROI",
    "score": "Rezultat",
    "name": "Nazwa",
    "bookmaker": "Bukmacher",
    "coupon_id": "ID kuponu",
    "total_odds": "Kurs łączny",
    "calculated_odds": "Kurs wyliczony",
    "bets": "Zakłady",
    "wins": "Wygrane",
    "winrate": "Skuteczność",
    "event": "Zdarzenie",
    "payload_json": "Dane zdarzenia",
    "plik": "Plik",
    "risk": "Ryzyko",
    "risk_level": "Poziom ryzyka",
    "source": "Źródło",
    "liga_typ": "Liga i typ",
}


def read_csv_safe(path: Path) -> pd.DataFrame:
    if modular_read_csv_safe:
        try:
            return modular_read_csv_safe(path)
        except Exception:
            pass
    try:
        if path.exists() and path.stat().st_size > 0:
            return pd.read_csv(path)
    except Exception:
        try:
            return pd.read_csv(path, encoding="utf-8")
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def streamlit_df(df: pd.DataFrame) -> pd.DataFrame:
    if modular_streamlit_df:
        try:
            return modular_streamlit_df(df)
        except Exception:
            pass
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    text_cols = [
        "fixture_id", "odds_event_id", "pick_id", "id", "coupon_id",
        "home_id", "away_id", "league_id",
    ]
    for col in text_cols:
        if col in out.columns:
            out[col] = out[col].astype(str)
    for col in out.columns:
        if out[col].dtype == "object":
            out[col] = out[col].astype(str)
    out = out.rename(columns={col: DISPLAY_COLUMNS.get(col, col) for col in out.columns})
    return out


def first_existing(row, names: Iterable[str], default="-"):
    for name in names:
        try:
            value = row.get(name)
        except Exception:
            value = None
        if value is not None and pd.notna(value) and str(value).strip() != "":
            return value
    return default


def as_float(value, default: float = 0.0) -> float:
    try:
        value = pd.to_numeric(pd.Series([value]), errors="coerce").fillna(default).iloc[0]
        return float(value)
    except Exception:
        return float(default)


def numeric_series(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col in df.columns and len(df) > 0:
        return pd.to_numeric(df[col], errors="coerce").fillna(default)
    return pd.Series(dtype=float)


def pct(value) -> str:
    try:
        return f"{float(value):.1f}%"
    except Exception:
        return "0.0%"


def money(value) -> str:
    try:
        return f"{float(value):,.2f} zł".replace(",", " ")
    except Exception:
        return "0.00 zł"


def fmt_market(value) -> str:
    raw = str(value if value is not None else "").strip()
    return DISPLAY_MARKETS.get(raw.upper(), raw.replace("_", " ").title() if raw else "-")


def normalize_picks(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.copy()
    if "market" in out.columns:
        mask = out["market"].astype(str).str.upper().isin(TARGET_MARKETS)
        if mask.any():
            out = out[mask].copy()
    if "kurs_buk" in out.columns:
        odds = pd.to_numeric(out["kurs_buk"], errors="coerce")
        if odds.notna().any():
            out = out[(odds >= 1.00) & (odds <= 5.00)].copy()
    return out.reset_index(drop=True)


def load_strategy_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_strategy_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def filter_profile_options(cfg: dict) -> dict:
    profiles = cfg.get("filter_profiles") or {}
    if profiles:
        return profiles
    return {
        "safe": {"label": "Filtry Safe", "min_book_odds": 1.0, "max_book_odds": 2.5},
        "medium": {"label": "Filtry Medium", "min_book_odds": 1.0, "max_book_odds": 3.5},
        "risk": {"label": "Filtry ryzyka", "min_book_odds": 1.0, "max_book_odds": 5.0},
    }


def active_filter_profile(cfg: dict) -> str:
    active = str(cfg.get("active_filter_profile", "medium")).lower()
    profiles = filter_profile_options(cfg)
    return active if active in profiles else "medium"




def load_picks() -> pd.DataFrame:
    for path in PICK_CANDIDATES:
        df = read_csv_safe(path)
        if not df.empty:
            return df
    return pd.DataFrame()


def load_pick_candidates(paths) -> pd.DataFrame:
    for path in paths:
        df = read_csv_safe(path)
        if not df.empty:
            return df
    return pd.DataFrame()



def load_ai_picks(prematch: pd.DataFrame, path: Path = AI_PICKS_FILE, mode: str = "main") -> pd.DataFrame:
    """Load autonomous AI picks. If the file is missing, generate it once on demand."""
    df = read_csv_safe(path)
    if not df.empty:
        return df
    try:
        from ai_autonomous_picks_engine import run_once as run_ai_picks_once
        run_ai_picks_once(mode=mode)
        df = read_csv_safe(path)
        if not df.empty:
            return df
    except Exception:
        pass
    # Empty dataframe means AI has no independent signals yet; do not copy PREMATCH into AI.
    return pd.DataFrame()


def real_values(df: pd.DataFrame, columns: Iterable[str], limit: int = 10, default=None) -> List[float]:
    if default is None:
        default = []
    if df is None or df.empty:
        return list(default)
    for col in columns:
        if col in df.columns:
            values = pd.to_numeric(df[col], errors="coerce").dropna().astype(float).tolist()
            if values:
                return values[-limit:]
    return list(default)

def group_counts(df: pd.DataFrame, columns: Iterable[str], limit: int = 10) -> List[float]:
    if df is None or df.empty:
        return []
    for col in columns:
        if col in df.columns:
            counts = df[col].astype(str).replace({"": "-"}).value_counts().head(limit).astype(float).tolist()
            if counts:
                return counts
    return []

def bucket_counts(series: pd.Series, bins=None) -> List[float]:
    if bins is None:
        bins = [0, 50, 60, 70, 80, 90, 101]
    if series is None or len(series) == 0:
        return []
    vals = pd.to_numeric(series, errors="coerce").dropna()
    if vals.empty:
        return []
    return pd.cut(vals, bins=bins, include_lowest=True).value_counts(sort=False).astype(float).tolist()

def safe_heights(values: List[float]) -> List[float]:
    vals = [float(v) for v in values if pd.notna(v)]
    if not vals:
        return [0] * 10
    if len(vals) < 10:
        vals = ([vals[0]] * (10 - len(vals))) + vals
    vals = vals[-10:]
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return [55 if hi else 0 for _ in vals]
    return [max(8, min(100, 18 + ((v - lo) / (hi - lo)) * 82)) for v in vals]


def _chart_status(values: List[float]) -> str:
    vals = [float(v) for v in values if pd.notna(v)]
    if not vals:
        return "NO DATA"
    avg = sum(vals) / len(vals)
    if avg > 65:
        return "STRONG EDGE"
    if avg > 45:
        return "NEUTRAL"
    return "WATCH"

def _chart_insight(title: str, values: List[float], subtitle: str = "") -> str:
    vals = [float(v) for v in values if pd.notna(v)]
    if not vals:
        return "Brak danych wejściowych. Wykres jest gotowy i automatycznie uzupełni się po pojawieniu się danych w systemie."
    avg = sum(vals) / len(vals)
    hi = max(vals)
    lo = min(vals)
    trend = vals[-1] - vals[0] if len(vals) > 1 else 0
    direction = "rosnący" if trend > 0 else "spadkowy" if trend < 0 else "stabilny"
    return f"Średnia wartość wynosi {avg:.2f}. Zakres danych: {lo:.2f} - {hi:.2f}. Trend końcowy jest {direction}. AI wykorzystuje ten wykres do oceny jakości sygnałów, stabilności wartości oraz ryzyka rynkowego."

def _chart_axis_labels(title: str):
    t = str(title).lower()
    if "roi" in t:
        return "SEGMENT / LIGA / OKRES", "ROI / PROFITABILITY"
    if "win" in t or "skutecz" in t:
        return "PEWNOŚĆ / SEGMENT RYNKU", "SKUTECZNOŚĆ"
    if "confidence" in t or "pewno" in t:
        return "SEGMENT PEWNOŚCI", "SIŁA SYGNAŁU"
    if "risk" in t or "ryzyk" in t:
        return "SEGMENT RYZYKA", "EKSPOZYCJA NA RYZYKO"
    if "value" in t or "ev" in t:
        return "VALUE SEGMENT", "EV / EDGE"
    if "live" in t:
        return "LIVE SEGMENT", "LIVE PRESSURE"
    return "SEGMENT", "VALUE"

def chart_html(title: str, values: List[float], subtitle: str = "Dane z systemu") -> str:
    vals = [float(v) for v in values if pd.notna(v)]
    heights = safe_heights(vals)
    status = _chart_status(vals)
    insight = _chart_insight(title, vals, subtitle)
    avg = (sum(vals) / len(vals)) if vals else 0
    sample = len(vals)
    maxv = max(vals) if vals else 0
    x_title, y_title = _chart_axis_labels(title)

    bars = ""
    for i, h in enumerate(heights):
        val = vals[i - len(heights)] if vals and i >= len(heights) - len(vals) else 0
        color = "#7CFF2B" if val >= 0 else "#ff4d4d"
        bars += (
            f'<i title="Segment P{i+1} | {y_title}: {val:.2f} | Benchmark: {avg:.2f}" '
            f'style="height:{h:.0f}%;background:linear-gradient(180deg,{color},rgba(124,255,43,.10));"></i>'
        )

    return (
        f'<div class="pro-chart-card">'
        f'<div class="pro-chart-head">'
        f'<div><div class="pro-chart-title">{title}</div>'
        f'<div class="pro-chart-subtitle">{subtitle}. Oś X: {x_title}. Oś Y: {y_title}. Punkt odniesienia pokazuje średnią wartość serii.</div></div>'
        f'<div class="pro-chart-badge">{status}</div>'
        f'</div>'
        f'<div class="placeholder-bars" style="height:210px;position:relative">{bars}'
        f'<span style="position:absolute;left:10px;right:10px;bottom:{max(8,min(92,55))}%;border-top:1px dashed rgba(255,255,255,.38);"></span>'
        f'</div>'
        f'<div class="pro-chart-meta">'
        f'<div><strong>Punkt odniesienia</strong>Średnia: {avg:.2f}</div>'
        f'<div><strong>Próba</strong>Liczba punktów: {sample}</div>'
        f'<div><strong>Peak value</strong>Maksimum: {maxv:.2f}</div>'
        f'</div>'
        f'<div class="pro-chart-insight"><b>AI insight:</b> {insight}</div>'
        f'</div>'
    )

def chart_card(title: str, values: List[float], subtitle: str = "Dane z systemu") -> str:
    return chart_html(title, values, subtitle)


def pick_confidence_values(picks: pd.DataFrame) -> List[float]:
    return real_values(picks, ["confidence", "advanced_confidence", "ai_pick_score", "score"], default=group_counts(picks, ["league", "liga", "market", "typ"]))

def pick_value_values(picks: pd.DataFrame) -> List[float]:
    return real_values(picks, ["ev", "edge", "value", "ai_value", "kurs_buk", "odds"], default=pick_confidence_values(picks))

def result_roi_values(results: pd.DataFrame) -> List[float]:
    return real_values(results, ["roi", "profit", "zysk"], default=group_counts(results, ["result", "league", "market"]))

def winrate_values(results: pd.DataFrame, picks: pd.DataFrame) -> List[float]:
    if results is not None and not results.empty and "result" in results.columns:
        r = results["result"].astype(str).str.lower()
        mapped = r.map(lambda x: 100 if any(w in x for w in ["win", "won", "wygr", "1", "true"]) else 0)
        return mapped.rolling(5, min_periods=1).mean().tolist()[-10:]
    return pick_confidence_values(picks)

def hour_values(df: pd.DataFrame) -> List[float]:
    if df is None or df.empty:
        return []
    for col in ["timestamp", "date", "match_date", "settled_at"]:
        if col in df.columns:
            dt = pd.to_datetime(df[col], errors="coerce")
            vals = dt.dropna().dt.hour.value_counts().sort_index().astype(float).tolist()
            if vals:
                return vals
    return group_counts(df, ["league", "market", "typ"])

def ensure_live_file() -> None:
    cols = [
        "fixture_id", "league", "match", "home", "away", "minute", "score", "status",
        "signal", "signal_verified", "confidence", "odds", "odds_market", "odds_bookmaker",
        "odds_verified", "value", "ev", "risk", "source", "data_status", "updated_at",
    ]
    if not LIVE_FILE.exists():
        pd.DataFrame(columns=cols).to_csv(LIVE_FILE, index=False)



def load_live_data(picks: pd.DataFrame) -> pd.DataFrame:
    # LIVE never falls back to prematch data. Only verified, fresh provider rows are displayed.
    ensure_live_file()
    live = read_csv_safe(LIVE_FILE)
    if live.empty:
        return live

    required = {"fixture_id", "league", "match", "minute", "score", "status", "source", "data_status", "updated_at"}
    if not required.issubset(live.columns):
        return pd.DataFrame(columns=live.columns)

    status = live["status"].astype(str).str.upper().str.strip()
    active = status.isin({"1H", "2H", "HT", "ET", "BT", "P", "LIVE", "INT", "SUSP"})
    verified = live["data_status"].astype(str).str.startswith("VERIFIED_FIXTURE")
    real_source = live["source"].astype(str).str.startswith("API-Football")
    updated = pd.to_datetime(live["updated_at"], errors="coerce", utc=True)
    max_age = max(60, int(os.getenv("LIVE_MAX_AGE_SECONDS", "900")))
    fresh = updated.notna() & ((pd.Timestamp.now(tz="UTC") - updated).dt.total_seconds() <= max_age)

    result = live.loc[active & verified & real_source & fresh].copy()
    if result.empty:
        return result
    result["_updated_dt"] = updated.loc[result.index]
    return result.sort_values(["_updated_dt", "minute"], ascending=[False, False])


def load_results() -> pd.DataFrame:
    frames = []
    archive_files = [
        DATA_DIR / "auto_all_picks_history.csv",
        DATA_DIR / "auto_low_picks_history.csv",
        DATA_DIR / "auto_risk_picks_history.csv",
    ]
    for path in archive_files:
        df = read_csv_safe(path)
        if df.empty:
            continue
        df = df.copy()
        df["record_source"] = path.name
        if "league" not in df.columns and "liga" in df.columns:
            df["league"] = df["liga"]
        if "match_name" not in df.columns:
            df["match_name"] = df["match"] if "match" in df.columns else df.get("mecz", "")
        if "market" not in df.columns and "typ" in df.columns:
            df["market"] = df["typ"]
        if "odds" not in df.columns and "kurs_buk" in df.columns:
            df["odds"] = df["kurs_buk"]
        if "fixture_status" not in df.columns and "status" in df.columns:
            df["fixture_status"] = df["status"]
        df["status"] = "OPEN"
        df["result"] = "PENDING"
        frames.append(df)
    for path in [RESULTS_FILE, HISTORY_FILE, BASE_DIR / "results_history.csv", BASE_DIR / "history.csv"]:
        df = read_csv_safe(path)
        if not df.empty:
            df = df.copy()
            df["record_source"] = path.name
            frames.append(df)
    try:
        from agi_storage import load_history_dataframe
        storage_df = load_history_dataframe()
        if storage_df is not None and not storage_df.empty:
            storage_df = storage_df.copy()
            storage_df["record_source"] = "kanibal_persistent.sqlite3"
            frames.append(storage_df)
    except Exception:
        pass
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True, sort=False)

    def history_key(row) -> str:
        for name in ("pick_key", "pick_id", "ai_id"):
            value = str(first_existing(row, [name], "")).strip()
            if value:
                return f"{name}:{value}"
        fixture = str(first_existing(row, ["fixture_id"], "")).strip()
        market = str(first_existing(row, ["market", "typ", "bet_name"], "")).strip().upper()
        odds = str(first_existing(row, ["odds", "kurs_buk"], "")).strip()
        if fixture and market:
            return f"fixture:{fixture}|market:{market}|odds:{odds}"
        return f"row:{row.name}"

    combined["_history_key"] = combined.apply(history_key, axis=1)
    combined = combined.drop_duplicates(subset=["_history_key"], keep="last")
    return combined.drop(columns=["_history_key"]).reset_index(drop=True)


def b64_image(path: Path) -> str:
    try:
        return base64.b64encode(path.read_bytes()).decode("utf-8")
    except Exception:
        return ""


def css() -> None:
    st.markdown('''
<style>
:root{--bg:#05080a;--panel:#0a0f13;--line:rgba(255,255,255,.10);--green:#7CFF2B;--yellow:#ffc400;--red:#ff3b30;--blue:#10a8ff;--muted:#8f9aa5;--white:#f7fbf4;}
html,body,.stApp{background:radial-gradient(circle at 9% 5%,rgba(255,85,0,.10),transparent 28%),radial-gradient(circle at 88% 7%,rgba(98,255,0,.16),transparent 30%),linear-gradient(180deg,#050607 0%,#060a08 45%,#030405 100%)!important;color:var(--white)!important;font-family:Inter,Arial,sans-serif!important;}
header[data-testid="stHeader"]{background:transparent!important}div[data-testid="stToolbar"],#MainMenu,footer{display:none!important}.block-container{max-width:1920px!important;padding:.35rem .75rem 1.0rem!important}.kanibal-hero{width:100%;margin:0 0 18px;border:1px solid rgba(124,255,43,.22);border-radius:18px;overflow:hidden;background:#050607}.kanibal-hero img{display:block;width:100%;height:auto;object-fit:contain;object-position:center}.kanibal-fallback{height:210px;border:1px solid rgba(124,255,43,.22);border-radius:18px;display:flex;align-items:center;justify-content:center;font-size:52px;font-weight:950;color:#fff;background:linear-gradient(90deg,#050607,#0a1a0c)}
.stTabs [data-baseweb="tab-list"]{gap:0;background:#070a0d;border:1px solid var(--line);border-radius:12px;overflow:hidden;width:100%;margin:0 0 18px}.stTabs [data-baseweb="tab"]{height:58px;flex-grow:1;background:#070a0d;border-right:1px solid rgba(255,255,255,.08);color:#fff!important;font-size:13px;font-weight:900;text-transform:uppercase;letter-spacing:.02em}.stTabs [aria-selected="true"]{background:linear-gradient(180deg,rgba(124,255,43,.20),rgba(124,255,43,.055))!important;color:var(--green)!important;border-bottom:3px solid var(--green)!important}.stTabs [data-baseweb="tab-highlight"]{display:none}.ka-title{display:flex;align-items:center;gap:14px;font-size:34px;font-weight:950;line-height:1;color:#fff;text-shadow:0 2px 0 #000;margin:26px 0 22px}.ka-dot{width:28px;height:28px;border-radius:50%;background:radial-gradient(circle at 35% 30%,#caffdb,#1bd257 62%,#064e22);box-shadow:0 0 22px rgba(124,255,43,.65);display:inline-block}.ka-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px;margin:0 0 14px}.ka-card{background:linear-gradient(180deg,rgba(255,255,255,.044),rgba(255,255,255,.016));border:1px solid var(--line);border-radius:14px;padding:17px;box-shadow:0 16px 36px rgba(0,0,0,.34)}.ka-card h3{font-size:18px;margin:0 0 14px;color:#fff!important;font-weight:950}.ka-label{font-size:11px;color:#a0a9b3;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px}.ka-value{font-size:29px;font-weight:950;color:#fff;line-height:1}.ka-sub{font-size:12px;color:var(--green);font-weight:800;margin-top:8px}.ka-panel{background:linear-gradient(180deg,rgba(255,255,255,.038),rgba(255,255,255,.014));border:1px solid var(--line);border-radius:14px;padding:18px;box-shadow:0 18px 40px rgba(0,0,0,.34);height:auto;box-sizing:border-box}.ka-layout{display:grid;grid-template-columns:1.15fr .85fr;gap:14px;margin-bottom:14px}.ka-bottom{display:grid;grid-template-columns:1.05fr .75fr .85fr;gap:14px;margin-top:14px;clear:both}.live-layout{display:grid;grid-template-columns:1.38fr 1fr;gap:14px;align-items:start;margin-bottom:14px}.ai-detail{margin-top:14px;background:linear-gradient(180deg,rgba(124,255,43,.055),rgba(255,255,255,.018));border:1px solid rgba(124,255,43,.16);border-radius:14px;padding:16px}.status-link{text-decoration:none!important}.ai-head,.ai-row{display:grid;grid-template-columns:1.05fr 3.05fr 1.25fr .9fr 1.55fr 1.15fr 1.25fr;gap:0;align-items:center}.ai-head{background:rgba(255,255,255,.026);border-bottom:1px solid var(--line);color:#a6b0b9;text-transform:uppercase;font-size:12px;font-weight:950}.ai-head div{padding:12px 10px}.ai-row{background:rgba(2,6,8,.50);border-bottom:1px solid rgba(255,255,255,.065);font-size:14px}.ai-row:hover{background:rgba(124,255,43,.035)}.ai-row div{padding:13px 10px}.ai-status-wrap div[data-testid="stButton"] button{background:rgba(124,255,43,.10)!important;color:var(--green)!important;border:1px solid rgba(124,255,43,.20)!important;border-radius:7px!important;font-size:12px!important;font-weight:950!important;min-height:34px!important;padding:5px 10px!important;width:auto!important}.ai-status-wrap div[data-testid="stButton"] button:hover{background:rgba(124,255,43,.18)!important;border-color:rgba(124,255,43,.42)!important;color:#fff!important}.ai-details-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.ai-detail-title{font-size:20px;font-weight:950;margin-bottom:12px;color:#fff}.ai-reason{background:rgba(2,6,8,.40);border:1px solid rgba(255,255,255,.08);border-radius:12px;padding:14px;margin-top:14px}.ka-two{display:grid;grid-template-columns:1fr 1fr;gap:14px}.ka-three{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}.ka-table{width:100%;border-collapse:collapse;color:#fff!important;font-size:14px}.ka-table th{background:rgba(255,255,255,.024);padding:12px 10px;text-transform:uppercase;color:#a6b0b9;font-size:12px;font-weight:900;border-bottom:1px solid var(--line);text-align:left}.ka-table td{padding:13px 10px;border-bottom:1px solid rgba(255,255,255,.065);background:rgba(2,6,8,.50);vertical-align:middle}.ka-table tr:hover td{background:rgba(124,255,43,.035)}.green{color:var(--green)!important;font-weight:950}.yellow{color:var(--yellow)!important;font-weight:950}.red{color:var(--red)!important;font-weight:950}.blue{color:var(--blue)!important;font-weight:850}.pill{display:inline-block;padding:6px 10px;border-radius:7px;font-size:12px;font-weight:950}.pill-green{background:rgba(124,255,43,.10);color:var(--green)}.pill-yellow{background:rgba(255,196,0,.14);color:var(--yellow)}.pill-red{background:rgba(255,59,48,.14);color:var(--red)}.progress{height:8px;background:#30373c;border-radius:12px;overflow:hidden;min-width:88px}.progress span{height:100%;display:block;background:linear-gradient(90deg,#4fd62a,#9eff28);border-radius:12px}.placeholder-bars{height:175px;display:flex;align-items:end;gap:10px;padding:15px 8px 0;background:linear-gradient(180deg,rgba(124,255,43,.05),rgba(124,255,43,.015));border-radius:10px;border:1px solid rgba(255,255,255,.055)}.placeholder-bars i{flex:1;background:linear-gradient(180deg,var(--green),rgba(124,255,43,.10));border-radius:6px 6px 0 0;box-shadow:0 0 15px rgba(124,255,43,.20)}.sparkline{height:68px;border-bottom:1px solid rgba(255,255,255,.12);background:linear-gradient(180deg,rgba(124,255,43,.12),rgba(124,255,43,.02));clip-path:polygon(0 80%,12% 70%,25% 65%,37% 48%,50% 52%,62% 36%,75% 43%,88% 20%,100% 8%,100% 100%,0 100%)}.footer-ka{display:flex;justify-content:space-between;color:#7d858b;font-size:12px;padding:18px 8px 8px}.status-dot{display:inline-block;width:8px;height:8px;background:var(--green);border-radius:50%;box-shadow:0 0 12px var(--green);margin-left:8px}@media(max-width:1100px){.ka-grid,.ka-layout,.ka-bottom,.ka-two,.ka-three{grid-template-columns:1fr}.stTabs [data-baseweb="tab"]{font-size:11px;height:52px}.ka-title{font-size:28px}}

/* === AI TABLE 1:1 FINAL === */
.ai-table-final{width:100%;background:linear-gradient(180deg,rgba(8,13,22,.98),rgba(3,7,13,.99));border:1px solid rgba(124,255,43,.22);border-radius:18px;overflow:hidden;box-shadow:0 0 28px rgba(124,255,43,.06);margin:0 0 14px}
.ai-table-final-head,.ai-table-final-row{display:grid;grid-template-columns:.90fr 1.58fr .86fr .58fr 1.05fr .84fr .96fr;align-items:center}
.ai-table-final-head{min-height:48px;background:rgba(124,255,43,.075);border-bottom:1px solid rgba(124,255,43,.18);color:#7CFF2B;font-size:12px;font-weight:950;letter-spacing:.09em;text-transform:uppercase}
.ai-table-final-head div,.ai-table-final-row div{padding:0 14px}
.ai-table-final-row{min-height:68px;background:rgba(7,12,20,.84);border-bottom:1px solid rgba(255,255,255,.055);color:#eef9f0;font-size:14px;font-weight:700}
.ai-table-final-row:hover{background:rgba(10,18,27,.98);box-shadow:inset 0 0 0 1px rgba(124,255,43,.10)}
.ai-cell-main{color:#fff;font-weight:950;font-size:15px;line-height:1.15}
.ai-cell-sub{display:block;margin-top:4px;color:#8d9b95;font-size:11px;font-weight:750;letter-spacing:.05em}
.ai-cell-num{color:#f7fff7;font-weight:950}
.ai-edge-plus{color:#7CFF2B;font-weight:950}
.ai-conf-line{display:flex;align-items:center;gap:10px}
.ai-conf-value{min-width:36px;color:#fff;font-weight:950}
.ai-conf-track{height:8px;min-width:78px;max-width:104px;width:100%;border-radius:999px;background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.06);overflow:hidden}
.ai-conf-fill{height:100%;border-radius:999px;background:linear-gradient(90deg,#7CFF2B,#ffc400);box-shadow:0 0 12px rgba(124,255,43,.28)}
.ai-status-col .stButton>button{width:100%!important;border-radius:999px!important;background:linear-gradient(180deg,rgba(124,255,43,.20),rgba(25,95,30,.24))!important;border:1px solid rgba(124,255,43,.42)!important;color:#B8FF7A!important;font-size:12px!important;font-weight:950!important;letter-spacing:.08em!important;text-transform:uppercase!important;box-shadow:0 0 18px rgba(124,255,43,.12)!important;padding:9px 10px!important}
.ai-status-col .stButton>button:hover{color:#fff!important;background:linear-gradient(180deg,rgba(124,255,43,.32),rgba(35,120,42,.30))!important;box-shadow:0 0 24px rgba(124,255,43,.22)!important}
.ai-status-inline{
display:inline-flex;
align-items:center;
justify-content:center;
min-width:92px;
height:36px;
border-radius:10px;
background:#1b2026;
border:1px solid rgba(255,255,255,.08);
color:#ffffff;
font-size:12px;
font-weight:900;
letter-spacing:.05em;
text-transform:uppercase;
margin-left:auto;
}
.ai-detail-final{background:linear-gradient(180deg,rgba(8,13,22,.99),rgba(3,7,13,.99));border:1px solid rgba(124,255,43,.20);border-radius:18px;padding:18px;margin:0 0 18px;box-shadow:0 0 28px rgba(124,255,43,.06)}
.ai-detail-final-title{color:#7CFF2B;font-size:16px;font-weight:950;letter-spacing:.10em;text-transform:uppercase;margin-bottom:14px}
.ai-detail-final-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.ai-detail-final-box{border-radius:14px;background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.07);padding:14px}
.ai-detail-final-label{color:#8d9b95;font-size:11px;font-weight:950;letter-spacing:.09em;text-transform:uppercase;margin-bottom:8px}
.ai-detail-final-value{color:#fff;font-size:18px;font-weight:950}
.ai-detail-final-note{color:#a7b8af;font-size:12px;line-height:1.45;font-weight:650;margin-top:14px}
@media(max-width:900px){.ai-table-final-head{display:none}.ai-table-final-row{grid-template-columns:1fr;gap:6px;padding:12px 0}.ai-table-final-row div{padding:4px 14px}.ai-detail-final-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}


.ai-status-text{
display:flex;
align-items:center;
justify-content:center;
width:120px;
height:42px;
margin:0 auto;
border-radius:14px;
background:#1b2026;
border:1px solid rgba(255,255,255,.08);
color:#ffffff;
font-size:12px;
font-weight:950;
letter-spacing:.08em;
text-transform:uppercase;
}

.ai-status-text:contains("PERFECT"){
color:#7CFF2B;
}

.ai-status-text:contains("NORMAL"){
color:#ffd24a;
}

.ai-status-text:contains("RISK"){
color:#ff6262;
}


/* === POPRAWKA: AI WARTOSC I SZCZEGOLY === */
.ai-detail-final{
background:linear-gradient(180deg,rgba(8,13,22,.99),rgba(3,7,13,.99))!important;
border:1px solid rgba(124,255,43,.18)!important;
border-radius:18px!important;
padding:16px!important;
margin:10px 0 18px!important;
box-shadow:0 0 28px rgba(124,255,43,.05)!important;
}
.ai-detail-final-grid{
display:grid!important;
grid-template-columns:repeat(3,minmax(0,1fr))!important;
gap:16px!important;
}
.ai-detail-final-box{
background:linear-gradient(180deg,rgba(255,255,255,.035),rgba(255,255,255,.014))!important;
border:1px solid rgba(124,255,43,.16)!important;
border-radius:14px!important;
padding:18px!important;
min-height:145px!important;
box-shadow:inset 0 0 0 1px rgba(255,255,255,.015)!important;
}
.ai-detail-final-title{
color:#7CFF2B!important;
font-size:20px!important;
font-weight:950!important;
letter-spacing:.02em!important;
text-transform:uppercase!important;
margin:0 0 18px 0!important;
}
.ai-engine-line{
color:#f6fff6!important;
font-size:14px!important;
font-weight:800!important;
line-height:1.7!important;
}
.ai-engine-line b{
color:#ffffff!important;
font-weight:950!important;
}
.ai-status-inline{
background:#1b2026!important;
border:1px solid rgba(255,255,255,.08)!important;
color:#ffffff!important;
}
@media(max-width:1100px){
.ai-detail-final-grid{grid-template-columns:1fr!important;}
}


/* === PROFESSIONAL CHART SYSTEM === */
.pro-chart-card{
background:linear-gradient(180deg,rgba(9,15,24,.98),rgba(4,8,14,.99));
border:1px solid rgba(124,255,43,.16);
border-radius:18px;
padding:18px 18px 12px;
margin-bottom:16px;
box-shadow:0 18px 42px rgba(0,0,0,.32),0 0 28px rgba(124,255,43,.045);
}
.pro-chart-head{
display:flex;
align-items:flex-start;
justify-content:space-between;
gap:14px;
margin-bottom:12px;
}
.pro-chart-title{
color:#fff;
font-size:17px;
font-weight:950;
letter-spacing:.04em;
text-transform:uppercase;
line-height:1.2;
}
.pro-chart-subtitle{
color:#91a099;
font-size:12px;
font-weight:700;
line-height:1.45;
margin-top:5px;
}
.pro-chart-badge{
white-space:nowrap;
display:inline-flex;
align-items:center;
justify-content:center;
min-width:96px;
height:32px;
padding:0 12px;
border-radius:999px;
background:rgba(124,255,43,.09);
border:1px solid rgba(124,255,43,.18);
color:#7CFF2B;
font-size:11px;
font-weight:950;
letter-spacing:.08em;
text-transform:uppercase;
}
.pro-chart-insight{
margin-top:10px;
padding:12px 14px;
border-radius:12px;
background:rgba(255,255,255,.026);
border:1px solid rgba(255,255,255,.065);
color:#aebbb4;
font-size:12px;
font-weight:700;
line-height:1.45;
}
.pro-chart-insight b{
color:#7CFF2B;
}
.pro-chart-meta{
display:grid;
grid-template-columns:repeat(3,minmax(0,1fr));
gap:10px;
margin-top:10px;
}
.pro-chart-meta div{
padding:9px 11px;
border-radius:10px;
background:rgba(0,0,0,.18);
border:1px solid rgba(255,255,255,.055);
color:#8fa099;
font-size:11px;
font-weight:800;
line-height:1.35;
}
.pro-chart-meta strong{
display:block;
color:#fff;
font-size:12px;
font-weight:950;
margin-bottom:3px;
}
@media(max-width:900px){
.pro-chart-head{display:block}
.pro-chart-badge{margin-top:10px}
.pro-chart-meta{grid-template-columns:1fr}
}


/* === PROFESSIONAL VISUAL CHART UPGRADE === */
.pro-chart-card{
backdrop-filter:blur(12px)!important;
position:relative!important;
overflow:hidden!important;
box-shadow:0 18px 44px rgba(0,0,0,.34),0 0 28px rgba(124,255,43,.06)!important;
}

.pro-chart-card:before{
content:'';
position:absolute;
top:0;
left:0;
right:0;
height:1px;
background:linear-gradient(90deg,transparent,rgba(124,255,43,.7),transparent);
}

.placeholder-bars{
display:flex!important;
align-items:flex-end!important;
gap:12px!important;
height:220px!important;
padding:22px 12px 14px!important;
border-radius:16px!important;
background:
linear-gradient(180deg,rgba(9,16,24,.98),rgba(4,8,14,.99))!important;
border:1px solid rgba(124,255,43,.10)!important;
overflow:hidden!important;
}

.placeholder-bars i{
flex:1!important;
min-width:16px!important;
border-radius:14px 14px 4px 4px!important;
box-shadow:0 0 16px rgba(124,255,43,.24)!important;
transition:all .25s ease!important;
position:relative!important;
}

.placeholder-bars i:hover{
transform:translateY(-6px)!important;
filter:brightness(1.12)!important;
}

.placeholder-bars i:after{
content:''!important;
position:absolute!important;
left:0!important;
right:0!important;
top:0!important;
height:35%!important;
background:linear-gradient(180deg,rgba(255,255,255,.22),transparent)!important;
border-radius:14px 14px 0 0!important;
}

.pro-chart-title{
font-size:18px!important;
}

.pro-chart-subtitle{
font-size:12px!important;
line-height:1.5!important;
}

.pro-chart-insight{
font-size:12px!important;
line-height:1.55!important;
}



/* === ETAP 5 PROFESSIONAL WWW DESIGN === */
.block-container{max-width:1680px!important;padding:.85rem 1.15rem 1.4rem!important;}
.ka-page-banner{position:relative;width:100%;min-height:260px;border:1px solid rgba(124,255,43,.20);border-radius:18px;overflow:hidden;background:#050607;margin:4px 0 18px;box-shadow:0 20px 70px rgba(0,0,0,.38)}
.ka-page-banner img{display:block;width:100%;height:270px;object-fit:cover;object-position:center;opacity:.92;filter:saturate(1.04) contrast(1.04)}
.ka-page-banner:after{content:"";position:absolute;inset:0;background:linear-gradient(90deg,rgba(0,0,0,.84),rgba(0,0,0,.30) 58%,rgba(0,0,0,.70));pointer-events:none}
.ka-page-banner-content{position:absolute;inset:0;z-index:2;padding:34px 38px;display:flex;flex-direction:column;justify-content:flex-end}
.ka-page-eyebrow{color:var(--green);font-size:12px;font-weight:950;text-transform:uppercase;letter-spacing:.18em;margin-bottom:12px}
.ka-page-banner h1{font-size:44px;line-height:1;margin:0 0 10px;font-weight:1000;letter-spacing:0;text-transform:uppercase;color:#fff;text-shadow:0 3px 0 #000}
.ka-page-banner p{font-size:15px;line-height:1.55;color:#d7e3d9;margin:0;max-width:860px;font-weight:750}
.ka-mini-banner{position:relative;min-height:145px;border:1px solid rgba(124,255,43,.16);border-radius:14px;overflow:hidden;background:#050607;margin:0 0 14px}
.ka-mini-banner img{width:100%;height:150px;object-fit:cover;object-position:center;opacity:.72;display:block}
.ka-mini-banner:after{content:"";position:absolute;inset:0;background:linear-gradient(90deg,rgba(0,0,0,.86),rgba(0,0,0,.38));pointer-events:none}
.ka-mini-banner-content{position:absolute;inset:0;z-index:2;padding:22px 24px;display:flex;flex-direction:column;justify-content:flex-end}
.ka-mini-banner h2{font-size:26px!important;margin:0 0 6px!important;color:#fff!important;font-weight:1000!important;text-transform:uppercase!important;letter-spacing:0!important}
.ka-mini-banner p{font-size:13px;color:#d7e3d9;margin:0;max-width:780px;font-weight:750;line-height:1.45}
.ka-title{font-size:30px;margin:18px 0 16px;}
.ka-card,.ka-panel{border-radius:12px!important;background:linear-gradient(180deg,rgba(255,255,255,.044),rgba(255,255,255,.016))!important;box-shadow:0 16px 36px rgba(0,0,0,.34)!important;}
.ka-grid{gap:14px;margin:0 0 14px;}
.ka-table th{font-size:11px;letter-spacing:.06em;}
.ka-table td{font-size:13px;}
.stTabs [data-baseweb="tab-list"]{border-radius:12px!important;box-shadow:0 18px 44px rgba(0,0,0,.36)!important;}
.stTabs [data-baseweb="tab"]{height:58px!important;font-size:12px!important;letter-spacing:.03em!important;}
div[data-testid="stDataFrame"]{border:1px solid rgba(255,255,255,.08);border-radius:12px;overflow:hidden;background:rgba(2,6,8,.50)}
.ka-professional-note{padding:14px;border:1px solid rgba(124,255,43,.18);background:rgba(124,255,43,.055);border-radius:12px;color:#c9d8cf;font-size:13px;line-height:1.55;font-weight:750;margin:0 0 14px}
@media(max-width:1100px){.ka-page-banner h1{font-size:34px}.ka-page-banner img{height:230px}.ka-page-banner-content{padding:26px 22px}.ka-mini-banner h2{font-size:22px!important}}

/* === ETAP 7 WWW PROFESSIONAL COCKPIT === */
:root{
  --bg:#050708;
  --surface:#0a0f10;
  --surface-2:#0f1517;
  --surface-3:#151b1e;
  --line:rgba(219,230,224,.12);
  --line-strong:rgba(124,255,43,.24);
  --green:#7CFF2B;
  --green-soft:rgba(124,255,43,.10);
  --amber:#ffca45;
  --cyan:#42d9ff;
  --red:#ff5b5b;
  --muted:#94a39b;
  --text:#f4f8f2;
}
html,body,.stApp{
  background:
    linear-gradient(180deg,#050708 0%,#07100b 42%,#050708 100%)!important;
  color:var(--text)!important;
}
.block-container{
  max-width:1760px!important;
  padding:14px 18px 22px!important;
}
header[data-testid="stHeader"]{
  background:linear-gradient(180deg,rgba(5,7,8,.94),rgba(5,7,8,0))!important;
}
.ka-page-banner{
  min-height:230px!important;
  border-radius:8px!important;
  border:1px solid rgba(124,255,43,.20)!important;
  margin:0 0 14px!important;
  box-shadow:0 18px 48px rgba(0,0,0,.42)!important;
}
/* Full bitmap banner mode: show the whole designed banner, do not crop it. */
.ka-image-banner{
  min-height:0!important;
  height:auto!important;
  background:#020303!important;
}
.ka-image-banner img{
  width:100%!important;
  height:auto!important;
  max-height:none!important;
  object-fit:contain!important;
  object-position:center center!important;
  opacity:1!important;
  filter:none!important;
}
.ka-image-banner:after{
  display:none!important;
}
.ka-image-banner .ka-page-banner-content{
  display:none!important;
}
.ka-page-banner img{
  height:238px!important;
  opacity:.82!important;
  filter:saturate(1.06) contrast(1.08) brightness(.86)!important;
}
.ka-page-banner:after{
  background:linear-gradient(90deg,rgba(0,0,0,.90) 0%,rgba(0,0,0,.58) 52%,rgba(0,0,0,.82) 100%)!important;
}
.ka-page-banner-content{
  padding:28px 32px!important;
  justify-content:flex-end!important;
}
.ka-page-eyebrow{
  color:var(--green)!important;
  font-size:11px!important;
  letter-spacing:.16em!important;
  margin-bottom:10px!important;
}
.ka-page-banner h1{
  font-size:38px!important;
  line-height:1.02!important;
  text-shadow:none!important;
  letter-spacing:0!important;
}
.ka-page-banner p{
  color:#d5dfd9!important;
  font-size:14px!important;
  max-width:980px!important;
  font-weight:650!important;
}
.ka-mini-banner{
  min-height:116px!important;
  border-radius:8px!important;
  border-color:rgba(124,255,43,.14)!important;
  margin:0 0 12px!important;
}
.ka-mini-image-banner{
  min-height:0!important;
  height:auto!important;
  background:#020303!important;
}
.ka-mini-image-banner img{
  width:100%!important;
  height:auto!important;
  max-height:none!important;
  object-fit:contain!important;
  object-position:center center!important;
  opacity:1!important;
  filter:none!important;
}
.ka-mini-image-banner:after{
  display:none!important;
}
.ka-mini-image-banner .ka-mini-banner-content{
  display:none!important;
}
.ka-mini-banner img{
  height:118px!important;
  opacity:.58!important;
}
.ka-mini-banner-content{
  padding:18px 20px!important;
}
.ka-mini-banner h2{
  font-size:22px!important;
  line-height:1.05!important;
  text-shadow:none!important;
}
.ka-mini-banner p{
  font-size:12px!important;
  color:#cbd7d0!important;
}
.stTabs [data-baseweb="tab-list"]{
  position:sticky!important;
  top:0!important;
  z-index:20!important;
  display:grid!important;
  grid-auto-flow:column!important;
  grid-auto-columns:minmax(118px,1fr)!important;
  gap:0!important;
  background:#070a0b!important;
  border:1px solid rgba(219,230,224,.12)!important;
  border-radius:8px!important;
  overflow:auto!important;
  margin:0 0 14px!important;
  box-shadow:0 14px 32px rgba(0,0,0,.34)!important;
}
.stTabs [data-baseweb="tab"]{
  height:48px!important;
  min-width:118px!important;
  padding:0 12px!important;
  background:#080c0d!important;
  border-right:1px solid rgba(219,230,224,.08)!important;
  color:#d8e4dd!important;
  font-size:11px!important;
  font-weight:900!important;
  letter-spacing:.04em!important;
  text-transform:uppercase!important;
}
.stTabs [aria-selected="true"]{
  background:linear-gradient(180deg,rgba(124,255,43,.16),rgba(124,255,43,.045))!important;
  color:#bfff83!important;
  border-bottom:2px solid var(--green)!important;
}
.ka-title{
  margin:18px 0 12px!important;
  font-size:24px!important;
  font-weight:950!important;
  text-shadow:none!important;
}
.ka-dot{
  width:14px!important;
  height:14px!important;
  border-radius:3px!important;
  background:linear-gradient(135deg,var(--green),var(--cyan))!important;
  box-shadow:0 0 14px rgba(124,255,43,.35)!important;
}
.ka-grid{
  grid-template-columns:repeat(5,minmax(0,1fr))!important;
  gap:10px!important;
  margin:0 0 12px!important;
}
.ka-card{
  min-height:106px!important;
  border-radius:8px!important;
  border:1px solid rgba(219,230,224,.11)!important;
  background:linear-gradient(180deg,rgba(18,25,27,.96),rgba(9,14,15,.98))!important;
  padding:14px!important;
  box-shadow:0 12px 28px rgba(0,0,0,.28)!important;
}
.ka-card:before{
  content:"";
  display:block;
  height:2px;
  width:42px;
  margin:0 0 12px;
  background:linear-gradient(90deg,var(--green),var(--cyan));
  border-radius:2px;
}
.ka-label{
  font-size:10px!important;
  color:#a8b5ae!important;
  letter-spacing:.10em!important;
}
.ka-value{
  font-size:28px!important;
  line-height:1.05!important;
  letter-spacing:0!important;
}
.ka-sub{
  min-height:16px!important;
  font-size:11px!important;
  color:#95ff69!important;
}
.sparkline{display:none!important;}
.ka-panel{
  border-radius:8px!important;
  border:1px solid rgba(219,230,224,.11)!important;
  background:linear-gradient(180deg,rgba(14,20,22,.98),rgba(7,11,12,.98))!important;
  padding:16px!important;
  box-shadow:0 14px 34px rgba(0,0,0,.30)!important;
}
.ka-panel h3{
  margin:0 0 12px!important;
  font-size:15px!important;
  line-height:1.2!important;
  letter-spacing:.05em!important;
  text-transform:uppercase!important;
  color:#f6fff7!important;
}
.ka-table{
  table-layout:auto!important;
  font-size:13px!important;
  border-collapse:separate!important;
  border-spacing:0!important;
}
.ka-table th{
  position:sticky!important;
  top:49px!important;
  z-index:5!important;
  background:#111819!important;
  color:#aebbb4!important;
  padding:10px 11px!important;
  font-size:10px!important;
  letter-spacing:.08em!important;
  border-bottom:1px solid rgba(124,255,43,.16)!important;
}
.ka-table td{
  background:#091011!important;
  border-bottom:1px solid rgba(219,230,224,.07)!important;
  padding:11px!important;
  color:#eef6f0!important;
}
.ka-table tr:nth-child(even) td{
  background:#0c1314!important;
}
.ka-table tr:hover td{
  background:rgba(124,255,43,.055)!important;
}
.ka-table-scroll{
  width:100%!important;
  overflow:auto!important;
  border:1px solid rgba(219,230,224,.11)!important;
  border-radius:8px!important;
  background:#091011!important;
}
.ka-table-scroll .ka-table{
  min-width:760px!important;
}
.ka-table-scroll .ka-table th{
  top:0!important;
}
.pill{
  border-radius:6px!important;
  padding:5px 9px!important;
  white-space:nowrap!important;
}
.progress{
  height:7px!important;
  background:#202829!important;
}
.progress span{
  background:linear-gradient(90deg,var(--green),var(--amber))!important;
}
.ai-table-final{
  border-radius:8px!important;
  border:1px solid rgba(219,230,224,.12)!important;
  background:#091011!important;
  box-shadow:0 14px 34px rgba(0,0,0,.30)!important;
}
.ai-table-final-head{
  min-height:44px!important;
  background:#111819!important;
  color:#bfff83!important;
  font-size:10px!important;
}
.ai-table-final-row{
  min-height:58px!important;
  background:#091011!important;
  font-size:13px!important;
}
.ai-table-final-row:hover{
  background:rgba(124,255,43,.055)!important;
}
.ai-cell-main{
  font-size:14px!important;
}
.ai-cell-sub{
  color:#95a49b!important;
}
.ai-status-inline{
  height:30px!important;
  min-width:82px!important;
  border-radius:6px!important;
  background:#151d1f!important;
}
.ai-detail-final,
.ai-detail-final-box{
  border-radius:8px!important;
}
div[data-testid="stDataFrame"]{
  border-radius:8px!important;
  border:1px solid rgba(219,230,224,.11)!important;
  background:#091011!important;
}
div[data-testid="stMetric"]{
  background:#0d1415!important;
  border:1px solid rgba(219,230,224,.11)!important;
  border-radius:8px!important;
  padding:12px!important;
}
.stButton>button,
button[kind="secondary"],
button[kind="primary"]{
  border-radius:6px!important;
  border:1px solid rgba(124,255,43,.26)!important;
  background:linear-gradient(180deg,rgba(124,255,43,.16),rgba(124,255,43,.07))!important;
  color:#f4fff1!important;
  font-weight:850!important;
}
.stButton>button:hover,
button[kind="secondary"]:hover,
button[kind="primary"]:hover{
  border-color:rgba(124,255,43,.54)!important;
  background:linear-gradient(180deg,rgba(124,255,43,.22),rgba(124,255,43,.09))!important;
}
input,textarea,select{
  border-radius:6px!important;
}
.footer-ka{
  border-top:1px solid rgba(219,230,224,.10)!important;
  margin-top:16px!important;
  padding:14px 2px 4px!important;
}
.ka-page-banner.ka-image-banner,
.ka-mini-banner.ka-mini-image-banner{
  min-height:0!important;
  height:auto!important;
  background:#020303!important;
}
.ka-page-banner.ka-image-banner img,
.ka-mini-banner.ka-mini-image-banner img{
  display:block!important;
  width:100%!important;
  height:auto!important;
  max-height:none!important;
  object-fit:contain!important;
  object-position:center center!important;
  opacity:1!important;
  filter:none!important;
}
.ka-page-banner.ka-image-banner:after,
.ka-mini-banner.ka-mini-image-banner:after,
.ka-page-banner.ka-image-banner .ka-page-banner-content,
.ka-mini-banner.ka-mini-image-banner .ka-mini-banner-content{
  display:none!important;
}
@media(max-width:1200px){
  .ka-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important;}
  .ka-page-banner h1{font-size:31px!important;}
  .ka-page-banner-content{padding:24px 22px!important;}
}
@media(max-width:760px){
  .block-container{padding:10px 10px 18px!important;}
  .ka-grid{grid-template-columns:1fr!important;}
  .ka-page-banner{min-height:210px!important;}
  .ka-page-banner img{height:214px!important;}
  .ka-image-banner{min-height:0!important;}
  .ka-image-banner img{height:auto!important;}
  .ka-page-banner h1{font-size:25px!important;}
  .ka-page-banner p{font-size:12px!important;}
  .stTabs [data-baseweb="tab-list"]{grid-auto-columns:minmax(104px,1fr)!important;}
  .stTabs [data-baseweb="tab"]{min-width:104px!important;height:44px!important;font-size:10px!important;}
}

/* Czytelne zakładki i hiperłącza na ciemnym tle. */
.stTabs [data-baseweb="tab"],
.stTabs [data-baseweb="tab"] p,
.stTabs [data-baseweb="tab"] span{
  color:#d8e4dd!important;
  opacity:1!important;
  text-decoration:none!important;
}
.stTabs [data-baseweb="tab"]:hover,
.stTabs [data-baseweb="tab"]:hover p,
.stTabs [data-baseweb="tab"]:hover span{
  color:#ffffff!important;
  background:rgba(124,255,43,.055)!important;
}
.stTabs [aria-selected="true"],
.stTabs [aria-selected="true"] p,
.stTabs [aria-selected="true"] span{
  color:#bfff83!important;
  opacity:1!important;
}
.stApp a:not(.status-link){
  color:#9cff65!important;
  text-decoration:underline!important;
  text-decoration-color:rgba(156,255,101,.55)!important;
  text-underline-offset:3px!important;
}
.stApp a:not(.status-link):hover{
  color:#ffffff!important;
  text-decoration-color:#7CFF2B!important;
}
</style>
''', unsafe_allow_html=True)


def hero() -> None:
    if BANNER_FILE.exists() and BANNER_FILE.stat().st_size > 0:
        b64 = b64_image(BANNER_FILE)
        st.markdown(f'<div class="kanibal-hero"><img src="data:image/png;base64,{b64}" alt="KANIBAL ANALYTICS"></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="kanibal-fallback">KANIBAL ANALYTICS</div>', unsafe_allow_html=True)


def metric(label, value, sub="") -> str:
    return f'<div class="ka-card"><div class="ka-label">{label}</div><div class="ka-value">{value}</div><div class="ka-sub">{sub}</div><div class="sparkline"></div></div>'


def metrics(items: List[tuple]) -> None:
    st.markdown('<div class="ka-grid">' + ''.join(metric(*i) for i in items) + '</div>', unsafe_allow_html=True)


def html_table(headers: List[str], rows: List[List[str]]) -> str:
    head = ''.join(f'<th>{h}</th>' for h in headers)
    body = ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in row) + '</tr>' for row in rows)
    return f'<table class="ka-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def _format_table_value(value) -> str:
    if value is None or pd.isna(value):
        return "-"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def dataframe_html_table(df: pd.DataFrame, limit: int | None = None) -> str:
    if df is None or df.empty:
        return html_table(["Informacja"], [["Brak danych."]])
    out = streamlit_df(df)
    if limit:
        out = out.head(limit)
    headers = [html.escape(str(col)) for col in out.columns]
    rows = []
    for _, row in out.iterrows():
        rows.append([html.escape(_format_table_value(row[col])) for col in out.columns])
    return '<div class="ka-table-scroll">' + html_table(headers, rows) + '</div>'


def confidence_bar(value: float) -> str:
    value = max(0.0, min(100.0, float(value)))
    return f'<div style="display:flex;align-items:center;gap:10px"><b>{value:.0f}%</b><div class="progress"><span style="width:{value:.0f}%"></span></div></div>'


def placeholder_chart(title: str, subtitle: str = "Wykres gotowy - oczekuje na dane") -> str:
    return chart_card(title, [], subtitle)


def live_rows(live: pd.DataFrame) -> List[List[str]]:
    rows = []
    for _, row in live.head(30).iterrows():
        signal_verified = str(first_existing(row, ["signal_verified"], "false")).strip().lower() in {"1", "true", "yes"}
        odds_verified = str(first_existing(row, ["odds_verified"], "false")).strip().lower() in {"1", "true", "yes"}
        raw_conf = pd.to_numeric(pd.Series([first_existing(row, ["confidence"], None)]), errors="coerce").iloc[0]
        conf_html = confidence_bar(float(raw_conf)) if signal_verified and pd.notna(raw_conf) else "-"
        signal = first_existing(row, ["signal"], "-") if signal_verified else "Brak zweryfikowanego typu"
        odds = first_existing(row, ["odds"], "-") if odds_verified else "-"
        odds_market = first_existing(row, ["odds_market"], "") if odds_verified else ""
        bookmaker = first_existing(row, ["odds_bookmaker"], "") if odds_verified else ""
        odds_context = " · ".join(str(value) for value in (odds_market, bookmaker) if value)
        odds_text = f"{odds} ({odds_context})" if odds_context else str(odds)
        quality = "Mecz + kurs z API" if odds_verified else "Mecz z API"
        status = str(first_existing(row, ["status"], "-"))
        rows.append([
            html.escape(str(first_existing(row, ["league", "liga"], "-"))),
            f'<b>{html.escape(str(first_existing(row, ["match", "mecz"], "-")))}</b>',
            f'<span class="green">{html.escape(str(first_existing(row, ["minute", "minuta"], "-")))}</span>',
            f'<b>{html.escape(str(first_existing(row, ["score", "wynik"], "-")))}</b>',
            f'<span class="yellow">{html.escape(str(signal))}</span>',
            conf_html,
            html.escape(odds_text),
            f'<span class="blue">{html.escape(status)}</span>',
            f'<span class="pill pill-green">{quality}</span>',
        ])
    return rows


def pick_rows(picks: pd.DataFrame) -> List[List[str]]:
    rows = []
    for _, row in picks.head(10).iterrows():
        conf = as_float(first_existing(row, ["confidence", "advanced_confidence", "ai_pick_score"], 0))
        rows.append([str(first_existing(row, ["liga", "league"], "-")), f'<b>{first_existing(row, ["mecz", "match"], "-")}</b>', fmt_market(first_existing(row, ["typ", "market"], "-")), str(first_existing(row, ["kurs_buk", "odds"], "-")), confidence_bar(conf), f'<span class="green">{first_existing(row, ["ev", "edge", "value"], "-")}</span>', '<span class="pill pill-green">WARTO</span>' if conf >= 60 else '<span class="pill pill-yellow">OBSERWUJ</span>'])
    return rows




def ai_row_key(row, idx: int) -> str:
    match = str(first_existing(row, ["match", "mecz"], "match")).replace(" ", "_").replace("/", "_")
    market = str(first_existing(row, ["market", "typ"], "market")).replace(" ", "_").replace("/", "_")
    return f"ai_detail_{idx}_{match}_{market}"





def render_ai_detail_card(row) -> str:
    def number(names):
        raw = first_existing(row, names, None)
        try:
            parsed = float(pd.to_numeric(pd.Series([raw]), errors="coerce").iloc[0])
            return parsed if math.isfinite(parsed) else None
        except Exception:
            return None

    def shown(value, digits=2):
        return "BRAK DANYCH" if value is None else f"{value:.{digits}f}"

    conf = number(["confidence", "advanced_confidence", "ai_pick_score"])
    calibrated = number(["confidence_calibrated_v2", "calibrated_confidence", "calibrated"])
    model_prob = number(["prawd_model", "model_prob", "model_probability"])
    final_prob = number(["prawd_final", "final_prob", "final_probability", "probability"])

    ev = number(["ev", "value"])
    edge = number(["edge"])
    kelly = number(["kelly_25", "kelly", "kelly_fraction"])
    risk = str(first_existing(row, ["risk", "risk_level"], "BRAK DANYCH")).upper()

    book_odds = number(["book_odds", "odds", "kurs_buk"])
    model_odds = number(["kurs_model", "model_odds", "fair_odds"])
    bot_odds = number(["kurs_bota", "bot_odds", "ai_odds", "fair_odds"])
    sharp = str(first_existing(row, ["sharp", "sharp_signal", "sharp_label"], "BRAK DANYCH")).upper()

    home_xg = number(["home_goal_rate", "home_xg", "xg_home"])
    away_xg = number(["away_goal_rate", "away_xg", "xg_away"])
    adv_total_xg = number(["advanced_total_xg", "adv_total_xg", "total_xg"])
    adv_over = number(["advanced_over25_prob", "adv_over25", "adv_over_2_5", "over25_probability"])
    margin = number(["market_margin", "marza_sum", "margin", "bookmaker_margin"])

    momentum_score = number(["momentum_score", "momentum"])
    momentum_label = str(first_existing(row, ["momentum_label"], "BRAK DANYCH")).upper()
    sharp_score = number(["sharp_score"])
    sharp_signals = str(first_existing(row, ["sharp_signals", "sharp_signal"], "BRAK DANYCH"))

    meta_prob = number(["meta_prob", "meta_probability"])
    model_weight = number(["meta_weight_model", "model_weight"])
    market_weight = number(["meta_weight_market", "market_weight"])
    xg_weight = number(["meta_weight_xg", "xg_weight"])
    momentum_weight = number(["meta_weight_momentum", "momentum_weight"])
    sharp_weight = number(["meta_weight_sharp", "sharp_weight"])
    dynamic_stake = number(["dynamic_stake", "stake"])

    return (
        f"<div class='ai-detail-final'>"
        f"<div class='ai-detail-final-grid'>"

        f"<div class='ai-detail-final-box'>"
        f"<div class='ai-detail-final-title'>MODEL AI</div>"
        f"<div class='ai-engine-line'><b>PEWNOŚĆ:</b> {shown(conf)}</div>"
        f"<div class='ai-engine-line'><b>PEWNOŚĆ SKALIBROWANA:</b> {shown(calibrated)}</div>"
        f"<div class='ai-engine-line'><b>PRAWDOPODOBIEŃSTWO MODELU:</b> {shown(model_prob, 4)}</div>"
        f"<div class='ai-engine-line'><b>PRAWDOPODOBIEŃSTWO KOŃCOWE:</b> {shown(final_prob, 4)}</div>"
        f"<div class='ai-engine-line'><b>ETAP A:</b> {shown(final_prob, 4)}</div>"
        f"</div>"

        f"<div class='ai-detail-final-box'>"
        f"<div class='ai-detail-final-title'>SILNIK WARTOŚCI</div>"
        f"<div class='ai-engine-line'><b>EV:</b> {shown(ev, 4)}</div>"
        f"<div class='ai-engine-line'><b>PRZEWAGA:</b> {shown(edge, 4)}</div>"
        f"<div class='ai-engine-line'><b>KELLY:</b> {shown(kelly)}</div>"
        f"<div class='ai-engine-line'><b>RYZYKO:</b> {risk}</div>"
        f"</div>"

        f"<div class='ai-detail-final-box'>"
        f"<div class='ai-detail-final-title'>SILNIK RYNKU</div>"
        f"<div class='ai-engine-line'><b>KURS BUKMACHERA:</b> {shown(book_odds)}</div>"
        f"<div class='ai-engine-line'><b>KURS MODELU:</b> {shown(model_odds)}</div>"
        f"<div class='ai-engine-line'><b>KURS BOTA:</b> {shown(bot_odds)}</div>"
        f"<div class='ai-engine-line'><b>RYNEK SHARP:</b> {sharp}</div>"
        f"</div>"

        f"<div class='ai-detail-final-box'>"
        f"<div class='ai-detail-final-title'>DANE MODELU BRAMEK</div>"
        f"<div class='ai-engine-line'><b>TEMPO BRAMEK GOSPODARZY:</b> {shown(home_xg)}</div>"
        f"<div class='ai-engine-line'><b>TEMPO BRAMEK GOŚCI:</b> {shown(away_xg)}</div>"
        f"<div class='ai-engine-line'><b>SUMA:</b> {shown(adv_total_xg)}</div>"
        f"<div class='ai-engine-line'><b>OVER 2.5:</b> {shown(adv_over)}</div>"
        f"<div class='ai-engine-line'><b>MARŻA:</b> {shown(margin, 4)}</div>"
        f"</div>"

        f"<div class='ai-detail-final-box'>"
        f"<div class='ai-detail-final-title'>SILNIK TEMPA</div>"
        f"<div class='ai-engine-line'><b>WYNIK TEMPA:</b> {shown(momentum_score, 1)}</div>"
        f"<div class='ai-engine-line'><b>OCENA TEMPA:</b> {momentum_label}</div>"
        f"<div class='ai-engine-line'><b>WYNIK SHARP:</b> {shown(sharp_score, 0)}</div>"
        f"<div class='ai-engine-line'><b>SYGNAŁY SHARP:</b> {sharp_signals}</div>"
        f"</div>"

        f"<div class='ai-detail-final-box'>"
        f"<div class='ai-detail-final-title'>META AI</div>"
        f"<div class='ai-engine-line'><b>PRAWDOPODOBIEŃSTWO META:</b> {shown(meta_prob, 1)}</div>"
        f"<div class='ai-engine-line'><b>WAGA MODELU:</b> {shown(model_weight)}</div>"
        f"<div class='ai-engine-line'><b>WAGA RYNKU:</b> {shown(market_weight)}</div>"
        f"<div class='ai-engine-line'><b>WAGA DANYCH BRAMEK:</b> {shown(xg_weight)}</div>"
        f"<div class='ai-engine-line'><b>WAGA TEMPA:</b> {shown(momentum_weight)}</div>"
        f"<div class='ai-engine-line'><b>WAGA SHARP:</b> {shown(sharp_weight)}</div>"
        f"<div class='ai-engine-line'><b>DYNAMICZNA STAWKA:</b> {shown(dynamic_stake, 1)}</div>"
        f"</div>"

        f"</div></div>"
    )



def render_ai_picks_interactive(picks: pd.DataFrame) -> None:
    if picks.empty:
        st.markdown(
            '<div class="ka-panel"><h3>TYPY AI</h3>'
            '<div class="ai-table-final">'
            '<div class="ai-table-final-head"><div>LIGA</div><div>MECZ</div><div>RYNEK</div><div>KURS</div><div>PEWNOŚĆ</div><div>PRZEWAGA</div><div>STATUS</div></div>'
            '<div class="ai-table-final-row"><div>-</div><div><span class="ai-cell-main">Oczekiwanie na typy AI</span></div><div>-</div><div>-</div><div>-</div><div>-</div><div>-</div></div>'
            '</div></div>',
            unsafe_allow_html=True
        )
        return

    st.markdown(
        '<div class="ka-panel"><h3>TYPY AI</h3>'
        '<div class="ai-table-final">'
        '<div class="ai-table-final-head"><div>LIGA</div><div>MECZ</div><div>RYNEK</div><div>KURS</div><div>PEWNOŚĆ</div><div>PRZEWAGA</div><div>STATUS</div></div>'
        '</div></div>',
        unsafe_allow_html=True
    )

    shown = picks.head(10).reset_index(drop=True)

    for idx, row in shown.iterrows():
        conf = as_float(first_existing(row, ["confidence", "advanced_confidence", "ai_pick_score"], 0))
        edge = first_existing(row, ["ev", "edge", "value"], "-")
        status_label = (
            "BARDZO MOCNY" if conf >= 85
            else "NORMALNY" if conf >= 65
            else "RYZYKO"
        )

        league = first_existing(row, ["liga", "league"], "-")
        match = first_existing(row, ["mecz", "match"], "-")
        market = fmt_market(first_existing(row, ["typ", "market"], "-"))
        odds = first_existing(row, ["kurs_buk", "odds"], "-")
        conf_width = max(0, min(100, int(conf)))

        row_html = (
            f'<div class="ai-table-final" style="margin-top:-14px;border-top:0;border-radius:0;">'
            f'<div class="ai-table-final-row">'
            f'<div><span class="ai-cell-num">{league}</span></div>'
            f'<div><span class="ai-cell-main">{match}</span><span class="ai-cell-sub">Niezależny typ AI</span></div>'
            f'<div><span class="ai-cell-num">{market}</span></div>'
            f'<div><span class="ai-cell-num">{odds}</span></div>'
            f'<div><div class="ai-conf-line"><span class="ai-conf-value">{conf_width}%</span><div class="ai-conf-track"><div class="ai-conf-fill" style="width:{conf_width}%"></div></div></div></div>'
            f'<div><span class="ai-edge-plus">{edge}</span></div>'
            f'<div><div class="ai-status-inline">{status_label}</div></div>'
            f'</div></div>'
        )

        st.markdown(row_html, unsafe_allow_html=True)

        with st.expander(f"{status_label} - szczegóły AI", expanded=False):
            st.markdown(render_ai_detail_card(row), unsafe_allow_html=True)


def title(text: str) -> None:
    st.markdown(f'<div class="ka-title"><span class="ka-dot"></span>{text}</div>', unsafe_allow_html=True)


def page_banner(section: str, name: str, subtitle: str) -> None:
    image = b64_image(BANNER_FILE)
    if image:
        st.markdown(
            f'''<div class="ka-page-banner ka-image-banner"><img src="data:image/png;base64,{image}" alt="KANIBAL ANALYTICS"></div>''',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '''<div class="ka-page-banner ka-image-banner"></div>''',
            unsafe_allow_html=True,
        )


def subpage_banner(section: str, name: str, subtitle: str) -> None:
    # Podzakładki nie renderują własnego banera, żeby na ekranie był tylko jeden baner.
    return None


def _result_source(results: pd.DataFrame, picks: pd.DataFrame | None = None) -> pd.DataFrame:
    if results is not None and not results.empty:
        return results.copy()
    if picks is not None and not picks.empty:
        return picks.copy()
    return pd.DataFrame()


def _win_mask(df: pd.DataFrame) -> pd.Series:
    if df is None or df.empty:
        return pd.Series([], dtype=bool)
    if "result" in df.columns:
        return df["result"].astype(str).str.strip().str.upper().isin({"WIN", "WON", "WYGRANA", "1", "TRUE"})
    if "status" in df.columns:
        return df["status"].astype(str).str.strip().str.upper().isin({"WIN", "WON", "WYGRANA", "CLOSED_WIN"})
    return pd.Series([False] * len(df), index=df.index)


def _settled_mask(df: pd.DataFrame) -> pd.Series:
    if df is None or df.empty or "result" not in df.columns:
        return pd.Series(False, index=df.index if df is not None else None, dtype=bool)
    return df["result"].astype(str).str.strip().str.upper().isin(
        {"WIN", "WON", "LOSE", "LOSS", "LOST", "PUSH", "VOID"}
    )


def _smart_group_table(df: pd.DataFrame, group_col: str, label: str, limit: int = 15) -> None:
    if df is None or df.empty or group_col not in df.columns:
        table = html_table(["Informacja"], [["Brak danych do tej analizy."]])
        st.markdown(f'<div class="ka-panel"><h3>{html.escape(label)}</h3><div class="ka-table-scroll">{table}</div></div>', unsafe_allow_html=True)
        return
    work = df.copy()
    work[group_col] = work[group_col].astype(str).replace({"": "-", "nan": "-"})
    win = _win_mask(work)
    work["_win"] = win.astype(int) if len(win) else 0
    work["_settled"] = _settled_mask(work).astype(int)
    work["_profit"] = (
        pd.to_numeric(work["profit"], errors="coerce").fillna(0)
        if "profit" in work.columns
        else pd.Series(0.0, index=work.index, dtype=float)
    )
    work["_roi"] = (
        pd.to_numeric(work["roi"], errors="coerce").fillna(0)
        if "roi" in work.columns
        else pd.Series(0.0, index=work.index, dtype=float)
    )
    grouped = work.groupby(group_col, dropna=False).agg(
        typy=(group_col, "count"),
        rozliczone=("_settled", "sum"),
        wygrane=("_win", "sum"),
        profit=("_profit", "sum"),
        roi=("_roi", "mean"),
    ).reset_index()
    grouped["trafnosc_%"] = (grouped["wygrane"] / grouped["rozliczone"].replace(0, pd.NA) * 100).fillna(0).round(2)
    grouped = grouped.sort_values(["trafnosc_%", "typy", "profit"], ascending=[False, False, False]).head(limit)
    st.markdown(f'<div class="ka-panel"><h3>{html.escape(label)}</h3>{dataframe_html_table(grouped)}</div>', unsafe_allow_html=True)


def _decision_table(df: pd.DataFrame, cols: list[str], fallback: str) -> None:
    if df is None or df.empty:
        table = html_table(["Informacja"], [[html.escape(fallback)]])
        st.markdown(f'<div class="ka-table-scroll">{table}</div>', unsafe_allow_html=True)
        return
    existing = [c for c in cols if c in df.columns]
    st.markdown(dataframe_html_table(df[existing] if existing else df), unsafe_allow_html=True)


def _odds_from_pick(pick: dict, default: float = 2.0) -> float:
    return max(1.01, as_float(first_existing(pick, ["superbet_odds", "kurs_superbet", "kurs_buk", "odds"], default), default))


def render_live(live: pd.DataFrame, picks: pd.DataFrame) -> None:
    page_banner("Panel na żywo", "NA ŻYWO", "Wyłącznie świeże dane LIVE potwierdzone przez API. Braki pozostają puste.")
    if live.empty:
        verified_types = 0
        verified_odds = 0
        avg_conf = 0.0
        avg_odds = 0.0
    else:
        signal_mask = live.get("signal_verified", pd.Series(False, index=live.index)).astype(str).str.lower().isin({"1", "true", "yes"})
        odds_mask = live.get("odds_verified", pd.Series(False, index=live.index)).astype(str).str.lower().isin({"1", "true", "yes"})
        verified_types = int(signal_mask.sum())
        verified_odds = int(odds_mask.sum())
        avg_conf = as_float(pd.to_numeric(live.loc[signal_mask, "confidence"], errors="coerce").mean(), 0) if "confidence" in live else 0
        avg_odds = as_float(pd.to_numeric(live.loc[odds_mask, "odds"], errors="coerce").mean(), 0) if "odds" in live else 0
    metrics([
        ("Mecze live", str(len(live)), "potwierdzone przez API"),
        ("Typy live", str(verified_types), "tylko zweryfikowane"),
        ("Kursy live", str(verified_odds), "potwierdzone przez API"),
        ("Średnia pewność", pct(avg_conf) if verified_types else "-", "bez wartości zastępczych"),
        ("Średni kurs", f"{avg_odds:.2f}" if verified_odds and avg_odds else "-", "bez kursu prematch"),
    ])
    title("NA ŻYWO")
    rows = live_rows(live)
    headers = ["Liga", "Mecz", "Minuta", "Wynik", "Typ zakładu", "Pewność", "Kurs", "Status", "Jakość danych"]
    table = html_table(headers, rows) if rows else html_table(headers, [["-", "Brak świeżych, potwierdzonych danych LIVE", "-", "-", "-", "-", "-", "-", "-"]])
    st.markdown(f'<div class="ka-panel"><h3>NA ŻYWO - dane zweryfikowane</h3>{table}</div>', unsafe_allow_html=True)


def render_prematch(picks: pd.DataFrame, low_picks: pd.DataFrame | None = None, risk_picks: pd.DataFrame | None = None) -> None:
    page_banner("Typy przedmeczowe", "PRZEDMECZOWE", "Trzy czytelne tabele: główna, niskie ryzyko i podwyższone ryzyko.")
    low_picks = normalize_picks(low_picks) if low_picks is not None and not low_picks.empty else pd.DataFrame()
    risk_picks = normalize_picks(risk_picks) if risk_picks is not None and not risk_picks.empty else pd.DataFrame()
    metrics([
        ("Przedmeczowe", str(len(picks)), "główne"),
        ("Niskie ryzyko", str(len(low_picks)), "1.00-3.50"),
        ("Podwyższone ryzyko", str(len(risk_picks)), "1.00-5.00"),
        ("Średni kurs", f"{as_float(numeric_series(picks, 'kurs_buk').mean(), 0):.2f}", "główne"),
        ("Średnia pewność", pct(as_float(numeric_series(picks, "confidence").mean(), 0)), "model"),
    ])
    title("PRZEDMECZOWE")
    headers = ["Liga", "Mecz", "Rynek", "Kurs", "Pewność", "Przewaga", "Status"]
    prematch_tabs = st.tabs(["Główne", "Niskie ryzyko", "Podwyższone ryzyko"])
    datasets = [(picks, "TYPY PRZEDMECZOWE", "Brak danych przedmeczowych."), (low_picks, "NISKIE RYZYKO", "Brak danych niskiego ryzyka - bot nie zapisał jeszcze auto_low_picks.csv."), (risk_picks, "PODWYŻSZONE RYZYKO", "Brak danych podwyższonego ryzyka - bot nie zapisał jeszcze auto_risk_picks.csv.")]
    for tab, (df, label, empty_msg) in zip(prematch_tabs, datasets):
        with tab:
            subpage_banner("Prematch table", label, empty_msg)
            rows = pick_rows(df) if df is not None and not df.empty else []
            table = html_table(headers, rows) if rows else html_table(headers, [["-", empty_msg, "-", "-", "-", "-", "-"]])
            st.markdown(f'<div class="ka-panel"><h3>{label}</h3>{table}</div>', unsafe_allow_html=True)


def render_ai(picks: pd.DataFrame, results: pd.DataFrame, low_picks: pd.DataFrame | None = None, risk_picks: pd.DataFrame | None = None) -> None:
    low_picks = low_picks if low_picks is not None else pd.DataFrame()
    risk_picks = risk_picks if risk_picks is not None else pd.DataFrame()
    all_ai = pd.concat([df for df in [picks, low_picks, risk_picks] if df is not None and not df.empty], ignore_index=True, sort=False) if any(df is not None and not df.empty for df in [picks, low_picks, risk_picks]) else pd.DataFrame()
    page_banner("Typy AI", "AI", "Trzy niezależne tabele AI: główna, niskie ryzyko i podwyższone ryzyko.")
    title("AI")
    metrics([
        ("AI", str(len(picks)), "główne"),
        ("AI niskie ryzyko", str(len(low_picks)), "1.00-3.50"),
        ("AI podwyższone ryzyko", str(len(risk_picks)), "1.00-5.00"),
        ("Średni wynik AI", f"{as_float(numeric_series(all_ai, 'ai_pick_score').mean(), as_float(numeric_series(all_ai, 'confidence').mean(), 0)):.2f}", "model"),
        ("Rozliczone", str(int(_settled_mask(results).sum())), "historia"),
    ])
    ai_tabs = st.tabs(["AI", "AI niskie ryzyko", "AI podwyższone ryzyko"])
    datasets = [
        (picks, "TYPY AI", "Brak danych AI - główny tryb nie ma jeszcze kandydatów."),
        (low_picks, "AI NISKIE RYZYKO", "Brak danych AI niskiego ryzyka - poczekaj na cykl albo uruchom pełny launcher."),
        (risk_picks, "AI PODWYŻSZONE RYZYKO", "Brak danych AI podwyższonego ryzyka - poczekaj na cykl albo uruchom pełny launcher."),
    ]
    for tab, (df, label, empty_msg) in zip(ai_tabs, datasets):
        with tab:
            subpage_banner("AI table", label, empty_msg)
            if df is None or df.empty:
                st.info(empty_msg)
            render_ai_picks_interactive(df if df is not None else pd.DataFrame())


def render_analytics(picks: pd.DataFrame, results: pd.DataFrame, heading="ANALITYKA") -> None:
    page_banner("Centrum decyzji", "ANALITYKA", "Centrum nauki bota: ligi, rynki, ryzyko, źródła, baza cech i wnioski z historii.")
    title(heading)
    src = _result_source(results, picks)
    win = _win_mask(src)
    settled = _settled_mask(src)
    settled_count = int(settled.sum()) if len(settled) else 0
    winrate = (float(win[settled].mean()) * 100) if settled_count else 0.0
    learning_paths = [
        DATA_DIR / "ai_learning" / "ai_feature_store.csv",
        DATA_DIR / "ai_learning_low" / "ai_feature_store.csv",
        DATA_DIR / "ai_learning_risk" / "ai_feature_store.csv",
        DATA_DIR / "ai_learning" / "ai_learning_events.csv",
        DATA_DIR / "ai_learning_low" / "ai_learning_events.csv",
        DATA_DIR / "ai_learning_risk" / "ai_learning_events.csv",
        DATA_DIR / "history" / "learning_feature_store.csv",
        DATA_DIR / "history" / "learning_events.csv",
    ]
    learning_count = sum(len(read_csv_safe(path)) for path in learning_paths)
    metrics([
        ("Zebrane rekordy", str(len(src)), "historia + picks"),
        ("Trafność", f"{winrate:.2f}%", "rozliczone"),
        ("Profit", money(numeric_series(src, 'profit').sum() if not src.empty else 0), "suma"),
        ("ROI", f"{as_float(numeric_series(src, 'roi').mean(), 0):+.2f}%", "średnio"),
        ("Baza nauki", str(learning_count), "wszystkie zapisane rekordy"),
    ])
    st.markdown('<div class="ka-panel"><h3>Centrum decyzyjne bota</h3><p class="ka-sub">Tabele aktualizują się wraz z historią, rozliczeniami i plikami uczenia zapisanymi przez bota.</p></div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        _smart_group_table(src, "league" if "league" in src.columns else "liga", "Najpewniejsze ligi według trafności")
    with col2:
        _smart_group_table(src, "market" if "market" in src.columns else "typ", "Najpewniejsze typy zakładów")
    col3, col4 = st.columns(2)
    with col3:
        _smart_group_table(src, "risk_level" if "risk_level" in src.columns else "risk", "Ryzyko vs wynik")
    with col4:
        _smart_group_table(src, "source" if "source" in src.columns else "status", "Źródło/status vs wynik")
    st.markdown("#### Czego bot już się nauczył")
    learning_frames = []
    for path in learning_paths:
        df = read_csv_safe(path)
        if not df.empty:
            df["plik"] = path.name
            learning_frames.append(df)
    learning_df = pd.concat(learning_frames, ignore_index=True, sort=False) if learning_frames else pd.DataFrame()
    _decision_table(learning_df.tail(200), ["created_at", "written_at", "event", "league", "match", "market", "odds", "confidence", "edge", "ev", "payload_json", "plik"], "Brak zapisanej historii nauki. Pojawi się po kolejnych cyklach bota.")


def render_history(results: pd.DataFrame) -> None:
    page_banner("Historia wyników", "HISTORIA", "Profesjonalna historia wyników, pomagająca podejmować decyzje i uczyć się na danych.")
    title("HISTORIA")
    win_mask = _win_mask(results)
    wins = str(int(win_mask.sum())) if len(win_mask) else "0"
    settled_mask = _settled_mask(results)
    settled_count = int(settled_mask.sum()) if len(settled_mask) else 0
    open_count = int(len(results) - settled_count)
    metrics([
        ("Rekordy", str(len(results)), "historia"),
        ("Rozliczone", str(settled_count), "wyniki końcowe"),
        ("Wygrane", wins, "trafione"),
        ("Profit", money(numeric_series(results, 'profit').sum() if not results.empty else 0), "suma"),
        ("Otwarte", str(open_count), "oczekują na wynik"),
    ])
    hist_tabs = st.tabs(["Tabela", "Ligi", "Typy", "Decyzyjność"])
    with hist_tabs[0]:
        subpage_banner("Historia", "Tabela", "Pełna tabela rozliczeń i rekordów historii.")
        _decision_table(results, ["created_at", "updated_at", "match_date", "league", "match_name", "match", "market", "bet_name", "odds", "confidence", "edge", "ev", "stake", "status", "result", "profit", "roi", "score", "record_source"], "Brak historii.")
    with hist_tabs[1]:
        subpage_banner("Historia", "Ligi", "Skuteczność i zysk według lig.")
        _smart_group_table(results, "league" if "league" in results.columns else "liga", "Historia według lig")
    with hist_tabs[2]:
        subpage_banner("Historia", "Typy", "Skuteczność i zysk według typu zakładu.")
        _smart_group_table(results, "market" if "market" in results.columns else "typ", "Historia według typu zakładu")
    with hist_tabs[3]:
        subpage_banner("Historia", "Decyzyjność", "Najlepsze rekordy do nauki i decyzji.")
        settled = results.loc[settled_mask].copy() if not results.empty and len(settled_mask) else pd.DataFrame()
        sort_columns = [c for c in ["roi", "profit", "confidence"] if c in settled.columns]
        if not settled.empty and sort_columns:
            settled = settled.sort_values(by=sort_columns, ascending=False)
        _decision_table(settled.head(100), ["league", "match_name", "match", "market", "odds", "confidence", "edge", "ev", "result", "profit", "roi", "record_source"], f"Brak rozliczonych danych decyzyjnych. Zapisane i oczekujące rekordy: {open_count}.")


def render_ranking(picks: pd.DataFrame, results: pd.DataFrame) -> None:
    page_banner("Ranking", "RANKING", "Ranking lig, typów zakładów i połączeń liga + rynek, aktualizowany z historią.")
    title("RANKING")
    src = _result_source(results, picks)
    metrics([
        ("Ligi", str(src["league"].nunique()) if not src.empty and "league" in src.columns else "0", "ranking"),
        ("Typy", str(src["market"].nunique()) if not src.empty and "market" in src.columns else "0", "rynki"),
        ("Rekordy", str(len(src)), "baza"),
        ("Profit", money(numeric_series(src, 'profit').sum() if not src.empty else 0), "suma"),
        ("ROI", f"{as_float(numeric_series(src, 'roi').mean(), 0):+.2f}%", "średnio"),
    ])
    col1, col2 = st.columns(2)
    with col1:
        _smart_group_table(src, "league" if "league" in src.columns else "liga", "Liga: co trafia najczęściej")
    with col2:
        _smart_group_table(src, "market" if "market" in src.columns else "typ", "Typ zakładu: co trafia najczęściej")
    if not src.empty:
        league_col = "league" if "league" in src.columns else "liga" if "liga" in src.columns else None
        market_col = "market" if "market" in src.columns else "typ" if "typ" in src.columns else None
        if league_col and market_col:
            st.markdown("#### Liga + typ zakładu")
            combo = src.copy()
            combo["liga_typ"] = combo[league_col].astype(str) + " | " + combo[market_col].astype(str)
            _smart_group_table(combo, "liga_typ", "Najmocniejsze połączenia")


def render_gpt_professional(prematch_picks: pd.DataFrame, low_picks: pd.DataFrame, risk_picks: pd.DataFrame, live: pd.DataFrame, results: pd.DataFrame) -> None:
    page_banner("Czat GPT", "CZAT GPT", "Profesjonalny ekran rozmowy z GPT podzielony na Prematch, Low i Risk.")
    title("CZAT GPT")
    total_context = sum(len(df) for df in [prematch_picks, low_picks, risk_picks] if df is not None)
    model_name = os.getenv("GPT_ANALYSIS_MODEL", os.getenv("OPENAI_MODEL", "gpt-5.2-chat-latest")).replace("-chat-latest", "")
    metrics([
        ("Model", model_name, "fallback: gpt-4.1-mini"),
        ("Tryb", "AUTO", "prompt ukryty"),
        ("Typy GPT", str(total_context), "aktywny profil"),
        ("Do gry", "-", "po analizie"),
        ("Zapis", "Profilowy", "bez mieszania danych"),
    ])
    st.markdown('<div class="ka-panel"><h3>Profesjonalny asystent analityczny</h3><p class="ka-sub">Moduł analizuje typy wygenerowane przez bota, korzysta z cache i nie nadpisuje głównej logiki typowania. Widoczny jest tylko wynik analizy, prompt pozostaje ukryty w kodzie.</p></div>', unsafe_allow_html=True)

    datasets = [
        ("prematch", "Prematch", prematch_picks if prematch_picks is not None else pd.DataFrame(), PICK_CANDIDATES),
        ("low", "Low", low_picks if low_picks is not None else pd.DataFrame(), LOW_PICK_CANDIDATES),
        ("risk", "Risk", risk_picks if risk_picks is not None else pd.DataFrame(), RISK_PICK_CANDIDATES),
    ]
    profile_tabs = st.tabs([label for _, label, _, _ in datasets])
    for tab, (profile_key, profile_label, profile_df, source_files) in zip(profile_tabs, datasets):
        with tab:
            render_gpt_tab(BASE_DIR, profile_name=profile_label, key_prefix=profile_key, source_files=source_files)


def _manual_pick_label(row, idx: int) -> str:
    league = first_existing(row, ["liga", "league"], "-")
    match = first_existing(row, ["mecz", "match"], "-")
    bot_market = fmt_market(first_existing(row, ["market", "typ"], "-"))
    odds = first_existing(row, ["kurs_buk", "odds"], "-")
    return f"{idx + 1}. {match} | {league} | bot: {bot_market} @ {odds}"


def _market_code_by_label(label: str) -> str:
    return dict((market_label, code) for code, market_label in MANUAL_MARKETS).get(label, "")


def _ako_calculated_odds(odds_values) -> float:
    total = 1.0
    for value in odds_values:
        total *= float(value or 1)
    return round(total, 4)


@st.cache_data(ttl=300, show_spinner=False)
def _resolve_superbet_odds_cached(fixture_id: str, market_code: str, fallback: float) -> tuple[float, str]:
    fallback_value = max(1.01, as_float(fallback, 1.80))
    if not fixture_id or not market_code:
        return fallback_value, "Superbet (kurs z bota)"
    try:
        from data_api import get_bookmaker_market_odds
        row = get_bookmaker_market_odds({"fixture_id": fixture_id}, market_code, "superbet")
        if row and row.get("odds"):
            return max(1.01, as_float(row.get("odds"), fallback_value)), str(row.get("bookmaker") or "Superbet")
    except Exception:
        pass
    return fallback_value, "Superbet (kurs z bota)"


def _bookmaker_odds_for_pick(pick: dict, market_code: str, default: float = 2.0) -> tuple[float, str]:
    market_code = str(market_code or "").upper()
    fallback = _odds_from_pick(pick, default)
    market_keys = [
        f"superbet_{market_code}", f"kurs_superbet_{market_code}", f"odds_{market_code}", f"kurs_{market_code}",
        f"superbet_{market_code.lower()}", f"kurs_superbet_{market_code.lower()}", f"odds_{market_code.lower()}", f"kurs_{market_code.lower()}",
    ]
    for key in market_keys:
        if key in pick and str(pick.get(key, "")).strip() not in {"", "nan", "None"}:
            value = as_float(pick.get(key), 0)
            if value > 1:
                return max(1.01, value), "Superbet"

    fixture_id = str(first_existing(pick, ["fixture_id", "id"], "")).strip()
    return _resolve_superbet_odds_cached(fixture_id, market_code, fallback)


def _manual_mode_note(mode_key: str, mode_label: str) -> str:
    return f"Tryb: {mode_key} | {mode_label}"


def _filter_manual_by_mode(df: pd.DataFrame, mode_key: str) -> pd.DataFrame:
    if df is None or df.empty or "note" not in df.columns:
        return df if df is not None else pd.DataFrame()
    note = df["note"].astype(str)
    mask = note.str.contains(f"Tryb: {mode_key}", regex=False, na=False)
    if mode_key == "standard":
        mask = mask | note.str.strip().eq("")
    return df[mask].copy()


def _render_manual_profile(mode_key: str, mode_label: str, picks_source: pd.DataFrame, manual_df: pd.DataFrame, ako_df: pd.DataFrame) -> None:
    if picks_source is None or picks_source.empty:
        st.warning(f"Brak meczów dla profilu {mode_label}. Poczekaj na kolejny cykl bota albo sprawdź pliki typów.")
        return

    shown = picks_source.reset_index(drop=True)
    labels = [_manual_pick_label(row, idx) for idx, row in shown.iterrows()]
    market_labels = [label for _, label in MANUAL_MARKETS]
    mode_note = _manual_mode_note(mode_key, mode_label)
    mode_manual_df = _filter_manual_by_mode(manual_df, mode_key)
    mode_ako_df = _filter_manual_by_mode(ako_df, mode_key)

    st.markdown(f'<div class="ka-panel"><h3>{html.escape(mode_label)}</h3><p class="ka-sub">Wybierasz mecz, typ i stawkę. Kurs jest automatycznie pobierany dla wybranego rynku; jeżeli feed nie zwróci Superbet, panel używa kursu bota jako bezpiecznego uzupełnienia.</p></div>', unsafe_allow_html=True)
    action_tabs = st.tabs(["Zakład pojedynczy", "Kupon multi", "Historia", "Statystyki"])

    with action_tabs[0]:
        selected_idx = st.selectbox(
            "Mecz",
            list(range(len(labels))),
            format_func=lambda idx: labels[int(idx)],
            key=f"{mode_key}_single_match",
        )
        selected_pick = shown.iloc[int(selected_idx)].to_dict()
        selected_market_label = st.selectbox("Typ zakładu", market_labels, key=f"{mode_key}_single_market")
        market_code = _market_code_by_label(selected_market_label)
        auto_odds, bookmaker_name = _bookmaker_odds_for_pick(selected_pick, market_code, _odds_from_pick(selected_pick))
        st.caption(f"Kurs: {auto_odds:.2f} | źródło: {bookmaker_name}")
        stake = st.number_input("Stawka", min_value=0.01, max_value=1000000.0, value=10.0, step=1.0, key=f"{mode_key}_single_stake")
        st.number_input("Kurs automatyczny", min_value=1.01, max_value=100.0, value=float(auto_odds), step=0.01, disabled=True, key=f"{mode_key}_single_auto_odds_{selected_idx}_{market_code}")
        if st.button("Zapisz zakład pojedynczy", type="primary", key=f"{mode_key}_single_save"):
            try:
                bet_id = add_manual_bet(selected_pick, market_code, auto_odds, stake, bookmaker=bookmaker_name, note=mode_note)
                st.success(f"Zapisano zakład pojedynczy #{bet_id}.")
                st.rerun()
            except Exception as exc:
                st.error(f"Nie udało się zapisać zakładu: {exc}")

    with action_tabs[1]:
        leg_count = st.number_input("Ile meczów ma kupon multi?", min_value=2, max_value=10, value=3, step=1, key=f"{mode_key}_multi_count")
        legs = []
        leg_odds = []
        for idx in range(int(leg_count)):
            st.markdown(f"**Pozycja {idx + 1}**")
            cols = st.columns([2.2, 1.2, 0.8])
            with cols[0]:
                match_idx = st.selectbox(
                    "Mecz",
                    list(range(len(labels))),
                    format_func=lambda value: labels[int(value)],
                    key=f"{mode_key}_multi_match_{idx}",
                )
            with cols[1]:
                market_label = st.selectbox("Typ", market_labels, key=f"{mode_key}_multi_market_{idx}")
            selected = shown.iloc[int(match_idx)].to_dict()
            market_code = _market_code_by_label(market_label)
            odds_value, bookmaker_name = _bookmaker_odds_for_pick(selected, market_code, _odds_from_pick(selected, 1.80))
            with cols[2]:
                st.number_input("Kurs", min_value=1.01, max_value=100.0, value=float(odds_value), step=0.01, disabled=True, key=f"{mode_key}_multi_odds_{idx}_{match_idx}_{market_code}")
            legs.append({"pick": selected, "manual_market": market_code, "odds": odds_value})
            leg_odds.append(odds_value)

        calculated = _ako_calculated_odds(leg_odds)
        coupon_stake = st.number_input("Stawka kuponu", min_value=0.01, max_value=1000000.0, value=10.0, step=1.0, key=f"{mode_key}_multi_stake")
        st.metric("Kurs łączny", f"{calculated:.4f}")
        if st.button("Zapisz kupon multi", type="primary", key=f"{mode_key}_multi_save"):
            try:
                coupon_id = add_ako_coupon(
                    legs,
                    stake=coupon_stake,
                    total_odds=calculated,
                    name=f"{mode_label} multi",
                    bookmaker="Superbet",
                    note=mode_note,
                )
                st.success(f"Zapisano kupon multi #{coupon_id}.")
                st.rerun()
            except Exception as exc:
                st.error(f"Nie udało się zapisać kuponu multi: {exc}")

        if settle_all_manual and st.button("Sprawdź wyniki manualnych teraz", key=f"{mode_key}_settle_now"):
            updated = settle_all_manual()
            st.success(f"Rozliczono: {updated}")
            st.rerun()

    with action_tabs[2]:
        hist_tabs = st.tabs(["Single", "Multi", "Pozycje multi", "Usuń"])
        with hist_tabs[0]:
            _decision_table(mode_manual_df, ["created_at", "match_name", "league", "manual_market_label", "odds", "stake", "status", "result", "score", "profit", "roi", "bookmaker"], "Brak zapisanych zakładów pojedynczych w tym profilu.")
        with hist_tabs[1]:
            _decision_table(mode_ako_df, ["created_at", "name", "stake", "total_odds", "calculated_odds", "status", "result", "profit", "roi", "bookmaker"], "Brak zapisanych kuponów multi w tym profilu.")
        with hist_tabs[2]:
            legs_df = ako_legs_dataframe() if ako_legs_dataframe else pd.DataFrame()
            if not mode_ako_df.empty and not legs_df.empty and "coupon_id" in legs_df.columns:
                coupon_ids = set(pd.to_numeric(mode_ako_df["id"], errors="coerce").dropna().astype(int).tolist())
                legs_df = legs_df[pd.to_numeric(legs_df["coupon_id"], errors="coerce").fillna(-1).astype(int).isin(coupon_ids)].copy()
            elif mode_ako_df.empty:
                legs_df = pd.DataFrame()
            _decision_table(legs_df, ["coupon_id", "match_name", "league", "manual_market_label", "odds", "status", "result", "score"], "Brak pozycji multi w tym profilu.")
        with hist_tabs[3]:
            delete_cols = st.columns(2)
            with delete_cols[0]:
                st.subheader("Usuń zakład pojedynczy")
                if mode_manual_df.empty or delete_manual_bet is None:
                    st.info("Brak zapisanych zakładów pojedynczych w tym profilu.")
                else:
                    single_options = {f"#{int(row['id'])} | {row.get('match_name', '-')} | {row.get('manual_market_label', '-')} | {row.get('status', '-')}": int(row["id"]) for _, row in mode_manual_df.iterrows()}
                    selected_single = st.selectbox("Wybierz zakład", list(single_options.keys()), key=f"{mode_key}_delete_single_select")
                    if st.button("Usuń wybrany zakład", key=f"{mode_key}_delete_single_button"):
                        delete_manual_bet(single_options[selected_single])
                        st.success("Usunięto zakład pojedynczy.")
                        st.rerun()
            with delete_cols[1]:
                st.subheader("Usuń kupon multi")
                if mode_ako_df.empty or delete_ako_coupon is None:
                    st.info("Brak zapisanych kuponów multi w tym profilu.")
                else:
                    ako_options = {f"#{int(row['id'])} | {row.get('name', 'Kupon multi')} | {row.get('status', '-')} | kurs {row.get('total_odds', '-')}": int(row["id"]) for _, row in mode_ako_df.iterrows()}
                    selected_coupon = st.selectbox("Wybierz kupon", list(ako_options.keys()), key=f"{mode_key}_delete_multi_select")
                    if st.button("Usuń wybrany kupon", key=f"{mode_key}_delete_multi_button"):
                        delete_ako_coupon(ako_options[selected_coupon])
                        st.success("Usunięto kupon multi razem z pozycjami.")
                        st.rerun()

    with action_tabs[3]:
        mode_single_summary = manual_summary(mode_manual_df)
        mode_multi_summary = manual_summary(mode_ako_df.rename(columns={"total_odds": "odds"})) if not mode_ako_df.empty else {"total": 0, "open": 0, "winrate": 0, "profit": 0, "roi": 0}
        metrics([
            ("Single", str(mode_single_summary["total"]), "zapisane"),
            ("Multi", str(mode_multi_summary["total"]), "zapisane"),
            ("Wygrane single", str(mode_single_summary.get("wins", 0)), "rozliczone"),
            ("Profit", money(mode_single_summary["profit"] + mode_multi_summary["profit"]), "profil"),
            ("ROI", f"{mode_single_summary['roi']:+.2f}%", "single"),
        ])
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Według ligi")
            _decision_table(grouped_manual_stats(mode_manual_df, "league"), ["league", "bets", "wins", "winrate_%", "stake", "profit", "roi_%"], "Brak rozliczonych singli w tym profilu.")
        with col2:
            st.subheader("Według typu")
            _decision_table(grouped_manual_stats(mode_manual_df, "manual_market_label"), ["manual_market_label", "bets", "wins", "winrate_%", "stake", "profit", "roi_%"], "Brak rozliczonych singli w tym profilu.")


def render_manual_betting(picks_source: pd.DataFrame, low_source: pd.DataFrame | None = None, risk_source: pd.DataFrame | None = None) -> None:
    page_banner("Moje zakłady", "MOJE ZAKŁADY", "Zakłady pojedyncze i multi w trzech profilach: Standard, Niskie ryzyko i Duże ryzyko.")
    title("MOJE ZAKŁADY")

    required = [add_manual_bet, add_ako_coupon, manual_bets_dataframe, manual_summary, grouped_manual_stats]
    if not all(required):
        st.error("Moduł moich zakładów nie został załadowany.")
        return

    manual_df = manual_bets_dataframe()
    ako_df = ako_coupons_dataframe() if ako_coupons_dataframe else pd.DataFrame()
    summary = manual_summary(manual_df)
    ako_summary = manual_summary(ako_df.rename(columns={"total_odds": "odds"})) if not ako_df.empty else {"total": 0, "open": 0, "winrate": 0, "profit": 0, "roi": 0}

    metrics([
        ("Single", str(summary["total"]), "pojedyncze zakłady"),
        ("Multi", str(ako_summary["total"]), "kupony"),
        ("Otwarte", str(summary["open"] + ako_summary["open"]), "do rozliczenia"),
        ("Profit", money(summary["profit"] + ako_summary["profit"]), "manual"),
        ("ROI", f"{summary['roi']:+.2f}%", "single"),
    ])

    datasets = [
        ("standard", "Standard", picks_source if picks_source is not None else pd.DataFrame()),
        ("low", "Niskie ryzyko", low_source if low_source is not None else pd.DataFrame()),
        ("risk", "Duże ryzyko", risk_source if risk_source is not None else pd.DataFrame()),
    ]
    profile_tabs = st.tabs([label for _, label, _ in datasets])
    for tab, (mode_key, mode_label, source_df) in zip(profile_tabs, datasets):
        with tab:
            _render_manual_profile(mode_key, mode_label, source_df, manual_df, ako_df)

css()
require_login()
raw_picks = load_picks()
picks = normalize_picks(raw_picks)
low_picks = normalize_picks(load_pick_candidates(LOW_PICK_CANDIDATES))
risk_picks = normalize_picks(load_pick_candidates(RISK_PICK_CANDIDATES))
live = load_live_data(picks)
results = load_results()
ai_picks = load_ai_picks(picks)
ai_low_picks = load_ai_picks(low_picks, LOW_AI_PICKS_FILE, "low")
ai_risk_picks = load_ai_picks(risk_picks, RISK_AI_PICKS_FILE, "risk")
ai_context = pd.concat(
    [df for df in [ai_picks, ai_low_picks, ai_risk_picks] if df is not None and not df.empty],
    ignore_index=True,
    sort=False,
) if any(df is not None and not df.empty for df in [ai_picks, ai_low_picks, ai_risk_picks]) else pd.DataFrame()

tabs = st.tabs(["NA ŻYWO", "PRZEDMECZOWE", "AI", "ANALITYKA", "HISTORIA", "MOJE ZAKŁADY", "RANKING", "CZAT GPT"])
with tabs[0]: render_live(live, picks)
with tabs[1]: render_prematch(picks, low_picks, risk_picks)
with tabs[2]: render_ai(ai_picks, results, ai_low_picks, ai_risk_picks)
with tabs[3]: render_analytics(picks, results, "ANALITYKA")
with tabs[4]: render_history(results)
with tabs[5]: render_manual_betting(raw_picks, low_picks, risk_picks)
with tabs[6]: render_ranking(picks, results)
with tabs[7]: render_gpt_professional(picks, low_picks, risk_picks, live, results)
st.markdown('<div class="footer-ka"><span>KANIBAL ANALYTICS | ANALIZA. PRZEWAGA. ZYSK.</span><span>DANE AKTUALIZOWANE NA ŻYWO <span class="status-dot"></span></span></div>', unsafe_allow_html=True)
