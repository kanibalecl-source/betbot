from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, List

import pandas as pd
import streamlit as st

from auth_manager import require_login
from advanced_learning_engine import AdvancedLearningEngine

st.set_page_config(
    page_title="KANIBAL ANALYTICS",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PICKS_FILE = DATA_DIR / "auto_all_picks.csv"
LIVE_FILE = DATA_DIR / "live_matches.csv"
HISTORY_FILE = DATA_DIR / "history.csv"
RESULTS_FILE = DATA_DIR / "results_history.csv"
BANNER_FILE = BASE_DIR / "kanibal_banner_pro.webp"

TARGET_MARKETS = {
    "DOUBLE_1X", "DOUBLE_X2", "DOUBLE_12", "BTTS_YES", "BTTS_NO",
    "OVER_0.5", "OVER_1.5", "OVER_2.5", "OVER_3.5", "OVER_4.5",
    "UNDER_0.5", "UNDER_1.5", "UNDER_2.5", "UNDER_3.5", "UNDER_4.5",
}


def safe_read_csv(path: Path) -> pd.DataFrame:
    try:
        if path.exists():
            return pd.read_csv(path)
    except Exception:
        try:
            return pd.read_csv(path, encoding="utf-8")
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def num(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def fmt(value: Any, suffix: str = "", decimals: int = 1, default: str = "—") -> str:
    try:
        if value is None or pd.isna(value):
            return default
        number = float(value)
        if decimals == 0:
            return f"{number:,.0f}{suffix}".replace(",", " ")
        return f"{number:,.{decimals}f}{suffix}".replace(",", " ")
    except Exception:
        text = str(value).strip()
        return f"{text}{suffix}" if text else default


def first_value(df: pd.DataFrame, columns: Iterable[str], default: Any = "—") -> Any:
    for column in columns:
        if column in df.columns and not df[column].dropna().empty:
            return df[column].dropna().iloc[0]
    return default


def existing_columns(df: pd.DataFrame, columns: List[str]) -> List[str]:
    return [column for column in columns if column in df.columns]


def css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');

        :root {
            --bg: #030609;
            --panel: rgba(8, 16, 24, 0.78);
            --panel-strong: rgba(9, 21, 31, 0.94);
            --line: rgba(113, 255, 73, 0.16);
            --green: #53ff4f;
            --green-soft: rgba(83, 255, 79, 0.18);
            --yellow: #ffc928;
            --orange: #ff7a1a;
            --red: #ff3f47;
            --muted: #8d98a7;
        }

        html, body, [class*="css"] {font-family: 'Inter', sans-serif !important;}
        .stApp {
            background:
                radial-gradient(circle at 8% 4%, rgba(255, 111, 0, 0.12), transparent 28%),
                radial-gradient(circle at 86% 8%, rgba(83, 255, 79, 0.16), transparent 31%),
                radial-gradient(circle at 50% 115%, rgba(28, 128, 255, 0.08), transparent 34%),
                linear-gradient(180deg, #030609 0%, #06090d 48%, #020406 100%);
            color: #fff;
        }
        header[data-testid="stHeader"] {background: transparent !important;}
        .block-container {max-width: 100% !important; padding: 1.0rem 1.6rem 2.0rem !important;}
        #MainMenu, footer {visibility: hidden;}
        h1, h2, h3, h4 {color: #fff !important; letter-spacing: -0.03em;}
        .stMarkdown, .stText, p, span, label {color: #e9edf2;}

        .ka-shell {width: 100%;}
        .ka-banner {
            min-height: 138px;
            border-radius: 22px;
            border: 1px solid rgba(255,255,255,0.10);
            box-shadow: 0 22px 90px rgba(0,0,0,0.55), inset 0 0 90px rgba(83,255,79,0.06);
            overflow: hidden;
            margin-bottom: 18px;
            background: linear-gradient(90deg, #05080c 0%, #0c1115 38%, #07120b 100%);
            position: relative;
        }
        .ka-banner:after {
            content: ""; position:absolute; inset:0;
            background: linear-gradient(90deg, transparent, rgba(83,255,79,0.08), transparent);
            pointer-events:none;
        }
        .ka-banner-img {width: 100%; height: 142px; object-fit: cover; display:block; opacity: .98;}

        .ka-topbar {
            display:flex; align-items:center; justify-content:space-between; gap: 16px;
            margin: 8px 0 18px;
        }
        .ka-page-title {font-size: 34px; font-weight: 900; color:#fff; display:flex; align-items:center; gap:12px;}
        .ka-page-sub {font-size: 12px; color: var(--muted); margin-top: 3px; text-transform: uppercase; letter-spacing: .14em;}
        .ka-status {
            display:flex; align-items:center; gap:10px; padding: 11px 14px; border-radius: 999px;
            border:1px solid rgba(83,255,79,.18); background: rgba(6,18,12,.72); color: var(--green); font-weight:800;
            box-shadow: 0 0 30px rgba(83,255,79,.10);
        }
        .ka-dot {width:9px; height:9px; border-radius:50%; background:var(--green); box-shadow:0 0 18px var(--green);}

        .ka-card {
            background: linear-gradient(180deg, rgba(14,25,35,.92), rgba(6,12,19,.90));
            border: 1px solid rgba(255,255,255,.08);
            border-radius: 18px;
            padding: 18px;
            box-shadow: 0 18px 50px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.04);
            min-height: 100%;
        }
        .ka-card:hover {border-color: rgba(83,255,79,.20); box-shadow:0 22px 70px rgba(0,0,0,.45), 0 0 22px rgba(83,255,79,.06);}
        .ka-kpi-label {font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .10em; font-weight:700;}
        .ka-kpi-value {font-size: 30px; color:#fff; font-weight:900; margin-top: 8px; line-height:1;}
        .ka-kpi-trend {font-size: 12px; color: var(--green); font-weight:800; margin-top: 8px;}
        .ka-section-title {font-size: 18px; color:#fff; font-weight:900; margin-bottom:14px; display:flex; gap:10px; align-items:center;}
        .ka-muted {color: var(--muted);}
        .ka-pill {
            display:inline-flex; align-items:center; gap:7px; padding:6px 10px; border-radius:999px;
            border:1px solid rgba(83,255,79,.18); background:rgba(83,255,79,.10); color:var(--green); font-size:12px; font-weight:800;
        }
        .ka-pill-yellow {border-color: rgba(255,201,40,.22); background:rgba(255,201,40,.10); color:var(--yellow);}
        .ka-pill-red {border-color: rgba(255,63,71,.22); background:rgba(255,63,71,.10); color:var(--red);}

        .ka-match-card {
            display:grid; grid-template-columns: minmax(180px,1.5fr) .65fr .65fr .85fr .8fr .8fr .8fr; gap: 12px;
            align-items:center; padding: 14px 12px; border-radius: 14px; margin-bottom: 9px;
            background: rgba(255,255,255,.025); border:1px solid rgba(255,255,255,.06);
        }
        .ka-match-card:hover {background:rgba(83,255,79,.045); border-color:rgba(83,255,79,.18);}
        .ka-match-name {font-size:14px; font-weight:800; color:#fff;}
        .ka-match-meta {font-size:12px; color:var(--muted); margin-top:4px;}
        .ka-mini-label {font-size:10px; color:var(--muted); text-transform:uppercase; letter-spacing:.08em;}
        .ka-mini-value {font-size:15px; color:#fff; font-weight:900; margin-top:3px;}
        .ka-green {color:var(--green) !important;} .ka-yellow {color:var(--yellow) !important;} .ka-red {color:var(--red) !important;}

        .ka-progress {height: 9px; background:rgba(255,255,255,.08); border-radius:999px; overflow:hidden; margin-top:7px;}
        .ka-progress > div {height:100%; border-radius:999px; background:linear-gradient(90deg,#2bd93b,#96ff48); box-shadow:0 0 18px rgba(83,255,79,.45);}
        .ka-ring {
            width: 136px; height: 136px; border-radius: 50%; display:flex; align-items:center; justify-content:center; margin:auto;
            background: conic-gradient(var(--green) calc(var(--p)*1%), rgba(255,255,255,.08) 0);
            box-shadow: 0 0 42px rgba(83,255,79,.18);
            position:relative;
        }
        .ka-ring:before {content:""; position:absolute; inset:14px; border-radius:50%; background:#071019; border:1px solid rgba(255,255,255,.08);}
        .ka-ring span {position:relative; z-index:1; font-size:31px; font-weight:900; color:#fff;}

        .stTabs [data-baseweb="tab-list"] {
            gap: 0; background: rgba(7,10,14,.86); border-radius: 18px; overflow:hidden;
            border:1px solid rgba(255,255,255,.09); box-shadow:0 18px 55px rgba(0,0,0,.34); margin-bottom: 26px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 70px; flex-grow:1; font-weight:900; color:#fff; background:transparent;
            border-right:1px solid rgba(255,255,255,.055);
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(180deg, rgba(83,255,79,.16), rgba(83,255,79,.045)) !important;
            color: var(--green) !important; border-bottom: 3px solid var(--green) !important;
            box-shadow: inset 0 -18px 38px rgba(83,255,79,.08);
        }
        .stDataFrame, div[data-testid="stTable"] {border-radius:18px !important; overflow:hidden;}
        div[data-testid="stMetric"] {
            background: linear-gradient(180deg, rgba(14,25,35,.92), rgba(6,12,19,.90));
            border:1px solid rgba(255,255,255,.08); border-radius:18px; padding:16px; box-shadow:0 18px 50px rgba(0,0,0,.30);
        }
        div[data-testid="stMetricValue"] {font-weight: 900; color:#fff;}
        div[data-testid="stMetricDelta"] {color: var(--green);}
        .stAlert {border-radius:16px; border:1px solid rgba(0,121,255,.20); background: rgba(0,72,155,.14);}
        button[kind="secondary"], .stButton button {
            background: linear-gradient(180deg, rgba(83,255,79,.18), rgba(83,255,79,.08)) !important;
            color:#fff !important; border:1px solid rgba(83,255,79,.30) !important; border-radius:12px !important; font-weight:900 !important;
        }
        @media (max-width: 1100px) {.ka-match-card{grid-template-columns:1fr 1fr;} .ka-banner-img{height:110px;} .ka-page-title{font-size:28px;}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def banner() -> None:
    if BANNER_FILE.exists():
        import base64
        data = base64.b64encode(BANNER_FILE.read_bytes()).decode("utf-8")
        st.markdown(f"""
            <div class="ka-banner"><img class="ka-banner-img" src="data:image/webp;base64,{data}" /></div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
            <div class="ka-banner" style="display:flex;align-items:center;padding:24px 34px;">
                <div>
                    <div style="font-size:54px;font-weight:900;letter-spacing:.05em;">KANIBAL ANALYTICS</div>
                    <div style="font-size:15px;color:#53ff4f;letter-spacing:.28em;font-weight:800;">ANALIZA • PRZEWAGA • ZYSK</div>
                </div>
            </div>
        """, unsafe_allow_html=True)


def page_header(title: str, subtitle: str, icon: str = "⚡") -> None:
    st.markdown(f"""
        <div class="ka-topbar">
            <div>
                <div class="ka-page-title"><span>{icon}</span><span>{title}</span></div>
                <div class="ka-page-sub">{subtitle}</div>
            </div>
            <div class="ka-status"><span class="ka-dot"></span> SYSTEM ONLINE</div>
        </div>
    """, unsafe_allow_html=True)


def kpi(label: str, value: str, trend: str = "", accent: str = "green") -> None:
    color_class = "ka-green" if accent == "green" else "ka-yellow" if accent == "yellow" else "ka-red"
    st.markdown(f"""
        <div class="ka-card">
            <div class="ka-kpi-label">{label}</div>
            <div class="ka-kpi-value">{value}</div>
            <div class="ka-kpi-trend {color_class}">{trend}</div>
        </div>
    """, unsafe_allow_html=True)


def panel(title: str, body: str, icon: str = "") -> None:
    st.markdown(f"""
        <div class="ka-card">
            <div class="ka-section-title">{icon} {title}</div>
            {body}
        </div>
    """, unsafe_allow_html=True)


def normalize_picks(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    if "market" in df.columns:
        df = df[df["market"].astype(str).isin(TARGET_MARKETS)].copy()
    if "kurs_buk" in df.columns:
        df["_kurs_buk_num"] = pd.to_numeric(df["kurs_buk"], errors="coerce")
        df = df[(df["_kurs_buk_num"].isna()) | ((df["_kurs_buk_num"] >= 1.00) & (df["_kurs_buk_num"] <= 2.50))].copy()
    return df


def match_cards(df: pd.DataFrame, live: bool = False, limit: int = 8) -> None:
    if df.empty:
        st.warning("Brak danych do wyświetlenia.")
        return
    rows = df.head(limit).to_dict("records")
    html = []
    for row in rows:
        match = row.get("mecz") or row.get("match") or f"{row.get('home','—')} vs {row.get('away','—')}"
        league = row.get("liga") or row.get("league") or "—"
        market = row.get("typ") or row.get("market") or row.get("advanced_market") or "—"
        odds = row.get("kurs_buk") or row.get("odds") or "—"
        confidence = row.get("confidence") or row.get("advanced_confidence") or row.get("pewnosc") or "—"
        edge = row.get("edge") or row.get("ev") or row.get("live_edge") or "—"
        pressure = row.get("pressure_index") or row.get("pressure") or row.get("tempo_score") or "—"
        score = row.get("score") or row.get("wynik") or "—"
        minute = row.get("minute") or row.get("minuta") or "—"
        action = "LIVE" if live else "VALUE"
        html.append(f"""
            <div class="ka-match-card">
                <div><div class="ka-match-name">{match}</div><div class="ka-match-meta">{league}</div></div>
                <div><div class="ka-mini-label">{'Min.' if live else 'Rynek'}</div><div class="ka-mini-value">{minute if live else market}</div></div>
                <div><div class="ka-mini-label">Wynik</div><div class="ka-mini-value ka-yellow">{score}</div></div>
                <div><div class="ka-mini-label">Kurs</div><div class="ka-mini-value">{odds}</div></div>
                <div><div class="ka-mini-label">Pewność</div><div class="ka-mini-value ka-green">{confidence}</div></div>
                <div><div class="ka-mini-label">Pressure/Edge</div><div class="ka-mini-value ka-yellow">{pressure if live else edge}</div></div>
                <div><span class="ka-pill">{action}</span></div>
            </div>
        """)
    st.markdown("".join(html), unsafe_allow_html=True)


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, AdvancedLearningEngine]:
    DATA_DIR.mkdir(exist_ok=True)
    picks = normalize_picks(safe_read_csv(PICKS_FILE))
    engine = AdvancedLearningEngine()
    live_df = engine.live_tempo_snapshot()
    return picks, live_df, engine


require_login()
css()
banner()

picks_df, live_df, learning_engine = load_data()
summary = learning_engine.performance_summary()

# Global KPI strip
k1, k2, k3, k4, k5, k6 = st.columns(6)
with k1:
    kpi("Typy dzisiaj", fmt(len(picks_df), decimals=0), "pipeline aktywny")
with k2:
    kpi("Mecze LIVE", fmt(len(live_df), decimals=0), "live data")
with k3:
    avg_conf = pd.to_numeric(picks_df.get("confidence", pd.Series(dtype=float)), errors="coerce").mean() if not picks_df.empty else 0
    kpi("Śr. pewność", fmt(avg_conf, "%", 1), "model confidence")
with k4:
    kpi("Learning bets", fmt(summary.get("bets", 0), decimals=0), "historia wyników")
with k5:
    kpi("ROI", fmt(summary.get("roi_pct", 0), "%", 1), "learning engine", "green" if summary.get("roi_pct", 0) >= 0 else "red")
with k6:
    kpi("Profit", fmt(summary.get("profit", 0), " PLN", 1), "rozliczenia")

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

tabs = st.tabs(["🚨 NA ŻYWO", "⚽ PRZEDMECZOWE", "🧠 AI", "📊 ANALITYKA", "🕘 HISTORIA", "🏆 RANKING", "🔔 ALERTY"])
live_tab, prematch_tab, ai_tab, analytics_tab, history_tab, ranking_tab, alerts_tab = tabs

with live_tab:
    page_header("SYGNAŁY NA ŻYWO", "live trading terminal • tempo • pressure • momentum", "🟢")
    left, right = st.columns([1.55, 1.0], gap="large")
    with left:
        st.markdown('<div class="ka-card"><div class="ka-section-title">🚨 Live matches</div>', unsafe_allow_html=True)
        match_cards(live_df, live=True, limit=10)
        st.markdown('</div>', unsafe_allow_html=True)
    with right:
        confidence = num(first_value(live_df, ["advanced_confidence", "confidence"], 78), 78)
        ring = max(0, min(100, confidence))
        bars = []
        for label, columns in [
            ("Pressure", ["pressure_index", "pressure"]),
            ("Tempo", ["tempo_score", "tempo"]),
            ("Momentum", ["momentum_score_adv", "momentum"]),
            ("xG Pace", ["xg_pace"]),
        ]:
            value = max(0, min(100, num(first_value(live_df, columns, 0), 0)))
            bars.append(f"<div style='margin-bottom:14px'><div class='ka-mini-label'>{label} <span style='float:right;color:#fff'>{fmt(value, '/100', 0)}</span></div><div class='ka-progress'><div style='width:{value}%'></div></div></div>")
        panel("Live analytics", f"<div class='ka-ring' style='--p:{ring}'><span>{fmt(ring, '%', 0)}</span></div><div style='height:18px'></div>{''.join(bars)}", "📈")
    c1, c2, c3 = st.columns(3, gap="large")
    with c1:
        if not live_df.empty and any(c in live_df.columns for c in ["tempo_score", "pressure_index", "momentum_score_adv"]):
            cols = existing_columns(live_df, ["tempo_score", "pressure_index", "momentum_score_adv", "xg_pace"])
            st.markdown('<div class="ka-card"><div class="ka-section-title">📉 Trendy live</div>', unsafe_allow_html=True)
            st.line_chart(live_df[cols].apply(pd.to_numeric, errors="coerce"))
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            panel("Trendy live", "<span class='ka-muted'>Dane trendów pojawią się po zapisaniu pełnego feedu LIVE.</span>", "📉")
    with c2:
        top = picks_df.head(3)
        body = "".join([f"<div style='border-bottom:1px solid rgba(255,255,255,.07);padding:10px 0'><b>{r.get('typ', r.get('market','—'))}</b><br><span class='ka-muted'>{r.get('mecz', r.get('match','—'))}</span><span style='float:right' class='ka-green'>{r.get('confidence','—')}</span></div>" for r in top.to_dict('records')]) or "<span class='ka-muted'>Brak okazji.</span>"
        panel("Najlepsze okazje", body, "💎")
    with c3:
        if not picks_df.empty and ("liga" in picks_df.columns or "league" in picks_df.columns):
            col = "liga" if "liga" in picks_df.columns else "league"
            ranking = picks_df[col].value_counts().head(6).reset_index()
            ranking.columns = ["Liga", "Sygnały"]
            st.markdown('<div class="ka-card"><div class="ka-section-title">🏆 Top ligi live</div>', unsafe_allow_html=True)
            st.dataframe(ranking, use_container_width=True, hide_index=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            panel("Top ligi live", "<span class='ka-muted'>Ranking uzupełni się po kolejnych cyklach.</span>", "🏆")

with prematch_tab:
    page_header("PRZEDMECZOWE", "value picks • kursy • edge • confidence", "⚽")
    if picks_df.empty:
        st.warning("Brak danych PREMATCH.")
    else:
        match_cards(picks_df, live=False, limit=12)
        cols = existing_columns(picks_df, ["liga", "mecz", "market", "typ", "kurs_buk", "confidence", "ev", "edge", "risk", "best_pick_label", "ai_pick_score"])
        with st.expander("Pełna tabela danych PREMATCH", expanded=False):
            st.dataframe(picks_df[cols] if cols else picks_df, use_container_width=True, hide_index=True)

with ai_tab:
    page_header("SZTUCZNA INTELIGENCJA", "model details • value engine • xG • momentum • meta AI", "🧠")
    if picks_df.empty:
        st.warning("Brak danych AI.")
    else:
        for _, row in picks_df.head(20).iterrows():
            match_name = row.get("mecz", row.get("match", "BRAK MECZU"))
            market_name = row.get("typ", row.get("market", ""))
            with st.expander(f"📊 {match_name} | {market_name}", expanded=False):
                a, b, c = st.columns(3)
                with a:
                    panel("Model AI", f"<b>Confidence:</b> {row.get('confidence','—')}<br><b>Calibrated:</b> {row.get('confidence_calibrated_v2','—')}<br><b>Model prob:</b> {row.get('prawd_model','—')}<br><b>Final prob:</b> {row.get('prawd_final','—')}", "🧠")
                with b:
                    panel("Value engine", f"<b>EV:</b> {row.get('ev','—')}<br><b>Edge:</b> {row.get('edge','—')}<br><b>Kelly:</b> {row.get('kelly_25','—')}<br><b>Risk:</b> {row.get('risk','—')}", "💹")
                with c:
                    panel("Market engine", f"<b>Book odds:</b> {row.get('kurs_buk','—')}<br><b>Model odds:</b> {row.get('kurs_model','—')}<br><b>Bot odds:</b> {row.get('kurs_bota','—')}<br><b>Sharp:</b> {row.get('sharp_label','—')}", "🎯")
                d, e, f = st.columns(3)
                with d:
                    panel("xG engine", f"<b>Home xG:</b> {row.get('home_xg','—')}<br><b>Away xG:</b> {row.get('away_xg','—')}<br><b>Total xG:</b> {row.get('advanced_total_xg','—')}<br><b>Over 2.5:</b> {row.get('advanced_over25_prob','—')}", "🥅")
                with e:
                    panel("Momentum", f"<b>Score:</b> {row.get('momentum_score','—')}<br><b>Label:</b> {row.get('momentum_label','—')}<br><b>Sharp score:</b> {row.get('sharp_score','—')}<br><b>Signals:</b> {row.get('sharp_signals','—')}", "⚡")
                with f:
                    panel("Meta AI", f"<b>Meta prob:</b> {row.get('meta_probability','—')}<br><b>Model weight:</b> {row.get('meta_weight_model','—')}<br><b>Market weight:</b> {row.get('meta_weight_market','—')}<br><b>Dynamic stake:</b> {row.get('dynamic_stake','—')}", "🤖")

with analytics_tab:
    page_header("ANALITYKA", "ROI • skuteczność • uczenie • wykresy", "📊")
    a1, a2, a3, a4 = st.columns(4)
    with a1: kpi("Łączna liczba wyborów", fmt(len(picks_df), decimals=0), "current picks")
    with a2: kpi("Średni wynik AI", fmt(pd.to_numeric(picks_df.get('ai_pick_score', pd.Series(dtype=float)), errors='coerce').mean() if not picks_df.empty else 0, decimals=2), "score")
    with a3: kpi("Winrate", fmt(summary.get('winrate_pct', 0), "%", 1), "settled")
    with a4: kpi("ROI", fmt(summary.get('roi_pct', 0), "%", 1), "learning")

    left, right = st.columns([1.1, 1], gap="large")
    with left:
        curve = learning_engine.profit_curve()
        st.markdown('<div class="ka-card"><div class="ka-section-title">📈 Profit curve</div>', unsafe_allow_html=True)
        if not curve.empty:
            st.line_chart(curve.set_index(curve.columns[0]))
        else:
            st.info("Wykres profit curve pojawi się po rozliczeniu pierwszych typów.")
        st.markdown('</div>', unsafe_allow_html=True)
    with right:
        insights = learning_engine.learning_insights()
        body = "".join([f"<div style='padding:12px;border-radius:12px;background:rgba(0,121,255,.10);border:1px solid rgba(0,121,255,.14);margin-bottom:10px'>{i}</div>" for i in insights])
        panel("Wnioski systemu", body, "🧠")

    c1, c2 = st.columns(2, gap="large")
    with c1:
        conf = learning_engine.confidence_accuracy()
        st.markdown('<div class="ka-card"><div class="ka-section-title">🎚️ Confidence accuracy</div>', unsafe_allow_html=True)
        if not conf.empty:
            st.dataframe(conf, use_container_width=True, hide_index=True)
        else:
            st.info("Brak rozliczonych danych confidence.")
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        market_perf = learning_engine.group_performance("market")
        st.markdown('<div class="ka-card"><div class="ka-section-title">💹 Market performance</div>', unsafe_allow_html=True)
        if not market_perf.empty:
            st.dataframe(market_perf, use_container_width=True, hide_index=True)
        else:
            st.info("Brak rozliczonych danych marketów.")
        st.markdown('</div>', unsafe_allow_html=True)

with history_tab:
    page_header("HISTORIA", "wyniki • rozliczenia • profit/loss", "🕘")
    hist = learning_engine.load_results()
    if hist.empty:
        st.info("Historia wyników pojawi się po rozliczeniu pierwszych meczów.")
    else:
        st.dataframe(hist, use_container_width=True, hide_index=True)

with ranking_tab:
    page_header("RANKING", "najlepsze ligi • markety • strategie", "🏆")
    r1, r2 = st.columns(2, gap="large")
    with r1:
        league_col = "league" if "league" in learning_engine.load_results().columns else "liga"
        league_perf = learning_engine.group_performance(league_col)
        st.markdown('<div class="ka-card"><div class="ka-section-title">🏟️ Ranking lig</div>', unsafe_allow_html=True)
        if not league_perf.empty:
            st.dataframe(league_perf, use_container_width=True, hide_index=True)
        else:
            st.info("Ranking lig uzupełni się po wynikach.")
        st.markdown('</div>', unsafe_allow_html=True)
    with r2:
        market_perf = learning_engine.group_performance("market")
        st.markdown('<div class="ka-card"><div class="ka-section-title">🎯 Ranking marketów</div>', unsafe_allow_html=True)
        if not market_perf.empty:
            st.dataframe(market_perf, use_container_width=True, hide_index=True)
        else:
            st.info("Ranking marketów uzupełni się po wynikach.")
        st.markdown('</div>', unsafe_allow_html=True)

with alerts_tab:
    page_header("ALERTY", "pressure spikes • value alerts • system notifications", "🔔")
    body = """
        <div style='display:grid;gap:12px'>
            <div><span class='ka-pill'>LIVE ALERT</span> <b>Wysokie pressure</b><br><span class='ka-muted'>Alerty pojawią się po wykryciu spike w danych LIVE.</span></div>
            <div><span class='ka-pill ka-pill-yellow'>VALUE ALERT</span> <b>Wartość rynkowa</b><br><span class='ka-muted'>System obserwuje kursy, edge i confidence.</span></div>
            <div><span class='ka-pill'>SYSTEM</span> <b>Scheduler online</b><br><span class='ka-muted'>Backend działa niezależnie od otwartego dashboardu.</span></div>
        </div>
    """
    panel("Centrum alertów", body, "🔔")

st.markdown("<div style='height:22px'></div><div style='text-align:center;color:#6c7582;font-size:12px'>KANIBAL ANALYTICS • Premium UI Layer • backend logic unchanged</div>", unsafe_allow_html=True)
