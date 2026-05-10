import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime

st.set_page_config(
    page_title="KANIBAL ANALYTICS",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

DATA_DIR = Path("data")
CSV_FILE = DATA_DIR / "auto_all_picks.csv"

st.markdown("""
<style>

.stApp {
    background:
        radial-gradient(circle at top right, rgba(85,255,25,0.12), transparent 28%),
        linear-gradient(180deg, #050607 0%, #080b0f 100%);
    color:white;
}

header[data-testid="stHeader"] {
    background: transparent;
}

.block-container {
    max-width: 100% !important;
    padding-top: 1rem !important;
    padding-left: 1.4rem !important;
    padding-right: 1.4rem !important;
}

.kanibal-hero {
    background:
        linear-gradient(90deg, rgba(8,10,14,0.98), rgba(13,18,25,0.94));
    border:1px solid rgba(255,255,255,0.08);
    border-radius:24px;
    padding:34px;
    margin-bottom:18px;
    box-shadow:0 24px 70px rgba(0,0,0,0.45);
}

.kanibal-title {
    font-size:56px;
    font-weight:900;
    color:white;
}

.kanibal-sub {
    color:#9ca3af;
    font-size:16px;
    letter-spacing:4px;
    margin-top:10px;
}

.metric-grid {
    display:grid;
    grid-template-columns:repeat(4,1fr);
    gap:14px;
    margin-bottom:20px;
}

.metric-card {
    background:linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02));
    border:1px solid rgba(255,255,255,0.08);
    border-radius:18px;
    padding:18px;
}

.metric-label {
    color:#9ca3af;
    font-size:12px;
    font-weight:800;
}

.metric-value {
    color:#72ff2f;
    font-size:34px;
    font-weight:900;
    margin-top:8px;
}

.panel {
    background:linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01));
    border:1px solid rgba(255,255,255,0.08);
    border-radius:18px;
    padding:20px;
    margin-bottom:18px;
}

.panel-title {
    color:white;
    font-size:24px;
    font-weight:900;
    margin-bottom:4px;
}

.panel-subtitle {
    color:#9ca3af;
    font-size:12px;
    font-weight:800;
    margin-bottom:18px;
}

/* PREMIUM TABLE STYLE */

div[data-testid="stDataFrame"] {
    background: rgba(8,12,18,0.96) !important;
    border: 1px solid rgba(114,255,47,0.16) !important;
    border-radius: 18px !important;
    overflow: hidden !important;
    box-shadow: 0 0 28px rgba(114,255,47,0.08) !important;
}

div[data-testid="stDataFrame"] table {
    background: #070b11 !important;
    color: #ffffff !important;
}

div[data-testid="stDataFrame"] thead tr th {
    background:
        linear-gradient(180deg, #101722 0%, #0c121b 100%) !important;
    color: #72ff2f !important;
    font-weight: 900 !important;
    border-bottom: 1px solid rgba(114,255,47,0.22) !important;
    font-size: 12px !important;
    letter-spacing: 0.4px !important;
}

div[data-testid="stDataFrame"] tbody tr {
    background: #070b11 !important;
}

div[data-testid="stDataFrame"] tbody tr:nth-child(even) {
    background: #0b1017 !important;
}

div[data-testid="stDataFrame"] tbody tr:hover {
    background: rgba(114,255,47,0.08) !important;
}

div[data-testid="stDataFrame"] tbody td {
    color: #e5e7eb !important;
    border-color: rgba(255,255,255,0.05) !important;
    font-size: 12px !important;
}

.stTabs [data-baseweb="tab-list"] {
    gap:0;
    background:#070a0e;
    border:1px solid rgba(255,255,255,0.08);
    border-radius:14px;
    overflow:hidden;
    margin-top:14px;
    margin-bottom:22px;
}

.stTabs [data-baseweb="tab"] {
    color:white !important;
    height:56px;
    padding:0 24px;
    font-size:13px;
    font-weight:900;
}

.stTabs [aria-selected="true"] {
    color:#72ff2f !important;
    background:rgba(114,255,47,0.08) !important;
    border-bottom:3px solid #72ff2f !important;
}

</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=30)
def load_csv():
    if not CSV_FILE.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(CSV_FILE)
        df = df.fillna("")

        for col in df.columns:
            try:
                df[col] = df[col].astype(str)
            except:
                pass

        return df

    except Exception as e:
        st.error(f"CSV ERROR: {e}")
        return pd.DataFrame()

def fmt_percent(v):
    try:
        v=float(str(v).replace(",", "."))
        if abs(v)<=1:
            v*=100
        return f"{v:.1f}%"
    except:
        return "-"

def fmt_float(v):
    try:
        return f"{float(str(v).replace(',', '.')):.2f}"
    except:
        return "-"

def fmt_money(v):
    try:
        return f"{float(str(v).replace(',', '.')):.2f} zł"
    except:
        return "-"

def build_table(df, live=False):

    out = pd.DataFrame()

    def add(name, cols, fmt=None):
        for c in cols:
            if c in df.columns:
                if fmt:
                    out[name] = df[c].apply(fmt)
                else:
                    out[name] = df[c]
                return
        out[name] = "-"

    add("LEAGUE", ["liga","league"])
    add("MATCH", ["mecz","match"])
    add("MINUTE", ["minute"])
    add("SCORE", ["score"])
    add("SIGNAL", ["typ","signal"])
    add("BOOK ODDS", ["kurs_buk","odds"], fmt_float)
    add("BOT ODDS", ["kurs_bota","fair_odds"], fmt_float)
    add("MODEL ODDS", ["kurs_model"], fmt_float)
    add("EV", ["ev_percent","ev"], fmt_percent)
    add("EDGE", ["edge"], fmt_percent)
    add("MARGIN", ["marza_%"], fmt_percent)
    add("HOME xG", ["home_xg"], fmt_float)
    add("AWAY xG", ["away_xg"], fmt_float)
    add("CONF", ["confidence"], fmt_percent)
    add("STAKE", ["recommended_stake","stake"], fmt_money)
    add("RISK", ["risk_level","risk"])

    if live:
        cols = [
            "LEAGUE","MATCH","MINUTE","SCORE","SIGNAL",
            "BOOK ODDS","BOT ODDS","EV","EDGE",
            "CONF","STAKE","RISK"
        ]
    else:
        cols = [
            "LEAGUE","MATCH","SIGNAL",
            "BOOK ODDS","BOT ODDS","MODEL ODDS",
            "EV","EDGE","MARGIN",
            "HOME xG","AWAY xG",
            "CONF","STAKE","RISK"
        ]

    return out[cols]

df = load_csv()

live_df = pd.DataFrame()

if not df.empty and "minute" in df.columns:
    try:
        live_df = df[pd.to_numeric(df["minute"], errors="coerce") > 0]
    except:
        pass

st.markdown("""
<div class="kanibal-hero">
<div class="kanibal-title">⚽ KANIBAL ANALYTICS</div>
<div class="kanibal-sub">ANALIZA • PRZEWAGA • ZYSK</div>
</div>
""", unsafe_allow_html=True)

avg_ev = "0%"
avg_conf = "0%"

if not df.empty:
    try:
        avg_ev = fmt_percent(pd.to_numeric(df["ev_percent"], errors="coerce").mean())
    except:
        pass

    try:
        avg_conf = fmt_percent(pd.to_numeric(df["confidence"], errors="coerce").mean())
    except:
        pass

st.markdown(f"""
<div class="metric-grid">
<div class="metric-card">
<div class="metric-label">TOTAL SIGNALS</div>
<div class="metric-value">{len(df)}</div>
</div>

<div class="metric-card">
<div class="metric-label">LIVE MATCHES</div>
<div class="metric-value">{len(live_df)}</div>
</div>

<div class="metric-card">
<div class="metric-label">AVG EV</div>
<div class="metric-value">{avg_ev}</div>
</div>

<div class="metric-card">
<div class="metric-label">AVG CONFIDENCE</div>
<div class="metric-value">{avg_conf}</div>
</div>
</div>
""", unsafe_allow_html=True)

live_tab, prematch_tab, analytics_tab, settings_tab = st.tabs([
"📡 LIVE",
"🎯 PREMATCH",
"📊 ANALYTICS",
"⚙️ SETTINGS"
])

with live_tab:

    st.markdown("""
    <div class="panel">
    <div class="panel-title">📡 LIVE SIGNALS</div>
    <div class="panel-subtitle">MECZE LIVE</div>
    """, unsafe_allow_html=True)

    if live_df.empty:
        st.warning("Brak danych LIVE.")
    else:
        st.dataframe(
            build_table(live_df, live=True),
            use_container_width=True,
            height=650,
            hide_index=True
        )

    st.markdown("</div>", unsafe_allow_html=True)

with prematch_tab:

    st.markdown("""
    <div class="panel">
    <div class="panel-title">🎯 PREMATCH SIGNALS</div>
    <div class="panel-subtitle">KURSY • EV • EDGE • MARŻA • xG</div>
    """, unsafe_allow_html=True)

    if df.empty:
        st.warning("Brak danych PREMATCH.")
    else:
        st.dataframe(
            build_table(df),
            use_container_width=True,
            height=700,
            hide_index=True
        )

    st.markdown("</div>", unsafe_allow_html=True)

with analytics_tab:

    st.markdown("""
    <div class="panel">
    <div class="panel-title">📊 ANALYTICS</div>
    <div class="panel-subtitle">TOP VALUE</div>
    """, unsafe_allow_html=True)

    if not df.empty and "ev_percent" in df.columns:
        tmp = df.copy()
        tmp["_ev"] = pd.to_numeric(tmp["ev_percent"], errors="coerce")
        tmp = tmp.sort_values("_ev", ascending=False).head(15)

        st.dataframe(
            build_table(tmp),
            use_container_width=True,
            height=500,
            hide_index=True
        )

    st.markdown("</div>", unsafe_allow_html=True)

with settings_tab:

    st.success("Scheduler: ONLINE")
    st.success("Data API: ONLINE")
    st.success("Odds API: ONLINE")
    st.success("ETAPY 1–10: ACTIVE")

st.caption(f"Ostatnia aktualizacja: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
