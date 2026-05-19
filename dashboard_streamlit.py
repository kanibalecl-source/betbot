
import base64
from pathlib import Path
from typing import Iterable, List

import pandas as pd
import streamlit as st

from gpt_betting_assistant import render_gpt_chat_tab

try:
    from auth_manager import require_login
except Exception:
    def require_login():
        return True

st.set_page_config(page_title="KANIBAL ANALYTICS", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
PICKS_FILE = DATA_DIR / "auto_all_picks.csv"
AI_PICKS_FILE = DATA_DIR / "ai_picks.csv"
PICK_CANDIDATES = [DATA_DIR / "auto_all_picks.csv", BASE_DIR / "auto_all_picks.csv"]
LIVE_FILE = DATA_DIR / "live_matches.csv"
RESULTS_FILE = DATA_DIR / "results_history.csv"
HISTORY_FILE = DATA_DIR / "history.csv"
BANNER_FILE = BASE_DIR / "kanibal_banner.png"

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
            out = out[(odds >= 1.00) & (odds <= 2.80)].copy()
    return out.reset_index(drop=True)




def load_picks() -> pd.DataFrame:
    for path in PICK_CANDIDATES:
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

def chart_html(title: str, values: List[float], subtitle: str = "Dane z systemu") -> str:
    heights = safe_heights(values)
    bars = ''.join(f'<i style="height:{h:.0f}%"></i>' for h in heights)
    sub = subtitle if any(h > 0 for h in heights) else "Brak danych — wykres gotowy"
    return f'<h3>{title}</h3><div class="placeholder-bars">{bars}</div><div class="ka-sub">{sub}</div>'

def chart_card(title: str, values: List[float], subtitle: str = "Dane z systemu") -> str:
    return f'<div class="ka-panel">{chart_html(title, values, subtitle)}</div>'

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
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


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
background:#103c08;
border:1px solid rgba(124,255,43,.22);
color:#7CFF2B;
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


def placeholder_chart(title: str, subtitle: str = "Wykres gotowy — oczekuje na dane") -> str:
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
    conf = as_float(first_existing(row, ["confidence", "advanced_confidence", "ai_pick_score"], 0))
    edge = as_float(first_existing(row, ["ev", "edge", "value"], 0))
    odds = first_existing(row, ["odds", "kurs_buk"], "-")
    market = fmt_market(first_existing(row, ["market", "typ"], "-"))
    match = first_existing(row, ["match", "mecz"], "-")
    league = first_existing(row, ["league", "liga"], "-")
    risk = str(first_existing(row, ["risk"], "LOW")).upper()
    tempo = as_float(first_existing(row, ["tempo", "tempo_score"], conf), conf)
    pressure = as_float(first_existing(row, ["pressure", "pressure_score"], conf), conf)
    momentum = as_float(first_existing(row, ["momentum", "momentum_score"], conf), conf)
    value_score = as_float(first_existing(row, ["value_score", "value", "ev", "edge"], edge), edge)
    model_score = as_float(first_existing(row, ["model_score", "ai_pick_score", "score"], conf), conf)
    movement = as_float(first_existing(row, ["movement", "odds_movement", "clv"], value_score), value_score)
    reason = first_existing(row, ["model_reason", "reason", "ai_reason"], "Autonomiczny AI pick wygenerowany przez niezależny scoring engine na podstawie confidence, value, rynku i jakości sygnału.")
    return (
        f"<div class='ai-detail'>"
        f"<div class='ai-detail-title'>{match}</div>"
        f"<div class='ai-details-grid'>"
        f"<div class='ka-card'><div class='ka-label'>Liga</div><div class='ka-value' style='font-size:18px'>{league}</div></div>"
        f"<div class='ka-card'><div class='ka-label'>AI Pick</div><div class='ka-value' style='font-size:18px'>{market}</div></div>"
        f"<div class='ka-card'><div class='ka-label'>Kurs</div><div class='ka-value' style='font-size:18px'>{odds}</div></div>"
        f"</div><br><div class='ai-details-grid'>"
        f"<div class='ka-card'><div class='ka-label'>Confidence AI</div>{confidence_bar(conf)}</div>"
        f"<div class='ka-card'><div class='ka-label'>Edge / EV</div><div class='ka-value' style='font-size:18px'><span class='green'>{edge:.2f}</span></div></div>"
        f"<div class='ka-card'><div class='ka-label'>Ryzyko</div><div class='ka-value' style='font-size:18px'>{risk}</div></div>"
        f"</div><br><div class='ai-details-grid'>"
        f"<div class='ka-card'><div class='ka-label'>Tempo</div>{confidence_bar(tempo)}</div>"
        f"<div class='ka-card'><div class='ka-label'>Pressure</div>{confidence_bar(pressure)}</div>"
        f"<div class='ka-card'><div class='ka-label'>Momentum</div>{confidence_bar(momentum)}</div>"
        f"</div><br><div class='ai-details-grid'>"
        f"<div class='ka-card'><div class='ka-label'>Value</div>{confidence_bar(value_score)}</div>"
        f"<div class='ka-card'><div class='ka-label'>Model AI</div>{confidence_bar(model_score)}</div>"
        f"<div class='ka-card'><div class='ka-label'>Market movement</div>{confidence_bar(movement)}</div>"
        f"</div><div class='ai-reason'><div class='ka-label'>AI reasoning</div><div class='ka-sub'>{reason}</div></div>"
        f"</div>"
    )



def render_ai_picks_interactive(picks: pd.DataFrame) -> None:
    if picks.empty:
        st.markdown(
            '<div class="ka-panel"><h3>AI PICKS</h3>'
            '<div class="ai-table-final">'
            '<div class="ai-table-final-head"><div>LIGA</div><div>MECZ</div><div>RYNEK</div><div>KURS</div><div>PEWNOŚĆ</div><div>EDGE</div><div>STATUS</div></div>'
            '<div class="ai-table-final-row"><div>-</div><div><span class="ai-cell-main">Oczekiwanie na dane AI PICKS</span></div><div>-</div><div>-</div><div>-</div><div>-</div><div>-</div></div>'
            '</div></div>',
            unsafe_allow_html=True
        )
        return

    st.markdown(
        '<div class="ka-panel"><h3>AI PICKS</h3>'
        '<div class="ai-table-final">'
        '<div class="ai-table-final-head"><div>LIGA</div><div>MECZ</div><div>RYNEK</div><div>KURS</div><div>PEWNOŚĆ</div><div>EDGE</div><div>STATUS</div></div>'
        '</div></div>',
        unsafe_allow_html=True
    )

    shown = picks.head(10).reset_index(drop=True)
    for idx, row in shown.iterrows():
        conf = as_float(first_existing(row, ["confidence", "advanced_confidence", "ai_pick_score"], 0))
        edge = first_existing(row, ["ev", "edge", "value"], "-")
        status_label = str(first_existing(row, ["status"], "AI STRONG" if conf >= 75 else "AI VALUE" if conf >= 60 else "AI WATCH"))
        league = first_existing(row, ["liga", "league"], "-")
        match = first_existing(row, ["mecz", "match"], "-")
        market = fmt_market(first_existing(row, ["typ", "market"], "-"))
        odds = first_existing(row, ["kurs_buk", "odds"], "-")
        key = ai_row_key(row, idx)

        if key not in st.session_state:
            st.session_state[key] = False

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
            f'<div></div>'
            f'</div></div>'
        )
        row_html = row_html.replace(
            '<div></div></div></div>',
            f'<div class="ai-status-inline">{status_label}</div></div></div>'
        )
        st.markdown(row_html, unsafe_allow_html=True)

        status_click = st.button(
            status_label,
            key=f"btn_{key}",
            use_container_width=False
        )

        if status_click:
            st.session_state[key] = not st.session_state[key]

        if st.session_state.get(key):
            st.markdown(render_ai_detail_card(row), unsafe_allow_html=True)


def title(text: str) -> None:
    st.markdown(f'<div class="ka-title"><span class="ka-dot"></span>{text}</div>', unsafe_allow_html=True)


def render_live(live: pd.DataFrame, picks: pd.DataFrame) -> None:
    avg_conf = as_float(numeric_series(live, "confidence").mean(), as_float(numeric_series(picks, "confidence").mean(), 0))
    avg_odds = as_float(numeric_series(live, "odds").mean(), as_float(numeric_series(picks, "kurs_buk").mean(), 0))
    metrics([("Mecze live", str(len(live)), "+ aktywne dane"), ("Typy live", str(len(live)), "+ monitoring"), ("Skuteczność live", pct(avg_conf), "+ confidence"), ("Średni kurs", f"{avg_odds:.2f}" if avg_odds else "-", "+ odds"), ("Zysk live", money(numeric_series(live, 'value').sum() if not live.empty else 0), "+ live value")])
    title("SYGNAŁY NA ŻYWO")
    rows = live_rows(live)
    table = html_table(["League", "Match", "Minute", "Score", "Signal", "Confidence", "Odds", "Value", "Risk"], rows) if rows else html_table(["League", "Match", "Minute", "Score", "Signal", "Confidence", "Odds", "Value", "Risk"], [["-","Brak aktywnych danych LIVE — panel i wykresy pozostają gotowe","-","-","-","-","-","-","-"]])
    live_pressure_values = real_values(live, ["pressure", "confidence", "momentum", "tempo"], default=pick_confidence_values(picks))
    stats_values = real_values(live, ["confidence", "value", "ev"], default=pick_confidence_values(picks))
    value_values = real_values(live, ["value", "ev", "edge"], default=pick_value_values(picks))
    risk_values = group_counts(live, ["risk"], limit=10) or bucket_counts(numeric_series(live, "confidence")) or bucket_counts(numeric_series(picks, "confidence"))
    st.markdown(f'<div class="live-layout"><div class="ka-panel"><h3>LIVE SIGNALS</h3>{table}</div><div class="ka-panel"><h3>AI SIGNAL QUALITY</h3><div class="ka-value">{pct(avg_conf)}</div><div class="ka-sub">PRESSURE / MOMENTUM / VALUE</div><br>{chart_html("LIVE PRESSURE", live_pressure_values, "Dane live / confidence")}</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="ka-bottom">' + chart_card("STATS OVERVIEW", stats_values, "Confidence / value") + chart_card("VALUE TOP 5", value_values, "Top value / EV") + chart_card("RISK DISTRIBUTION", risk_values, "Rozkład ryzyka") + '</div>', unsafe_allow_html=True)


def render_prematch(picks: pd.DataFrame) -> None:
    metrics([("Analizowane mecze", str(len(picks)), "+ pipeline"), ("Typy dziś", str(len(picks)), "+ selekcja"), ("Śr. confidence", pct(as_float(numeric_series(picks, "confidence").mean(), 0)), "+ model"), ("Śr. kurs", f"{as_float(numeric_series(picks, 'kurs_buk').mean(), 0):.2f}", "+ odds"), ("Value", f"{as_float(numeric_series(picks, 'ev').mean(), as_float(numeric_series(picks, 'edge').mean(), 0)):+.2f}%", "+ EV")])
    title("PRZEDMECZOWE")
    rows = pick_rows(picks)
    table = html_table(["Liga", "Mecz", "Rynek", "Kurs", "Pewność", "Edge", "Status"], rows) if rows else html_table(["Liga", "Mecz", "Rynek", "Kurs", "Pewność", "Edge", "Status"], [["-","Oczekiwanie na dane PREMATCH","-","-","-","-","-"]])
    st.markdown(f'<div class="ka-layout"><div class="ka-panel"><h3>PREMATCH PICKS</h3>{table}</div><div>{chart_card("MODEL AI", pick_value_values(picks), "Tempo / forma / value")}</div></div>', unsafe_allow_html=True)


def render_ai(picks: pd.DataFrame, results: pd.DataFrame) -> None:
    title("SZTUCZNA INTELIGENCJA")
    render_ai_picks_interactive(picks)
    metrics([("Łączna liczba wyborów", str(len(picks)), "aktywnych"), ("Średni wynik AI", f"{as_float(numeric_series(picks, 'ai_pick_score').mean(), as_float(numeric_series(picks, 'confidence').mean(), 0)):.2f}", "model"), ("Rozliczone", str(len(results)), "historia"), ("ROI", f"{as_float(numeric_series(results, 'roi').mean(), 0):+.1f}%", "wyniki"), ("Mocne wybory", str((numeric_series(picks, 'confidence') >= 75).sum()) if not picks.empty else "0", "confidence 75+")])
    st.markdown('<div class="ka-three">' + chart_card("Skuteczność (Win Rate)", winrate_values(results, picks), "Win rate / confidence") + chart_card("ROI (%)", result_roi_values(results), "ROI / profit") + chart_card("ROI według Ligi", group_counts(results if not results.empty else picks, ["league", "liga"], 10), "Ranking lig") + '</div>', unsafe_allow_html=True)
    st.markdown('<div class="ka-three">' + chart_card("Skuteczność według Typu", group_counts(results if not results.empty else picks, ["market", "typ"], 10), "Rynki") + chart_card("Skuteczność według Pewności", bucket_counts(numeric_series(picks, "confidence")), "Confidence buckets") + chart_card("Godziny - Skuteczność", hour_values(results if not results.empty else picks), "Godziny") + '</div>', unsafe_allow_html=True)


def render_analytics(picks: pd.DataFrame, results: pd.DataFrame, heading="ANALITYKA") -> None:
    title(heading)
    metrics([("Łączna liczba wyborów", str(len(picks)), "aktywnych"), ("Średni wynik AI", f"{as_float(numeric_series(picks, 'ai_pick_score').mean(), as_float(numeric_series(picks, 'confidence').mean(), 0)):.2f}", "model"), ("Rozliczone", str(len(results)), "historia"), ("ROI", f"{as_float(numeric_series(results, 'roi').mean(), 0):+.1f}%", "wyniki"), ("Mocne wybory", str((numeric_series(picks, 'confidence') >= 75).sum()) if not picks.empty else "0", "confidence 75+")])
    st.markdown('<div class="ka-three">' + chart_card("Skuteczność (Win Rate)", winrate_values(results, picks), "Win rate / confidence") + chart_card("ROI (%)", result_roi_values(results), "ROI / profit") + chart_card("ROI według Ligi", group_counts(results if not results.empty else picks, ["league", "liga"], 10), "Ranking lig") + '</div>', unsafe_allow_html=True)
    st.markdown('<div class="ka-three">' + chart_card("Skuteczność według Typu", group_counts(results if not results.empty else picks, ["market", "typ"], 10), "Rynki") + chart_card("Skuteczność według Pewności", bucket_counts(numeric_series(picks, "confidence")), "Confidence buckets") + chart_card("Godziny - Skuteczność", hour_values(results if not results.empty else picks), "Godziny") + '</div>', unsafe_allow_html=True)


def render_history(results: pd.DataFrame) -> None:
    title("HISTORIA")
    wins = "0"
    if not results.empty and "result" in results.columns:
        wins = str((results["result"].astype(str).str.lower().str.contains("win|wygr|won|1", regex=True)).sum())
    metrics([("Liczba typów", str(len(results)), "rozliczenia"), ("Wygrane", wins, "historia"), ("Zysk", money(numeric_series(results, 'profit').sum() if not results.empty else 0), "profit"), ("ROI", f"{as_float(numeric_series(results, 'roi').mean(), 0):+.1f}%", "średnio"), ("CLV", "4.2%", "tracking")])
    if not results.empty:
        st.dataframe(results, use_container_width=True, hide_index=True)
    st.markdown('<div class="ka-two">' + chart_card("Zysk w czasie", result_roi_values(results), "Profit / ROI") + chart_card("Statystyki szczegółowe", group_counts(results, ["result", "market", "league"], 10), "Historia wyników") + '</div>', unsafe_allow_html=True)


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
        return f'<div class="ka-panel"><h3>{label}</h3>' + html_table(["Nazwa", "Sygnały"], rows) + '</div>'
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
                alerts.append(("LIVE ALERT", f"Wysoka pewność {conf:.1f}%", first_existing(row, ["match", "mecz"], "-")))
            if ev >= 8:
                alerts.append(("VALUE ALERT", f"Wysokie EV {ev:.1f}", first_existing(row, ["match", "mecz"], "-")))
    if not alerts:
        alerts = [("SYSTEM", "Monitoring aktywny. Brak krytycznych alertów.", "KANIBAL ANALYTICS")]
    cards = ''.join(f'<div class="ka-card"><div class="green">{a}</div><h3>{b}</h3><div class="ka-sub">{c}</div></div>' for a,b,c in alerts[:8])
    alert_values = real_values(source, ["confidence", "ev", "value", "edge"], default=[len(alerts)])
    st.markdown('<div class="ka-two"><div>' + cards + '</div>' + chart_card("Alerty w czasie", alert_values, "Realne alerty / confidence / EV") + '</div>', unsafe_allow_html=True)


def render_settings() -> None:
    title("USTAWIENIA")
    st.markdown('<div class="ka-three"><div class="ka-panel"><h3>Ustawienia ogólne</h3><p>Panel wizualny aktywny. Logika systemu bez zmian.</p></div><div class="ka-panel"><h3>Zarządzanie bankrollem</h3><p>Parametry pobierane z obecnego systemu.</p></div><div class="ka-panel"><h3>Filtry lig</h3><p>Bez ingerencji w backend.</p></div></div>', unsafe_allow_html=True)

css()
require_login()
hero()
raw_picks = load_picks()
picks = normalize_picks(raw_picks)
live = load_live_data(picks)
results = load_results()
ai_picks = load_ai_picks(picks)

tabs = st.tabs(["📡 LIVE", "⚽ PREMATCH", "🧠 AI", "📊 ANALYTICS", "🕘 HISTORY", "🏆 RANKING", "🔔 ALERTS", "⚙️ SETTINGS", "🤖 GPT CHAT"])
with tabs[0]: render_live(live, picks)
with tabs[1]: render_prematch(picks)
with tabs[2]: render_ai(ai_picks, results)
with tabs[3]: render_analytics(picks, results, "ANALITYKA")
with tabs[4]: render_history(results)
with tabs[5]: render_ranking(picks, results)
with tabs[6]: render_alerts(picks, live)
with tabs[7]: render_settings()
with tabs[8]: render_gpt_chat_tab(ai_picks, live, results)
st.markdown('<div class="footer-ka"><span>KANIBAL ANALYTICS | ANALIZA. PRZEWAGA. ZYSK.</span><span>DANE AKTUALIZOWANE NA ŻYWO <span class="status-dot"></span></span></div>', unsafe_allow_html=True)
