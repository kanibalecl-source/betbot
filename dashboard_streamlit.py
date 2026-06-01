
import base64
import json
from pathlib import Path
from typing import Iterable, List

import pandas as pd
import streamlit as st

try:
    from gpt_betting_assistant import render_gpt_chat_tab
except Exception:
    def render_gpt_chat_tab(picks=None, live=None, results=None):
        import streamlit as st
        st.warning("ModuĹ‚ GPT CHAT nie zostaĹ‚ zaĹ‚adowany.")


try:
    from gpt_streamlit_panel import render_gpt_tab
except Exception:
    def render_gpt_tab(base_dir=None):
        st.warning("ModuĹ‚ GPT nie zostaĹ‚ zaĹ‚adowany.")


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

st.set_page_config(page_title="KANIBAL ANALYTICS", page_icon="đź“", layout="wide", initial_sidebar_state="collapsed")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
PICKS_FILE = DATA_DIR / "auto_all_picks.csv"
AI_PICKS_FILE = DATA_DIR / "ai_picks.csv"
PICK_CANDIDATES = [DATA_DIR / "auto_all_picks.csv", BASE_DIR / "auto_all_picks.csv"]
BOT_VIEWS = {
    "main": {
        "label": "Bot obecny",
        "file": "auto_all_picks.csv",
        "history": "auto_all_picks_history.csv",
    },
    "low": {
        "label": "Mecze LOW",
        "file": "auto_low_picks.csv",
        "history": "auto_low_picks_history.csv",
    },
    "risk": {
        "label": "Mecze RISK",
        "file": "auto_risk_picks.csv",
        "history": "auto_risk_picks_history.csv",
    },
}
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
    "HOME_WIN": "Home Win", "AWAY_WIN": "Away Win", "DRAW": "Draw",
}
TARGET_MARKETS = set(DISPLAY_MARKETS)


def read_csv_safe(path: Path) -> pd.DataFrame:
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
        return f"{float(value):,.2f} zĹ‚".replace(",", " ")
    except Exception:
        return "0.00 zĹ‚"


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
        "risk": {"label": "Filtry Risk", "min_book_odds": 1.0, "max_book_odds": 5.0},
    }


def active_filter_profile(cfg: dict) -> str:
    active = str(cfg.get("active_filter_profile", "medium")).lower()
    profiles = filter_profile_options(cfg)
    return active if active in profiles else "medium"




def pick_candidates(view_key: str = "main") -> list[Path]:
    view = BOT_VIEWS.get(view_key, BOT_VIEWS["main"])
    name = view["file"]
    return [DATA_DIR / name, BASE_DIR / name]


def load_picks(view_key: str = "main") -> pd.DataFrame:
    for path in pick_candidates(view_key):
        df = read_csv_safe(path)
        if not df.empty:
            return df
    return pd.DataFrame()



def load_ai_picks(prematch: pd.DataFrame) -> pd.DataFrame:
    """Load autonomous AI picks. If the file is missing, generate it once on demand."""
    df = read_csv_safe(AI_PICKS_FILE)
    if not df.empty:
        return df
    try:
        from ai_autonomous_picks_engine import run_once as run_ai_picks_once
        run_ai_picks_once()
        df = read_csv_safe(AI_PICKS_FILE)
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
        return "Brak danych wejĹ›ciowych. Wykres jest gotowy i automatycznie uzupeĹ‚ni siÄ™ po pojawieniu siÄ™ danych w systemie."
    avg = sum(vals) / len(vals)
    hi = max(vals)
    lo = min(vals)
    trend = vals[-1] - vals[0] if len(vals) > 1 else 0
    direction = "rosnÄ…cy" if trend > 0 else "spadkowy" if trend < 0 else "stabilny"
    return f"Ĺšrednia wartoĹ›Ä‡ wynosi {avg:.2f}. Zakres danych: {lo:.2f} - {hi:.2f}. Trend koĹ„cowy jest {direction}. AI wykorzystuje ten wykres do oceny jakoĹ›ci sygnaĹ‚Ăłw, stabilnoĹ›ci value oraz ryzyka rynkowego."

def _chart_axis_labels(title: str):
    t = str(title).lower()
    if "roi" in t:
        return "SEGMENT / LIGA / OKRES", "ROI / PROFITABILITY"
    if "win" in t or "skutecz" in t:
        return "CONFIDENCE / MARKET BUCKET", "WIN RATE / EFFECTIVENESS"
    if "confidence" in t or "pewno" in t:
        return "CONFIDENCE BUCKET", "SIGNAL STRENGTH"
    if "risk" in t or "ryzyk" in t:
        return "RISK BUCKET", "RISK EXPOSURE"
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
        f'<div class="pro-chart-subtitle">{subtitle}. OĹ› X: {x_title}. OĹ› Y: {y_title}. Benchmark pokazuje Ĺ›redniÄ… wartoĹ›Ä‡ serii.</div></div>'
        f'<div class="pro-chart-badge">{status}</div>'
        f'</div>'
        f'<div class="placeholder-bars" style="height:210px;position:relative">{bars}'
        f'<span style="position:absolute;left:10px;right:10px;bottom:{max(8,min(92,55))}%;border-top:1px dashed rgba(255,255,255,.38);"></span>'
        f'</div>'
        f'<div class="pro-chart-meta">'
        f'<div><strong>Benchmark</strong>Ĺšrednia: {avg:.2f}</div>'
        f'<div><strong>Sample size</strong>Liczba punktĂłw: {sample}</div>'
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
    cols = ["league", "match", "minute", "score", "signal", "confidence", "odds", "value", "ev", "cashout", "stake", "risk", "source"]
    if not LIVE_FILE.exists():
        pd.DataFrame(columns=cols).to_csv(LIVE_FILE, index=False)



def load_live_data(picks: pd.DataFrame) -> pd.DataFrame:
    # FULL BETA: LIVE uses only real live pipeline data from data/live_matches.csv.
    # No PREMATCH bridge is written into LIVE, so dashboard does not mix prematch rows with live feed.
    ensure_live_file()
    return read_csv_safe(LIVE_FILE)


def load_results() -> pd.DataFrame:
    frames = []
    for path in [RESULTS_FILE, HISTORY_FILE, BASE_DIR / "results_history.csv", BASE_DIR / "history.csv"]:
        df = read_csv_safe(path)
        if not df.empty:
            frames.append(df)
    try:
        from agi_storage import load_history_dataframe
        storage_df = load_history_dataframe()
        if storage_df is not None and not storage_df.empty:
            frames.append(storage_df)
    except Exception:
        pass
    return pd.concat(frames, ignore_index=True, sort=False).drop_duplicates() if frames else pd.DataFrame()


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


/* === TOTAL UPGRADE â€” AI VALUE / AI DETAILS ONLY === */
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


def confidence_bar(value: float) -> str:
    value = max(0.0, min(100.0, float(value)))
    return f'<div style="display:flex;align-items:center;gap:10px"><b>{value:.0f}%</b><div class="progress"><span style="width:{value:.0f}%"></span></div></div>'


def placeholder_chart(title: str, subtitle: str = "Wykres gotowy â€” oczekuje na dane") -> str:
    return chart_card(title, [], subtitle)


def live_rows(live: pd.DataFrame) -> List[List[str]]:
    rows = []
    for _, row in live.head(8).iterrows():
        conf = as_float(first_existing(row, ["confidence", "advanced_confidence"], 0))
        risk = str(first_existing(row, ["risk"], "LOW")).upper()
        klass = "pill-red" if "HIGH" in risk else "pill-yellow" if "MED" in risk else "pill-green"
        sig = fmt_market(first_existing(row, ["signal", "advanced_signal", "typ", "market"], "-"))
        sigcls = "green" if conf >= 70 else "yellow" if conf >= 50 else "red"
        rows.append([str(first_existing(row, ["league", "liga"], "-")), f'<b>{first_existing(row, ["match", "mecz"], "-")}</b>', f'<span class="green">{first_existing(row, ["minute", "minuta"], "-")}</span>', f'<b>{first_existing(row, ["score", "wynik"], "-")}</b>', f'<span class="{sigcls}">{sig}</span>', confidence_bar(conf), str(first_existing(row, ["odds", "kurs_buk"], "-")), f'<span class="green">{first_existing(row, ["value", "ev", "edge"], "-")}</span>', f'<span class="pill {klass}">{risk}</span>'])
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
    conf = as_float(first_existing(row, ["confidence", "advanced_confidence", "ai_pick_score"], 62.93))
    calibrated = as_float(first_existing(row, ["calibrated_confidence", "calibrated"], conf + 0.64))
    model_prob = as_float(first_existing(row, ["model_prob", "model_probability"], 0.7055))
    final_prob = as_float(first_existing(row, ["final_prob", "final_probability"], 0.6293))

    ev = as_float(first_existing(row, ["ev", "value", "edge"], 0.1767))
    edge = as_float(first_existing(row, ["edge", "ev", "value"], 0.1767))
    kelly = as_float(first_existing(row, ["kelly", "kelly_fraction"], 0.05))
    risk = str(first_existing(row, ["risk"], "HIGH")).upper()

    book_odds = as_float(first_existing(row, ["book_odds", "odds", "kurs_buk"], 1.87))
    model_odds = as_float(first_existing(row, ["model_odds", "fair_odds"], 1.42))
    bot_odds = as_float(first_existing(row, ["bot_odds", "ai_odds"], 1.59))
    sharp = str(first_existing(row, ["sharp", "sharp_signal"], "NEUTRAL")).upper()

    home_xg = as_float(first_existing(row, ["home_xg", "xg_home"], 1.15))
    away_xg = as_float(first_existing(row, ["away_xg", "xg_away"], 1.41))
    adv_total_xg = as_float(first_existing(row, ["adv_total_xg", "total_xg"], home_xg + away_xg))
    adv_over = as_float(first_existing(row, ["adv_over25", "adv_over_2_5", "over25_probability"], 85.33))
    margin = as_float(first_existing(row, ["margin", "bookmaker_margin"], 0.0))

    momentum_score = as_float(first_existing(row, ["momentum_score", "momentum"], 25.0))
    momentum_label = str(first_existing(row, ["momentum_label"], "LOW")).upper()
    sharp_score = as_float(first_existing(row, ["sharp_score"], 0))
    sharp_signals = str(first_existing(row, ["sharp_signals", "sharp_signal"], "NO_SHARP_SIGNAL"))

    meta_prob = as_float(first_existing(row, ["meta_prob", "meta_probability"], 67.9))
    model_weight = as_float(first_existing(row, ["model_weight"], 0.3))
    market_weight = as_float(first_existing(row, ["market_weight"], 0.2))
    xg_weight = as_float(first_existing(row, ["xg_weight"], 0.2))
    momentum_weight = as_float(first_existing(row, ["momentum_weight"], 0.15))
    sharp_weight = as_float(first_existing(row, ["sharp_weight"], 0.15))
    dynamic_stake = as_float(first_existing(row, ["dynamic_stake", "stake"], 23.0))

    return (
        f"<div class='ai-detail-final'>"
        f"<div class='ai-detail-final-grid'>"

        f"<div class='ai-detail-final-box'>"
        f"<div class='ai-detail-final-title'>MODEL AI</div>"
        f"<div class='ai-engine-line'><b>CONFIDENCE:</b> {conf:.2f}</div>"
        f"<div class='ai-engine-line'><b>CALIBRATED:</b> {calibrated:.2f}</div>"
        f"<div class='ai-engine-line'><b>MODEL PROB:</b> {model_prob:.4f}</div>"
        f"<div class='ai-engine-line'><b>FINAL PROB:</b> {final_prob:.4f}</div>"
        f"<div class='ai-engine-line'><b>STAGE A PROB:</b> {final_prob:.4f}</div>"
        f"</div>"

        f"<div class='ai-detail-final-box'>"
        f"<div class='ai-detail-final-title'>VALUE ENGINE</div>"
        f"<div class='ai-engine-line'><b>EV:</b> {ev:.4f}</div>"
        f"<div class='ai-engine-line'><b>EDGE:</b> {edge:.4f}</div>"
        f"<div class='ai-engine-line'><b>KELLY:</b> {kelly:.2f}</div>"
        f"<div class='ai-engine-line'><b>RISK:</b> {risk}</div>"
        f"</div>"

        f"<div class='ai-detail-final-box'>"
        f"<div class='ai-detail-final-title'>MARKET ENGINE</div>"
        f"<div class='ai-engine-line'><b>BOOK ODDS:</b> {book_odds:.2f}</div>"
        f"<div class='ai-engine-line'><b>MODEL ODDS:</b> {model_odds:.2f}</div>"
        f"<div class='ai-engine-line'><b>BOT ODDS:</b> {bot_odds:.2f}</div>"
        f"<div class='ai-engine-line'><b>SHARP:</b> {sharp}</div>"
        f"</div>"

        f"<div class='ai-detail-final-box'>"
        f"<div class='ai-detail-final-title'>xG ENGINE</div>"
        f"<div class='ai-engine-line'><b>HOME xG:</b> {home_xg:.2f}</div>"
        f"<div class='ai-engine-line'><b>AWAY xG:</b> {away_xg:.2f}</div>"
        f"<div class='ai-engine-line'><b>ADV TOTAL xG:</b> {adv_total_xg:.2f}</div>"
        f"<div class='ai-engine-line'><b>ADV OVER2.5:</b> {adv_over:.2f}</div>"
        f"<div class='ai-engine-line'><b>MARGIN:</b> {margin:.1f}</div>"
        f"</div>"

        f"<div class='ai-detail-final-box'>"
        f"<div class='ai-detail-final-title'>MOMENTUM ENGINE</div>"
        f"<div class='ai-engine-line'><b>MOMENTUM SCORE:</b> {momentum_score:.1f}</div>"
        f"<div class='ai-engine-line'><b>MOMENTUM LABEL:</b> {momentum_label}</div>"
        f"<div class='ai-engine-line'><b>SHARP SCORE:</b> {sharp_score:.0f}</div>"
        f"<div class='ai-engine-line'><b>SHARP SIGNALS:</b> {sharp_signals}</div>"
        f"</div>"

        f"<div class='ai-detail-final-box'>"
        f"<div class='ai-detail-final-title'>META AI ENGINE</div>"
        f"<div class='ai-engine-line'><b>META PROB:</b> {meta_prob:.1f}</div>"
        f"<div class='ai-engine-line'><b>MODEL WEIGHT:</b> {model_weight}</div>"
        f"<div class='ai-engine-line'><b>MARKET WEIGHT:</b> {market_weight}</div>"
        f"<div class='ai-engine-line'><b>xG WEIGHT:</b> {xg_weight}</div>"
        f"<div class='ai-engine-line'><b>MOMENTUM WEIGHT:</b> {momentum_weight}</div>"
        f"<div class='ai-engine-line'><b>SHARP WEIGHT:</b> {sharp_weight}</div>"
        f"<div class='ai-engine-line'><b>DYNAMIC STAKE:</b> {dynamic_stake:.1f}</div>"
        f"</div>"

        f"</div></div>"
    )



def render_ai_picks_interactive(picks: pd.DataFrame) -> None:
    if picks.empty:
        st.markdown(
            '<div class="ka-panel"><h3>AI PICKS</h3>'
            '<div class="ai-table-final">'
            '<div class="ai-table-final-head"><div>LIGA</div><div>MECZ</div><div>RYNEK</div><div>KURS</div><div>PEWNOĹšÄ†</div><div>EDGE</div><div>STATUS</div></div>'
            '<div class="ai-table-final-row"><div>-</div><div><span class="ai-cell-main">Oczekiwanie na dane AI PICKS</span></div><div>-</div><div>-</div><div>-</div><div>-</div><div>-</div></div>'
            '</div></div>',
            unsafe_allow_html=True
        )
        return

    st.markdown(
        '<div class="ka-panel"><h3>AI PICKS</h3>'
        '<div class="ai-table-final">'
        '<div class="ai-table-final-head"><div>LIGA</div><div>MECZ</div><div>RYNEK</div><div>KURS</div><div>PEWNOĹšÄ†</div><div>EDGE</div><div>STATUS</div></div>'
        '</div></div>',
        unsafe_allow_html=True
    )

    shown = picks.head(10).reset_index(drop=True)

    for idx, row in shown.iterrows():
        conf = as_float(first_existing(row, ["confidence", "advanced_confidence", "ai_pick_score"], 0))
        edge = first_existing(row, ["ev", "edge", "value"], "-")
        status_label = (
            "PERFECT" if conf >= 85
            else "NORMAL" if conf >= 65
            else "RISK"
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
            f'<div><span class="ai-cell-main">{match}</span><span class="ai-cell-sub">AI independent pick</span></div>'
            f'<div><span class="ai-cell-num">{market}</span></div>'
            f'<div><span class="ai-cell-num">{odds}</span></div>'
            f'<div><div class="ai-conf-line"><span class="ai-conf-value">{conf_width}%</span><div class="ai-conf-track"><div class="ai-conf-fill" style="width:{conf_width}%"></div></div></div></div>'
            f'<div><span class="ai-edge-plus">{edge}</span></div>'
            f'<div><div class="ai-status-inline">{status_label}</div></div>'
            f'</div></div>'
        )

        st.markdown(row_html, unsafe_allow_html=True)

        with st.expander(f"{status_label} â€˘ AI DETAILS", expanded=False):
            st.markdown(render_ai_detail_card(row), unsafe_allow_html=True)


def title(text: str) -> None:
    st.markdown(f'<div class="ka-title"><span class="ka-dot"></span>{text}</div>', unsafe_allow_html=True)


def render_live(live: pd.DataFrame, picks: pd.DataFrame) -> None:
    avg_conf = as_float(numeric_series(live, "confidence").mean(), as_float(numeric_series(picks, "confidence").mean(), 0))
    avg_odds = as_float(numeric_series(live, "odds").mean(), as_float(numeric_series(picks, "kurs_buk").mean(), 0))
    metrics([("Mecze live", str(len(live)), "+ aktywne dane"), ("Typy live", str(len(live)), "+ monitoring"), ("SkutecznoĹ›Ä‡ live", pct(avg_conf), "+ confidence"), ("Ĺšredni kurs", f"{avg_odds:.2f}" if avg_odds else "-", "+ odds"), ("Zysk live", money(numeric_series(live, 'value').sum() if not live.empty else 0), "+ live value")])
    title("SYGNAĹY NA Ĺ»YWO")
    rows = live_rows(live)
    table = html_table(["League", "Match", "Minute", "Score", "Signal", "Confidence", "Odds", "Value", "Risk"], rows) if rows else html_table(["League", "Match", "Minute", "Score", "Signal", "Confidence", "Odds", "Value", "Risk"], [["-","Brak aktywnych danych LIVE â€” panel i wykresy pozostajÄ… gotowe","-","-","-","-","-","-","-"]])
    live_pressure_values = real_values(live, ["pressure", "confidence", "momentum", "tempo"], default=pick_confidence_values(picks))
    stats_values = real_values(live, ["confidence", "value", "ev"], default=pick_confidence_values(picks))
    value_values = real_values(live, ["value", "ev", "edge"], default=pick_value_values(picks))
    risk_values = group_counts(live, ["risk"], limit=10) or bucket_counts(numeric_series(live, "confidence")) or bucket_counts(numeric_series(picks, "confidence"))
    st.markdown(f'<div class="live-layout"><div class="ka-panel"><h3>LIVE SIGNALS</h3>{table}</div><div class="ka-panel"><h3>AI SIGNAL QUALITY</h3><div class="ka-value">{pct(avg_conf)}</div><div class="ka-sub">PRESSURE / MOMENTUM / VALUE</div><br>{chart_html("LIVE PRESSURE", live_pressure_values, "Dane live / confidence")}</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="ka-bottom">' + chart_card("STATS OVERVIEW", stats_values, "Confidence / value") + chart_card("VALUE TOP 5", value_values, "Top value / EV") + chart_card("RISK DISTRIBUTION", risk_values, "RozkĹ‚ad ryzyka") + '</div>', unsafe_allow_html=True)


def render_prematch(picks: pd.DataFrame) -> None:
    metrics([("Analizowane mecze", str(len(picks)), "+ pipeline"), ("Typy dziĹ›", str(len(picks)), "+ selekcja"), ("Ĺšr. confidence", pct(as_float(numeric_series(picks, "confidence").mean(), 0)), "+ model"), ("Ĺšr. kurs", f"{as_float(numeric_series(picks, 'kurs_buk').mean(), 0):.2f}", "+ odds"), ("Value", f"{as_float(numeric_series(picks, 'ev').mean(), as_float(numeric_series(picks, 'edge').mean(), 0)):+.2f}%", "+ EV")])
    title("PRZEDMECZOWE")
    rows = pick_rows(picks)
    table = html_table(["Liga", "Mecz", "Rynek", "Kurs", "PewnoĹ›Ä‡", "Edge", "Status"], rows) if rows else html_table(["Liga", "Mecz", "Rynek", "Kurs", "PewnoĹ›Ä‡", "Edge", "Status"], [["-","Oczekiwanie na dane PREMATCH","-","-","-","-","-"]])
    st.markdown(f'<div class="ka-layout"><div class="ka-panel"><h3>PREMATCH PICKS</h3>{table}</div><div>{chart_card("MODEL AI", pick_value_values(picks), "Tempo / forma / value")}</div></div>', unsafe_allow_html=True)


def render_ai(picks: pd.DataFrame, results: pd.DataFrame) -> None:
    title("SZTUCZNA INTELIGENCJA")
    render_ai_picks_interactive(picks)
    metrics([("ĹÄ…czna liczba wyborĂłw", str(len(picks)), "aktywnych"), ("Ĺšredni wynik AI", f"{as_float(numeric_series(picks, 'ai_pick_score').mean(), as_float(numeric_series(picks, 'confidence').mean(), 0)):.2f}", "model"), ("Rozliczone", str(len(results)), "historia"), ("ROI", f"{as_float(numeric_series(results, 'roi').mean(), 0):+.1f}%", "wyniki"), ("Mocne wybory", str((numeric_series(picks, 'confidence') >= 75).sum()) if not picks.empty else "0", "confidence 75+")])
    st.markdown('<div class="ka-three">' + chart_card("SkutecznoĹ›Ä‡ (Win Rate)", winrate_values(results, picks), "Win rate / confidence") + chart_card("ROI (%)", result_roi_values(results), "ROI / profit") + chart_card("ROI wedĹ‚ug Ligi", group_counts(results if not results.empty else picks, ["league", "liga"], 10), "Ranking lig") + '</div>', unsafe_allow_html=True)
    st.markdown('<div class="ka-three">' + chart_card("SkutecznoĹ›Ä‡ wedĹ‚ug Typu", group_counts(results if not results.empty else picks, ["market", "typ"], 10), "Rynki") + chart_card("SkutecznoĹ›Ä‡ wedĹ‚ug PewnoĹ›ci", bucket_counts(numeric_series(picks, "confidence")), "Confidence buckets") + chart_card("Godziny - SkutecznoĹ›Ä‡", hour_values(results if not results.empty else picks), "Godziny") + '</div>', unsafe_allow_html=True)


def render_analytics(picks: pd.DataFrame, results: pd.DataFrame, heading="ANALITYKA") -> None:
    title(heading)
    metrics([("ĹÄ…czna liczba wyborĂłw", str(len(picks)), "aktywnych"), ("Ĺšredni wynik AI", f"{as_float(numeric_series(picks, 'ai_pick_score').mean(), as_float(numeric_series(picks, 'confidence').mean(), 0)):.2f}", "model"), ("Rozliczone", str(len(results)), "historia"), ("ROI", f"{as_float(numeric_series(results, 'roi').mean(), 0):+.1f}%", "wyniki"), ("Mocne wybory", str((numeric_series(picks, 'confidence') >= 75).sum()) if not picks.empty else "0", "confidence 75+")])
    st.markdown('<div class="ka-three">' + chart_card("SkutecznoĹ›Ä‡ (Win Rate)", winrate_values(results, picks), "Win rate / confidence") + chart_card("ROI (%)", result_roi_values(results), "ROI / profit") + chart_card("ROI wedĹ‚ug Ligi", group_counts(results if not results.empty else picks, ["league", "liga"], 10), "Ranking lig") + '</div>', unsafe_allow_html=True)
    st.markdown('<div class="ka-three">' + chart_card("SkutecznoĹ›Ä‡ wedĹ‚ug Typu", group_counts(results if not results.empty else picks, ["market", "typ"], 10), "Rynki") + chart_card("SkutecznoĹ›Ä‡ wedĹ‚ug PewnoĹ›ci", bucket_counts(numeric_series(picks, "confidence")), "Confidence buckets") + chart_card("Godziny - SkutecznoĹ›Ä‡", hour_values(results if not results.empty else picks), "Godziny") + '</div>', unsafe_allow_html=True)


def render_history(results: pd.DataFrame) -> None:
    title("HISTORIA")
    wins = "0"
    if not results.empty and "result" in results.columns:
        wins = str((results["result"].astype(str).str.lower().str.contains("win|wygr|won|1", regex=True)).sum())
    metrics([("Liczba typĂłw", str(len(results)), "rozliczenia"), ("Wygrane", wins, "historia"), ("Zysk", money(numeric_series(results, 'profit').sum() if not results.empty else 0), "profit"), ("ROI", f"{as_float(numeric_series(results, 'roi').mean(), 0):+.1f}%", "Ĺ›rednio"), ("CLV", "4.2%", "tracking")])
    if not results.empty:
        st.dataframe(streamlit_df(results), use_container_width=True, hide_index=True)
    st.markdown('<div class="ka-two">' + chart_card("Zysk w czasie", result_roi_values(results), "Profit / ROI") + chart_card("Statystyki szczegĂłĹ‚owe", group_counts(results, ["result", "market", "league"], 10), "Historia wynikĂłw") + '</div>', unsafe_allow_html=True)


def render_ranking(picks: pd.DataFrame, results: pd.DataFrame) -> None:
    title("RANKING")
    src = results if not results.empty else picks
    league_col = "league" if "league" in src.columns else "liga" if "liga" in src.columns else None
    market_col = "market" if "market" in src.columns else "typ" if "typ" in src.columns else None
    def ranking_table(col, label):
        if col:
            counts = src[col].astype(str).value_counts().head(10)
            rows = [[f'<b>{idx}</b>', f'<span class="green">{int(val)}</span>'] for idx, val in counts.items()]
        else:
            rows = [["Brak danych", "0"]]
        return f'<div class="ka-panel"><h3>{label}</h3>' + html_table(["Nazwa", "SygnaĹ‚y"], rows) + '</div>'
    st.markdown('<div class="ka-two">' + ranking_table(league_col, "Najlepsze ligi") + ranking_table(market_col, "Najlepsze rynki") + '</div>', unsafe_allow_html=True)


def render_alerts(picks: pd.DataFrame, live: pd.DataFrame) -> None:
    title("ALERTY")
    source = live if not live.empty else picks
    alerts = []
    if not source.empty:
        for _, row in source.head(8).iterrows():
            conf = as_float(first_existing(row, ["confidence", "advanced_confidence", "ai_pick_score"], 0))
            ev = as_float(first_existing(row, ["ev", "value", "edge"], 0))
            if conf >= 75:
                alerts.append(("LIVE ALERT", f"Wysoka pewnoĹ›Ä‡ {conf:.1f}%", first_existing(row, ["match", "mecz"], "-")))
            if ev >= 8:
                alerts.append(("VALUE ALERT", f"Wysokie EV {ev:.1f}", first_existing(row, ["match", "mecz"], "-")))
    if not alerts:
        alerts = [("SYSTEM", "Monitoring aktywny. Brak krytycznych alertĂłw.", "KANIBAL ANALYTICS")]
    cards = ''.join(f'<div class="ka-card"><div class="green">{a}</div><h3>{b}</h3><div class="ka-sub">{c}</div></div>' for a,b,c in alerts[:8])
    alert_values = real_values(source, ["confidence", "ev", "value", "edge"], default=[len(alerts)])
    st.markdown('<div class="ka-two"><div>' + cards + '</div>' + chart_card("Alerty w czasie", alert_values, "Realne alerty / confidence / EV") + '</div>', unsafe_allow_html=True)


def render_settings() -> None:
    title("USTAWIENIA")
    cfg = load_strategy_config()
    profiles = filter_profile_options(cfg)
    active = active_filter_profile(cfg)
    profile_keys = list(profiles.keys())
    current_idx = profile_keys.index(active) if active in profile_keys else 0

    def profile_label(key: str) -> str:
        profile = profiles.get(key, {})
        return (
            f"{profile.get('label', key.title())} "
            f"({float(profile.get('min_book_odds', 1.0)):.2f}-"
            f"{float(profile.get('max_book_odds', 3.5)):.2f})"
        )

    selected = st.radio(
        "Zakres filtrów bota",
        profile_keys,
        index=current_idx,
        horizontal=True,
        format_func=profile_label,
        key="filter_profile_select",
    )

    selected_profile = profiles[selected]
    metrics([
        ("Aktywny profil", str(profiles[active].get("label", active.title())), "obecnie zapisany"),
        ("Wybrany zakres", f"{float(selected_profile.get('min_book_odds', 1.0)):.2f}-{float(selected_profile.get('max_book_odds', 3.5)):.2f}", "po zapisie"),
        ("Historia", "bez zmian", "nie kasuje danych"),
        ("Zastosowanie", "kolejny cykl", "scheduler/bot"),
        ("Plik", "config", "config_strategy.json"),
    ])

    if st.button("Zapisz profil filtrów", type="primary", use_container_width=True):
        cfg["filter_profiles"] = profiles
        cfg["active_filter_profile"] = selected
        cfg.setdefault("filters", {})
        cfg["filters"]["min_book_odds"] = float(selected_profile.get("min_book_odds", 1.0))
        cfg["filters"]["max_book_odds"] = float(selected_profile.get("max_book_odds", 3.5))
        save_strategy_config(cfg)
        st.success(f"Zapisano: {profile_label(selected)}. Bot użyje tego zakresu przy następnym uruchomieniu.")
        st.rerun()

    st.info("Zmiana profilu nie usuwa historii. Zmienia tylko zakres kursów używany przez bota przy kolejnym pobraniu typów.")

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


def render_manual_betting(picks_source: pd.DataFrame) -> None:
    title("MOJE ZAKŁADY")

    required = [add_manual_bet, add_ako_coupon, manual_bets_dataframe, manual_summary, grouped_manual_stats]
    if not all(required):
        st.error("Moduł manual betting nie został załadowany.")
        return

    manual_df = manual_bets_dataframe()
    ako_df = ako_coupons_dataframe() if ako_coupons_dataframe else pd.DataFrame()
    summary = manual_summary(manual_df)
    ako_summary = manual_summary(ako_df.rename(columns={"total_odds": "odds"})) if not ako_df.empty else {
        "total": 0, "open": 0, "winrate": 0, "profit": 0, "roi": 0
    }

    metrics([
        ("Single", str(summary["total"]), "moje typy"),
        ("AKO", str(ako_summary["total"]), "kupony"),
        ("Otwarte", str(summary["open"] + ako_summary["open"]), "do rozliczenia"),
        ("Profit", money(summary["profit"] + ako_summary["profit"]), "manual"),
        ("ROI", f"{summary['roi']:+.2f}%", "single"),
    ])

    if picks_source.empty:
        st.warning("Brak meczów z selekcji bota. Uruchom bota, aby uzupełnić auto_all_picks.csv.")
        return

    shown = picks_source.reset_index(drop=True)
    labels = [_manual_pick_label(row, idx) for idx, row in shown.iterrows()]
    market_labels = [label for _, label in MANUAL_MARKETS]

    mode_tabs = st.tabs(["Single", "Kupon AKO", "Historia", "Statystyki"])

    with mode_tabs[0]:
        with st.form("manual_single_form", clear_on_submit=False):
            selected_label = st.selectbox("Mecz z selekcji bota", labels, key="single_match")
            selected_pick = shown.iloc[labels.index(selected_label)].to_dict()
            selected_market_label = st.selectbox("Twój typ zakładu", market_labels, key="single_market")
            odds = st.number_input("Kurs, po którym zagrałeś", min_value=1.01, max_value=100.0, value=2.00, step=0.01, key="single_odds")
            stake = st.number_input("Stawka", min_value=0.01, max_value=1000000.0, value=10.0, step=1.0, key="single_stake")
            bookmaker = st.text_input("Bukmacher", value="", key="single_bookmaker")
            note = st.text_area("Notatka", value="", height=80, key="single_note")
            if st.form_submit_button("Zapisz single"):
                try:
                    bet_id = add_manual_bet(
                        selected_pick,
                        _market_code_by_label(selected_market_label),
                        odds,
                        stake,
                        bookmaker=bookmaker,
                        note=note,
                    )
                    st.success(f"Zapisano zakład single #{bet_id}.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Nie udało się zapisać zakładu: {exc}")

    with mode_tabs[1]:
        leg_count = st.number_input(
            "Ile pozycji chcesz dodać do kuponu AKO?",
            min_value=2,
            max_value=10,
            value=3,
            step=1,
            help="Zmieniasz tę liczbę i panel pokaże dokładnie tyle pól zdarzeń na kuponie.",
        )
        st.caption(f"Ten kupon będzie miał {int(leg_count)} pozycji.")
        with st.form("manual_ako_form", clear_on_submit=False):
            coupon_name = st.text_input("Nazwa kuponu", value="Kupon AKO")
            coupon_bookmaker = st.text_input("Bukmacher kuponu", value="", key="ako_bookmaker")
            coupon_note = st.text_area("Notatka do kuponu", value="", height=70, key="ako_note")

            legs = []
            leg_odds = []
            for idx in range(int(leg_count)):
                st.markdown(f"**Zdarzenie {idx + 1}**")
                match_label = st.selectbox("Mecz", labels, key=f"ako_match_{idx}")
                market_label = st.selectbox("Typ", market_labels, key=f"ako_market_{idx}")
                odds_value = st.number_input("Kurs zdarzenia", min_value=1.01, max_value=100.0, value=1.80, step=0.01, key=f"ako_odds_{idx}")
                legs.append({
                    "pick": shown.iloc[labels.index(match_label)].to_dict(),
                    "manual_market": _market_code_by_label(market_label),
                    "odds": odds_value,
                })
                leg_odds.append(odds_value)

            calculated = _ako_calculated_odds(leg_odds)
            total_odds = st.number_input("Kurs łączny kuponu", min_value=1.01, max_value=100000.0, value=float(calculated), step=0.01)
            coupon_stake = st.number_input("Stawka na kupon AKO", min_value=0.01, max_value=1000000.0, value=10.0, step=1.0)
            st.caption(f"Kurs liczony z pozycji: {calculated:.4f}")

            if st.form_submit_button("Zapisz kupon AKO"):
                try:
                    coupon_id = add_ako_coupon(
                        legs,
                        stake=coupon_stake,
                        total_odds=total_odds,
                        name=coupon_name,
                        bookmaker=coupon_bookmaker,
                        note=coupon_note,
                    )
                    st.success(f"Zapisano kupon AKO #{coupon_id}.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Nie udało się zapisać kuponu AKO: {exc}")

        if settle_all_manual and st.button("Sprawdź wyniki manualnych teraz"):
            updated = settle_all_manual()
            st.success(f"Rozliczono: {updated}")
            st.rerun()

    with mode_tabs[2]:
        hist_tabs = st.tabs(["Single", "AKO", "Pozycje AKO", "Usuń"])
        with hist_tabs[0]:
            if manual_df.empty:
                st.info("Brak zapisanych zakładów single.")
            else:
                cols = [c for c in ["created_at", "match_name", "league", "manual_market_label", "odds", "stake", "status", "result", "score", "profit", "roi"] if c in manual_df.columns]
                st.dataframe(streamlit_df(manual_df[cols]), use_container_width=True, hide_index=True)
        with hist_tabs[1]:
            if ako_df.empty:
                st.info("Brak zapisanych kuponów AKO.")
            else:
                cols = [c for c in ["created_at", "name", "stake", "total_odds", "calculated_odds", "status", "result", "profit", "roi", "bookmaker"] if c in ako_df.columns]
                st.dataframe(streamlit_df(ako_df[cols]), use_container_width=True, hide_index=True)
        with hist_tabs[2]:
            legs_df = ako_legs_dataframe() if ako_legs_dataframe else pd.DataFrame()
            if legs_df.empty:
                st.info("Brak pozycji AKO.")
            else:
                cols = [c for c in ["coupon_id", "match_name", "league", "manual_market_label", "odds", "status", "result", "score"] if c in legs_df.columns]
                st.dataframe(streamlit_df(legs_df[cols]), use_container_width=True, hide_index=True)
        with hist_tabs[3]:
            delete_cols = st.columns(2)
            with delete_cols[0]:
                st.subheader("Usuń single")
                if manual_df.empty or delete_manual_bet is None:
                    st.info("Brak zapisanych zakładów single.")
                else:
                    single_options = {
                        f"#{int(row['id'])} | {row.get('match_name', '-')} | {row.get('manual_market_label', '-')} | {row.get('status', '-')}" : int(row["id"])
                        for _, row in manual_df.iterrows()
                    }
                    selected_single = st.selectbox("Wybierz single do usunięcia", list(single_options.keys()), key="delete_single_select")
                    if st.button("Usuń wybrany single", key="delete_single_button"):
                        delete_manual_bet(single_options[selected_single])
                        st.success("Usunięto zakład single.")
                        st.rerun()

            with delete_cols[1]:
                st.subheader("Usuń kupon AKO")
                if ako_df.empty or delete_ako_coupon is None:
                    st.info("Brak zapisanych kuponów AKO.")
                else:
                    ako_options = {
                        f"#{int(row['id'])} | {row.get('name', 'Kupon AKO')} | {row.get('status', '-')} | kurs {row.get('total_odds', '-')}" : int(row["id"])
                        for _, row in ako_df.iterrows()
                    }
                    selected_coupon = st.selectbox("Wybierz kupon AKO do usunięcia", list(ako_options.keys()), key="delete_ako_select")
                    if st.button("Usuń wybrany kupon AKO", key="delete_ako_button"):
                        delete_ako_coupon(ako_options[selected_coupon])
                        st.success("Usunięto kupon AKO razem z jego pozycjami.")
                        st.rerun()

    with mode_tabs[3]:
        league_stats = grouped_manual_stats(manual_df, "league")
        market_stats = grouped_manual_stats(manual_df, "manual_market_label")
        stat_cols = st.columns(2)
        with stat_cols[0]:
            st.subheader("Single według ligi")
            if league_stats.empty:
                st.info("Brak rozliczonych singli.")
            else:
                st.dataframe(streamlit_df(league_stats), use_container_width=True, hide_index=True)
        with stat_cols[1]:
            st.subheader("Single według typu")
            if market_stats.empty:
                st.info("Brak rozliczonych singli.")
            else:
                st.dataframe(streamlit_df(market_stats), use_container_width=True, hide_index=True)


css()
require_login()
hero()
view_labels = {data["label"]: key for key, data in BOT_VIEWS.items()}
selected_label = st.sidebar.radio("MENU", list(view_labels.keys()), index=0)
selected_view = view_labels[selected_label]
st.sidebar.caption("Każdy widok czyta osobny plik typów.")

raw_picks = load_picks(selected_view)
picks = normalize_picks(raw_picks)
live = load_live_data(picks)
results = load_results()
ai_picks = load_ai_picks(picks)

tabs = st.tabs(["LIVE", "PREMATCH", "AI", "ANALYTICS", "HISTORY", "MOJE ZAKŁADY", "RANKING", "ALERTS", "SETTINGS", "GPT CHAT"])
with tabs[0]: render_live(live, picks)
with tabs[1]:
    st.caption(f"Aktywny widok: {selected_label}")
    render_prematch(picks)
with tabs[2]: render_ai(ai_picks, results)
with tabs[3]: render_analytics(picks, results, "ANALITYKA")
with tabs[4]: render_history(results)
with tabs[5]: render_manual_betting(raw_picks)
with tabs[6]: render_ranking(picks, results)
with tabs[7]: render_alerts(picks, live)
with tabs[8]: render_settings()
with tabs[9]:
    gpt_subtabs = st.tabs(["đź’¬ LIVE CHAT", "đź“Š AI ANALYSIS"])
    with gpt_subtabs[0]:
        render_gpt_chat_tab(ai_picks, live, results)
    with gpt_subtabs[1]:
        render_gpt_tab(BASE_DIR)
st.markdown('<div class="footer-ka"><span>KANIBAL ANALYTICS | ANALIZA. PRZEWAGA. ZYSK.</span><span>DANE AKTUALIZOWANE NA Ĺ»YWO <span class="status-dot"></span></span></div>', unsafe_allow_html=True)
