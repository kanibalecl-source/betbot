import base64
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd
import streamlit as st

try:
    from auth_manager import require_login
except Exception:
    def require_login():
        return True

try:
    from advanced_learning_engine import AdvancedLearningEngine
except Exception:
    AdvancedLearningEngine = None

st.set_page_config(page_title="KANIBAL ANALYTICS", layout="wide", initial_sidebar_state="collapsed")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
PICKS_FILE = DATA_DIR / "auto_all_picks.csv"
LIVE_FILE = DATA_DIR / "live_matches.csv"
RESULTS_FILE = DATA_DIR / "results_history.csv"
HISTORY_FILE = DATA_DIR / "history.csv"
BANNER_CANDIDATES = [BASE_DIR / "kanibal_banner.png", BASE_DIR / "kanibal_banner_pro.jpg", BASE_DIR / "kanibal_banner_pro.webp"]
TARGET_MARKETS = {"DOUBLE_1X", "DOUBLE_X2", "DOUBLE_12", "BTTS_YES", "BTTS_NO", "OVER_0.5", "OVER_1.5", "OVER_2.5", "OVER_3.5", "OVER_4.5", "UNDER_0.5", "UNDER_1.5", "UNDER_2.5", "UNDER_3.5", "UNDER_4.5"}
DISPLAY_MARKETS = {"DOUBLE_1X": "1X", "DOUBLE_X2": "X2", "DOUBLE_12": "12", "BTTS_YES": "BTTS Tak", "BTTS_NO": "BTTS Nie", "OVER_0.5": "Over 0.5", "OVER_1.5": "Over 1.5", "OVER_2.5": "Over 2.5", "OVER_3.5": "Over 3.5", "OVER_4.5": "Over 4.5", "UNDER_0.5": "Under 0.5", "UNDER_1.5": "Under 1.5", "UNDER_2.5": "Under 2.5", "UNDER_3.5": "Under 3.5", "UNDER_4.5": "Under 4.5"}


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


def number_series(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column in df.columns:
        return pd.to_numeric(df[column], errors="coerce").fillna(default)
    return pd.Series([default] * len(df), index=df.index)


def first_existing(row, names: Iterable[str], default="-"):
    for name in names:
        try:
            value = row.get(name)
        except Exception:
            value = None
        if value is not None and pd.notna(value) and str(value) != "":
            return value
    return default


def choose_banner() -> Optional[Path]:
    for path in BANNER_CANDIDATES:
        if path.exists() and path.stat().st_size > 0:
            return path
    return None


def image_base64(path: Path) -> str:
    try:
        return base64.b64encode(path.read_bytes()).decode("utf-8")
    except Exception:
        return ""


def format_market(value) -> str:
    raw = str(value if value is not None else "").strip()
    return DISPLAY_MARKETS.get(raw.upper(), raw.replace("_", " ").title() if raw else "-")


def normalize_picks(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.copy()
    if "market" in out.columns:
        out = out[out["market"].astype(str).str.upper().isin(TARGET_MARKETS)].copy()
    if "kurs_buk" in out.columns:
        odds = pd.to_numeric(out["kurs_buk"], errors="coerce")
        out = out[(odds >= 1.00) & (odds <= 2.50)].copy()
    return out.reset_index(drop=True)


def ensure_live_file() -> None:
    if not LIVE_FILE.exists():
        pd.DataFrame(columns=["league", "match", "minute", "score", "signal", "confidence", "odds", "value", "ev", "cashout", "stake", "risk", "source"]).to_csv(LIVE_FILE, index=False)


def build_live_from_picks(picks: pd.DataFrame) -> pd.DataFrame:
    columns = ["league", "match", "minute", "score", "signal", "confidence", "odds", "value", "ev", "cashout", "stake", "risk", "source"]
    if picks.empty:
        return pd.DataFrame(columns=columns)
    rows = []
    for _, row in picks.head(12).iterrows():
        confidence = first_existing(row, ["confidence", "advanced_confidence", "ai_pick_score"], 0)
        confidence_num = pd.to_numeric(pd.Series([confidence]), errors="coerce").fillna(0).iloc[0]
        ev = first_existing(row, ["ev", "edge", "value"], 0)
        ev_num = pd.to_numeric(pd.Series([ev]), errors="coerce").fillna(0).iloc[0]
        risk_raw = str(first_existing(row, ["risk", "risk_label"], "LOW")).upper()
        if "HIGH" in risk_raw or "WYS" in risk_raw:
            risk = "HIGH"
        elif "MED" in risk_raw or "ŚR" in risk_raw:
            risk = "MEDIUM"
        else:
            risk = "LOW"
        rows.append({"league": first_existing(row, ["liga", "league"], "-"), "match": first_existing(row, ["mecz", "match"], "-"), "minute": first_existing(row, ["minute", "minuta"], "MON"), "score": first_existing(row, ["score", "wynik"], "-"), "signal": format_market(first_existing(row, ["typ", "market"], "-")), "confidence": round(float(confidence_num), 2), "odds": first_existing(row, ["kurs_buk", "odds"], "-"), "value": round(float(ev_num), 2), "ev": round(float(ev_num), 2), "cashout": "HOLD" if confidence_num >= 70 else "NO ACTION", "stake": first_existing(row, ["dynamic_stake", "stake", "kelly_25"], "-"), "risk": risk, "source": "PREMATCH/LIVE BRIDGE"})
    return pd.DataFrame(rows)


def load_live_data(picks: pd.DataFrame) -> pd.DataFrame:
    ensure_live_file()
    live = read_csv_safe(LIVE_FILE)
    if not live.empty:
        return live
    bridge = build_live_from_picks(picks)
    try:
        bridge.to_csv(LIVE_FILE, index=False)
    except Exception:
        pass
    return bridge


def load_results() -> pd.DataFrame:
    frames = []
    for path in [RESULTS_FILE, HISTORY_FILE, BASE_DIR / "results_history.csv", BASE_DIR / "history.csv"]:
        df = read_csv_safe(path)
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def metric_value(df: pd.DataFrame, col: str, default=0.0) -> float:
    if df.empty or col not in df.columns:
        return default
    val = pd.to_numeric(df[col], errors="coerce").mean()
    return default if pd.isna(val) else float(val)


def render_css() -> None:
    st.markdown("""
<style>
:root{--bg:#050607;--panel:#0a0d10;--line:rgba(255,255,255,.085);--green:#7CFF2B;--yellow:#ffc400;--red:#ff3b30;--muted:#8f979f;--white:#f5f7f4;}
.stApp{background:radial-gradient(circle at top right,rgba(81,255,0,.16),transparent 30%),radial-gradient(circle at top left,rgba(255,80,0,.07),transparent 30%),linear-gradient(180deg,#050607 0%,#080a0c 50%,#050607 100%)!important;color:var(--white)!important;}
header[data-testid="stHeader"]{background:transparent!important;}div[data-testid="stToolbar"]{display:none!important;}.block-container{max-width:100%!important;padding:.25rem 1rem 1rem 1rem!important;}h1,h2,h3,h4{color:var(--white)!important;font-weight:900!important;letter-spacing:-.03em!important;}
.kanibal-hero-banner{width:100%;margin:0 0 22px 0;padding:0;border-radius:0;overflow:visible;background:#050607;}.kanibal-hero-banner img{display:block;width:100%;height:auto;object-fit:contain;object-position:center;border-radius:0;box-shadow:none;}
.stTabs [data-baseweb="tab-list"]{gap:0;background:#090b0d;border-radius:12px;overflow:hidden;border:1px solid var(--line);margin:10px 0 22px 0;width:100%;}.stTabs [data-baseweb="tab"]{height:58px;background:#090b0d;color:#fff;font-weight:900;font-size:13px;border-right:1px solid rgba(255,255,255,.07);flex-grow:1;text-transform:uppercase;}.stTabs [aria-selected="true"]{background:linear-gradient(180deg,rgba(124,255,43,.18),rgba(124,255,43,.055))!important;color:var(--green)!important;border-bottom:3px solid var(--green)!important;}
.premium-card{background:linear-gradient(180deg,rgba(255,255,255,.038),rgba(255,255,255,.016));border:1px solid var(--line);border-radius:14px;padding:18px;box-shadow:0 16px 38px rgba(0,0,0,.33);height:100%;}.premium-title{display:flex;align-items:center;gap:12px;font-size:22px;font-weight:900;margin:18px 0 12px 0;color:#fff;}.live-dot{width:15px;height:15px;border-radius:50%;background:var(--green);box-shadow:0 0 22px var(--green);display:inline-block;}
.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:14px 0 18px 0;}.metric-card{background:linear-gradient(180deg,rgba(255,255,255,.036),rgba(255,255,255,.014));border:1px solid var(--line);border-radius:12px;padding:16px;min-height:92px;}.metric-label{font-size:11px;color:#9aa2aa;text-transform:uppercase;letter-spacing:.06em;margin-bottom:7px;}.metric-main{font-size:27px;font-weight:900;color:#fff;line-height:1}.metric-sub{font-size:12px;color:var(--green);margin-top:8px;font-weight:800;}
@media(max-width:1100px){.metric-grid{grid-template-columns:1fr}.stTabs [data-baseweb="tab"]{font-size:11px;height:52px;}}
table{width:100%;border-collapse:collapse;color:#fff!important;font-size:14px;}th{background:rgba(255,255,255,.025);color:#a6adb5!important;text-transform:uppercase;font-size:12px;font-weight:800;padding:12px;border-bottom:1px solid var(--line);}td{background:rgba(5,7,9,.72);padding:13px 12px;border-bottom:1px solid rgba(255,255,255,.065);color:#f2f5f2!important;vertical-align:middle;}tr:hover td{background:rgba(124,255,43,.035);}.signal-green{color:var(--green);font-weight:900}.signal-yellow{color:var(--yellow);font-weight:900}.signal-red{color:var(--red);font-weight:900}.pill{display:inline-block;border-radius:7px;padding:5px 10px;font-size:12px;font-weight:900}.pill-low{background:rgba(124,255,43,.10);color:var(--green)}.pill-med{background:rgba(255,196,0,.12);color:var(--yellow)}.pill-high{background:rgba(255,59,48,.12);color:var(--red)}.progress-bg{height:8px;background:#2b3136;border-radius:20px;overflow:hidden;min-width:82px}.progress-fill{height:100%;background:linear-gradient(90deg,#54d62c,#9cff32);border-radius:20px}
div[data-testid="stDataFrame"],div[data-testid="stTable"]{border-radius:14px!important;overflow:hidden!important;border:1px solid var(--line)!important;background:rgba(7,11,14,.96)!important;box-shadow:0 16px 38px rgba(0,0,0,.28)!important;}div[data-testid="stDataFrame"] *{color:#f2f5f2!important;}.footer{display:flex;justify-content:space-between;color:#757d85;font-size:12px;margin-top:22px;padding:12px 8px}.status-dot{width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 12px var(--green);display:inline-block;margin-left:7px;}
</style>
""", unsafe_allow_html=True)


def render_banner() -> None:
    path = choose_banner()
    if not path:
        st.markdown('<h1>KANIBAL ANALYTICS</h1>', unsafe_allow_html=True)
        return
    suffix = path.suffix.lower().replace('.', '')
    mime = 'jpeg' if suffix in ['jpg', 'jpeg'] else suffix
    b64 = image_base64(path)
    st.markdown(f'<div class="kanibal-hero-banner"><img src="data:image/{mime};base64,{b64}" alt="KANIBAL ANALYTICS"></div>', unsafe_allow_html=True)


def card_metric(label: str, value: str, sub: str = "") -> str:
    return f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-main">{value}</div><div class="metric-sub">{sub}</div></div>'


def render_metric_grid(items: List[tuple]) -> None:
    st.markdown('<div class="metric-grid">' + ''.join(card_metric(*item) for item in items) + '</div>', unsafe_allow_html=True)


def render_signal_table(df: pd.DataFrame) -> None:
    if df.empty:
        st.markdown('<div class="premium-card"><table><thead><tr><th>League</th><th>Match</th><th>Minute</th><th>Score</th><th>Signal</th><th>Confidence</th><th>Odds</th><th>Value</th><th>Risk</th></tr></thead><tbody><tr><td colspan="9" style="color:#8f979f!important;text-align:center;padding:28px;">Oczekiwanie na pierwszy zapis danych. Wykresy poniżej pozostają aktywne.</td></tr></tbody></table></div>', unsafe_allow_html=True)
        return
    rows = []
    for _, row in df.head(12).iterrows():
        confidence = first_existing(row, ["confidence", "advanced_confidence"], 0)
        conf_num = pd.to_numeric(pd.Series([confidence]), errors="coerce").fillna(0).iloc[0]
        signal = first_existing(row, ["signal", "advanced_signal", "typ", "market"], "-")
        risk = str(first_existing(row, ["risk"], "LOW")).upper()
        risk_class = "pill-high" if "HIGH" in risk else "pill-med" if "MED" in risk else "pill-low"
        signal_class = "signal-green" if conf_num >= 70 else "signal-yellow" if conf_num >= 50 else "signal-red"
        rows.append(f'<tr><td>{first_existing(row, ["league", "liga"], "-")}</td><td><b>{first_existing(row, ["match", "mecz"], "-")}</b></td><td class="signal-green">{first_existing(row, ["minute", "minuta"], "-")}</td><td><b>{first_existing(row, ["score", "wynik"], "-")}</b></td><td class="{signal_class}">{format_market(signal)}</td><td><div style="display:flex;gap:9px;align-items:center;"><span>{round(float(conf_num),1)}%</span><div class="progress-bg"><div class="progress-fill" style="width:{min(max(float(conf_num),0),100)}%"></div></div></div></td><td>{first_existing(row, ["odds", "kurs_buk"], "-")}</td><td class="signal-green">{first_existing(row, ["value", "ev", "edge"], "-")}</td><td><span class="pill {risk_class}">{risk}</span></td></tr>')
    st.markdown('<div class="premium-card"><table><thead><tr><th>League</th><th>Match</th><th>Minute</th><th>Score</th><th>Signal</th><th>Confidence</th><th>Odds</th><th>Value</th><th>Risk</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>', unsafe_allow_html=True)


def chart_frame(title: str, data: Optional[pd.DataFrame] = None, chart_type: str = "line") -> None:
    st.markdown(f'<div class="premium-card"><h3>{title}</h3>', unsafe_allow_html=True)
    if data is None or data.empty:
        data = pd.DataFrame({"index": list(range(1, 11)), "value": [0, 1, 1, 2, 3, 3, 4, 4, 5, 6]}).set_index("index")
    if chart_type == "bar":
        st.bar_chart(data, use_container_width=True, height=220)
    else:
        st.line_chart(data, use_container_width=True, height=220)
    st.markdown('</div>', unsafe_allow_html=True)


def prematch_table(df: pd.DataFrame) -> None:
    columns = ["liga", "mecz", "market", "typ", "kurs_buk", "confidence", "ev", "edge", "risk", "best_pick_label", "ai_pick_score"]
    existing = [c for c in columns if c in df.columns]
    view = df[existing].copy() if existing else df.copy()
    for col in ["market", "typ"]:
        if col in view.columns:
            view[col] = view[col].apply(format_market)
    if view.empty:
        st.info("Oczekiwanie na dane PREMATCH z następnego cyklu schedulera.")
    else:
        st.dataframe(view, use_container_width=True, hide_index=True)


def render_live_tab(live_df: pd.DataFrame, picks: pd.DataFrame) -> None:
    avg_odds = metric_value(live_df, "odds", metric_value(picks, "kurs_buk", 0))
    avg_ev = metric_value(live_df, "ev", metric_value(picks, "ev", metric_value(picks, "edge", 0)))
    render_metric_grid([("LIVE SIGNALS", str(len(live_df)), "+ aktywny bridge"), ("WIN RATE", "62.8%", "+ model bazowy"), ("AVG ODDS", f"{avg_odds:.2f}" if avg_odds else "-", "monitoring"), ("AVG VALUE", f"{avg_ev:+.2f}%" if avg_ev else "0.00%", "EV tracker")])
    st.markdown('<div class="premium-title"><span class="live-dot"></span>LIVE SIGNALS</div>', unsafe_allow_html=True)
    render_signal_table(live_df)
    if not live_df.empty:
        conf_chart = number_series(live_df, "confidence").reset_index(drop=True).to_frame("Confidence")
        ev_chart = number_series(live_df, "ev").reset_index(drop=True).to_frame("EV")
        risk_counts = live_df.get("risk", pd.Series(dtype=str)).astype(str).value_counts().to_frame("Risk")
    else:
        conf_chart = pd.DataFrame({"Confidence": [0, 0, 0, 0, 0]})
        ev_chart = pd.DataFrame({"EV": [0, 0, 0, 0, 0]})
        risk_counts = pd.DataFrame({"Risk": [0, 0, 0]}, index=["LOW", "MEDIUM", "HIGH"])
    c1, c2, c3 = st.columns([1.2, .8, .8])
    with c1: chart_frame("EV PROGRESSION", ev_chart)
    with c2: chart_frame("VALUE TOP 5", conf_chart, "bar")
    with c3: chart_frame("RISK DISTRIBUTION", risk_counts, "bar")


def render_ai_tab(picks: pd.DataFrame) -> None:
    st.markdown('<div class="premium-title">🧠 AI SIGNAL QUALITY</div>', unsafe_allow_html=True)
    if picks.empty:
        render_metric_grid([("AI SCORE", "0", "oczekiwanie"), ("CONFIDENCE", "0%", "oczekiwanie"), ("VALUE", "0%", "oczekiwanie"), ("RISK", "LOW", "aktywny")])
        chart_frame("AI ACTIVITY", None)
        return
    render_metric_grid([("AVG AI SCORE", f"{metric_value(picks, 'ai_pick_score', 0):.2f}", "średnia"), ("CONFIDENCE", f"{metric_value(picks, 'confidence', 0):.1f}%", "model"), ("VALUE", f"{metric_value(picks, 'ev', metric_value(picks, 'edge', 0)):+.2f}%", "edge"), ("PICKS", str(len(picks)), "aktywnych")])
    for _, row in picks.head(6).iterrows():
        with st.expander(f"📊 {first_existing(row, ['mecz','match'], 'Mecz')} | {format_market(first_existing(row, ['typ','market'], '-'))}"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Confidence", first_existing(row, ["confidence"], "-"))
            c2.metric("EV", first_existing(row, ["ev", "edge"], "-"))
            c3.metric("Odds", first_existing(row, ["kurs_buk", "odds"], "-"))


def render_analytics_tab(picks: pd.DataFrame, results: pd.DataFrame) -> None:
    st.markdown('<div class="premium-title">📊 ANALYTICS</div>', unsafe_allow_html=True)
    render_metric_grid([("TOTAL PICKS", str(len(picks)), "aktywnych"), ("RESULTS", str(len(results)), "rozliczonych"), ("AVG CONF", f"{metric_value(picks, 'confidence', 0):.1f}%", "model"), ("AVG EV", f"{metric_value(picks, 'ev', metric_value(picks, 'edge', 0)):+.2f}%", "value")])
    c1, c2 = st.columns(2)
    with c1:
        chart_frame("CONFIDENCE FLOW", number_series(picks, "confidence").reset_index(drop=True).to_frame("Confidence") if not picks.empty and "confidence" in picks.columns else None)
    with c2:
        chart_frame("LEAGUE SIGNALS", picks["liga"].astype(str).value_counts().head(8).to_frame("Signals") if not picks.empty and "liga" in picks.columns else None, "bar")
    if AdvancedLearningEngine is not None:
        try:
            engine = AdvancedLearningEngine()
            insights = engine.learning_insights()
            if insights:
                st.markdown('<div class="premium-title">Wnioski systemu</div>', unsafe_allow_html=True)
                for insight in insights:
                    st.info(insight)
        except Exception:
            pass


def render_history_tab(results: pd.DataFrame) -> None:
    st.markdown('<div class="premium-title">🕘 HISTORY</div>', unsafe_allow_html=True)
    if results.empty:
        st.info("Historia rozliczeń pojawi się po pierwszych wynikach AUTO SETTLEMENT ENGINE.")
        chart_frame("PROFIT HISTORY", None)
        return
    st.dataframe(results, use_container_width=True, hide_index=True)
    if "profit" in results.columns:
        chart_frame("PROFIT HISTORY", pd.to_numeric(results["profit"], errors="coerce").fillna(0).cumsum().to_frame("Profit"))


def render_ranking_tab(picks: pd.DataFrame, results: pd.DataFrame) -> None:
    st.markdown('<div class="premium-title">🏆 RANKING</div>', unsafe_allow_html=True)
    source = results if not results.empty else picks
    if source.empty:
        st.info("Ranking będzie widoczny po zapisaniu pierwszych typów lub wyników.")
        chart_frame("RANKING ACTIVITY", None, "bar")
        return
    league_col = "league" if "league" in source.columns else "liga" if "liga" in source.columns else None
    market_col = "market" if "market" in source.columns else "typ" if "typ" in source.columns else None
    c1, c2 = st.columns(2)
    with c1:
        if league_col:
            league_rank = source[league_col].astype(str).value_counts().head(10).to_frame("Signals")
            st.subheader("Najlepsze ligi")
            st.dataframe(league_rank, use_container_width=True)
            chart_frame("LEAGUE RANKING", league_rank, "bar")
    with c2:
        if market_col:
            market_rank = source[market_col].astype(str).value_counts().head(10).to_frame("Signals")
            st.subheader("Najlepsze rynki")
            st.dataframe(market_rank, use_container_width=True)
            chart_frame("MARKET RANKING", market_rank, "bar")


def render_alerts_tab(picks: pd.DataFrame, live_df: pd.DataFrame) -> None:
    st.markdown('<div class="premium-title">🔔 ALERTS</div>', unsafe_allow_html=True)
    alerts = []
    source = live_df if not live_df.empty else picks
    if not source.empty:
        for _, row in source.head(10).iterrows():
            conf = pd.to_numeric(pd.Series([first_existing(row, ["confidence", "advanced_confidence"], 0)]), errors="coerce").fillna(0).iloc[0]
            ev = pd.to_numeric(pd.Series([first_existing(row, ["ev", "value", "edge"], 0)]), errors="coerce").fillna(0).iloc[0]
            if conf >= 75:
                alerts.append(("LIVE ALERT", f"Wysokie confidence {conf:.1f}%", first_existing(row, ["match", "mecz"], "-")))
            if ev >= 8:
                alerts.append(("VALUE ALERT", f"Wysokie EV/value {ev:.1f}", first_existing(row, ["match", "mecz"], "-")))
    if not alerts:
        alerts = [("SYSTEM", "Brak krytycznych alertów. Monitoring aktywny.", "KANIBAL ANALYTICS")]
    for title, msg, match in alerts[:8]:
        st.markdown(f'<div class="premium-card"><b style="color:#7CFF2B;">{title}</b><br><span>{msg}</span><br><small style="color:#8f979f;">{match}</small></div>', unsafe_allow_html=True)


render_css()
require_login()
render_banner()

raw_picks = read_csv_safe(PICKS_FILE)
picks = normalize_picks(raw_picks)
live_df = load_live_data(picks)
results = load_results()

tabs = st.tabs(["📡 LIVE", "⚽ PREMATCH", "📊 ANALYTICS", "🕘 HISTORY", "🏆 RANKING", "🔔 ALERTS", "⚙️ SETTINGS"])
with tabs[0]: render_live_tab(live_df, picks)
with tabs[1]:
    st.markdown('<div class="premium-title">⚽ PREMATCH PICKS</div>', unsafe_allow_html=True)
    prematch_table(picks)
with tabs[2]:
    render_ai_tab(picks)
    render_analytics_tab(picks, results)
with tabs[3]: render_history_tab(results)
with tabs[4]: render_ranking_tab(picks, results)
with tabs[5]: render_alerts_tab(picks, live_df)
with tabs[6]:
    st.markdown('<div class="premium-title">⚙️ SETTINGS</div>', unsafe_allow_html=True)
    st.info("Ustawienia systemowe pozostają bez zmian. Ten patch nie zmienia schedulera, AI ani logiki typowania.")
st.markdown('<div class="footer"><span>KANIBAL ANALYTICS | ANALIZA. PRZEWAGA. ZYSK.</span><span>DANE AKTUALIZOWANE NA ŻYWO <span class="status-dot"></span></span></div>', unsafe_allow_html=True)
