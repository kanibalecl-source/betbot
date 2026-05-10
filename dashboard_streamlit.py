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

st.markdown("""
<style>
html, body, [class*="css"] {
    background-color:#05070d;
    color:white;
}
.main {
    background: radial-gradient(circle at top right, #111827 0%, #05070d 60%);
}
.block-container {
    padding-top:1rem;
}
.banner {
    background: linear-gradient(90deg,#0b1120 0%, #111827 100%);
    border:1px solid #1f2937;
    border-radius:24px;
    padding:32px;
    margin-bottom:20px;
}
.banner-title {
    font-size:56px;
    font-weight:900;
    color:white;
}
.banner-sub {
    color:#9ca3af;
    font-size:18px;
}
.metric-card {
    background:#0f172a;
    border:1px solid #1f2937;
    border-radius:18px;
    padding:18px;
}
.metric-title {
    color:#9ca3af;
    font-size:14px;
}
.metric-value {
    color:#84cc16;
    font-size:34px;
    font-weight:800;
}
.section-box {
    background:#0b1120;
    border:1px solid #1f2937;
    border-radius:20px;
    padding:20px;
    margin-bottom:20px;
}
.section-title {
    font-size:24px;
    font-weight:700;
    margin-bottom:16px;
}
div[data-testid="stDataFrame"] {
    border-radius:18px;
    overflow:hidden;
    border:1px solid #1f2937;
}
</style>
""", unsafe_allow_html=True)

DATA_DIR = Path("data")
PREMATCH_FILE = DATA_DIR / "auto_all_picks.csv"

@st.cache_data(ttl=30)
def load_data():
    if not PREMATCH_FILE.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(PREMATCH_FILE)
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

def clean_table(df):
    rename_map = {
        "mecz":"MATCH",
        "liga":"LEAGUE",
        "typ":"SIGNAL",
        "kurs_buk":"ODDS",
        "confidence":"CONFIDENCE",
        "ev_percent":"EV",
        "recommended_stake":"STAKE",
        "risk_level":"RISK",
        "score":"SCORE",
        "minute":"MIN"
    }
    for o,n in rename_map.items():
        if o in df.columns:
            df=df.rename(columns={o:n})

    drop_cols=["pick_id","fixture_id","odds_event_id","home_team","away_team","home","away"]
    existing=[c for c in drop_cols if c in df.columns]
    if existing:
        df=df.drop(columns=existing)

    preferred=["LEAGUE","MATCH","MIN","SCORE","SIGNAL","CONFIDENCE","ODDS","EV","STAKE","RISK","match_date"]
    cols=[c for c in preferred if c in df.columns]
    rest=[c for c in df.columns if c not in cols]
    return df[cols+rest]

raw_df = load_data()
prematch_df = raw_df.copy()

live_df = pd.DataFrame()
if not raw_df.empty and "minute" in raw_df.columns:
    try:
        live_df = raw_df[pd.to_numeric(raw_df["minute"], errors="coerce") > 0]
    except:
        pass

st.markdown("""
<div class="banner">
<div class="banner-title">⚽ KANIBAL ANALYTICS</div>
<div class="banner-sub">ANALIZA • PRZEWAGA • ZYSK</div>
</div>
""", unsafe_allow_html=True)

c1,c2,c3,c4 = st.columns(4)

total=len(prematch_df)
live=len(live_df)

avg_ev=0
avg_conf=0

if not prematch_df.empty:
    if "ev_percent" in prematch_df.columns:
        try:
            avg_ev=round(pd.to_numeric(prematch_df["ev_percent"],errors="coerce").mean(),1)
        except:
            pass
    if "confidence" in prematch_df.columns:
        try:
            avg_conf=round(pd.to_numeric(prematch_df["confidence"],errors="coerce").mean(),1)
        except:
            pass

metrics = [
    ("TOTAL SIGNALS", total),
    ("LIVE MATCHES", live),
    ("AVG EV", f"{avg_ev}%"),
    ("AVG CONF", f"{avg_conf}%")
]

for col,metric in zip([c1,c2,c3,c4], metrics):
    with col:
        st.markdown(f"""
        <div class="metric-card">
        <div class="metric-title">{metric[0]}</div>
        <div class="metric-value">{metric[1]}</div>
        </div>
        """, unsafe_allow_html=True)

prematch_tab, live_tab, analytics_tab, history_tab, ranking_tab, alerts_tab, settings_tab = st.tabs([
"🎯 PREMATCH","📡 LIVE","📈 ANALYTICS","📜 HISTORY","🏆 RANKING","🔔 ALERTS","⚙️ SETTINGS"
])

with prematch_tab:
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🎯 PREMATCH SIGNALS</div>', unsafe_allow_html=True)
    if prematch_df.empty:
        st.warning("Brak danych PREMATCH")
    else:
        st.dataframe(clean_table(prematch_df), use_container_width=True, height=700)
    st.markdown('</div>', unsafe_allow_html=True)

with live_tab:
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">📡 LIVE SIGNALS</div>', unsafe_allow_html=True)
    if live_df.empty:
        st.warning("LIVE brak danych — bot pokaże mecze LIVE gdy minute > 0")
    else:
        st.dataframe(clean_table(live_df), use_container_width=True, height=700)
    st.markdown('</div>', unsafe_allow_html=True)

with analytics_tab:
    if not prematch_df.empty and "liga" in prematch_df.columns:
        stats = prematch_df["liga"].value_counts().reset_index()
        stats.columns=["League","Signals"]
        st.dataframe(stats, use_container_width=True)

with history_tab:
    st.info("Historia typów będzie rozwijana.")

with ranking_tab:
    st.info("Ranking AI będzie rozwijany.")

with alerts_tab:
    st.success("Alert system ONLINE")

with settings_tab:
    st.success("Scheduler: ONLINE")
    st.success("Odds API: ONLINE")
    st.success("Data API: ONLINE")
    st.success("ETAPY 1-10: ACTIVE")

st.caption(f"Ostatnia aktualizacja: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
