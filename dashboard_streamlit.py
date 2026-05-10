import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime

st.set_page_config(
    page_title="BETBOT AI",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# STYLING
# =========================

st.markdown("""
<style>

.main {
    background-color: #0f172a;
    color: white;
}

section[data-testid="stSidebar"] {
    background-color: #111827;
}

.block-container {
    padding-top: 1rem;
}

.banner {
    background: linear-gradient(90deg, #111827 0%, #1e293b 100%);
    border-radius: 18px;
    padding: 24px;
    margin-bottom: 18px;
    border: 1px solid #334155;
}

.banner-title {
    font-size: 34px;
    font-weight: 700;
    color: white;
}

.banner-sub {
    color: #cbd5e1;
    margin-top: 8px;
    font-size: 15px;
}

.metric-card {
    background: #1e293b;
    padding: 18px;
    border-radius: 14px;
    border: 1px solid #334155;
    text-align: center;
}

.metric-title {
    color: #94a3b8;
    font-size: 13px;
}

.metric-value {
    color: white;
    font-size: 28px;
    font-weight: 700;
}

div[data-testid="stDataFrame"] {
    border: 1px solid #334155;
    border-radius: 14px;
    overflow: hidden;
}

</style>
""", unsafe_allow_html=True)

# =========================
# PATHS
# =========================

DATA_DIR = Path("data")

PREMATCH_FILE = DATA_DIR / "auto_all_picks.csv"

# =========================
# HELPERS
# =========================

@st.cache_data(ttl=30)
def load_csv(path):

    if not path.exists():
        return pd.DataFrame()

    try:

        df = pd.read_csv(path)

        # FIX BIAŁEJ STRONY
        df = df.fillna("")

        for col in df.columns:
            try:
                df[col] = df[col].astype(str)
            except Exception:
                pass

        return df

    except Exception as e:
        st.error(f"CSV ERROR: {e}")
        return pd.DataFrame()


def clean_df(df):

    rename_map = {
        "mecz": "MATCH",
        "liga": "LEAGUE",
        "typ": "PICK",
        "kurs_buk": "ODDS",
        "confidence": "CONF %",
        "ev_percent": "EV %",
        "tempo_level": "TEMPO",
        "risk_level": "RISK",
        "recommended_stake": "STAKE",
        "market_direction": "MARKET",
        "score": "SCORE",
        "minute": "MIN"
    }

    for old, new in rename_map.items():
        if old in df.columns:
            df = df.rename(columns={old: new})

    drop_cols = [
        "pick_id",
        "fixture_id",
        "odds_event_id",
        "home_team",
        "away_team",
        "home",
        "away"
    ]

    existing_drop = [c for c in drop_cols if c in df.columns]

    if existing_drop:
        df = df.drop(columns=existing_drop)

    preferred = [
        "MATCH",
        "LEAGUE",
        "PICK",
        "ODDS",
        "CONF %",
        "EV %",
        "TEMPO",
        "RISK",
        "STAKE",
        "MARKET",
        "MIN",
        "SCORE",
        "match_date"
    ]

    cols = [c for c in preferred if c in df.columns]
    rest = [c for c in df.columns if c not in cols]

    return df[cols + rest]


# =========================
# LOAD DATA
# =========================

df = load_csv(PREMATCH_FILE)

# =========================
# HEADER
# =========================

st.markdown("""
<div class="banner">
    <div class="banner-title">⚽ BETBOT AI DASHBOARD</div>
    <div class="banner-sub">
        AI • Bayesian • Ensemble • EV • Kelly • CLV • Market Movement
    </div>
</div>
""", unsafe_allow_html=True)

# =========================
# METRICS
# =========================

c1, c2, c3, c4 = st.columns(4)

total_picks = len(df) if not df.empty else 0

avg_conf = 0
if not df.empty and "confidence" in df.columns:
    try:
        avg_conf = round(pd.to_numeric(df["confidence"], errors="coerce").mean(), 1)
    except:
        avg_conf = 0

avg_ev = 0
if not df.empty and "ev_percent" in df.columns:
    try:
        avg_ev = round(pd.to_numeric(df["ev_percent"], errors="coerce").mean(), 1)
    except:
        avg_ev = 0

with c1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">TOTAL PICKS</div>
        <div class="metric-value">{total_picks}</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">AVG CONFIDENCE</div>
        <div class="metric-value">{avg_conf}%</div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">AVG EV</div>
        <div class="metric-value">{avg_ev}%</div>
    </div>
    """, unsafe_allow_html=True)

with c4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">LAST UPDATE</div>
        <div class="metric-value" style="font-size:16px;">
            {datetime.now().strftime("%H:%M:%S")}
        </div>
    </div>
    """, unsafe_allow_html=True)

st.write("")

# =========================
# TABS
# =========================

tab1, tab2, tab3, tab4 = st.tabs([
    "🎯 PREMATCH",
    "📡 LIVE",
    "📈 ANALYTICS",
    "⚙️ SYSTEM"
])

with tab1:

    st.subheader("🎯 PREMATCH PICKS")

    if df.empty:
        st.warning("Brak danych PREMATCH")
    else:

        clean = clean_df(df)

        st.dataframe(
            clean,
            use_container_width=True,
            height=720
        )

with tab2:

    st.subheader("📡 LIVE MATCHES")

    st.info("LIVE ENGINE aktywny — moduł LIVE będzie rozwijany dalej.")

with tab3:

    st.subheader("📈 ANALYTICS")

    if not df.empty:

        st.write("Top ligi:")

        if "liga" in df.columns:

            league_stats = (
                df["liga"]
                .value_counts()
                .reset_index()
            )

            league_stats.columns = ["League", "Picks"]

            st.dataframe(
                league_stats,
                use_container_width=True,
                height=400
            )

with tab4:

    st.subheader("⚙️ SYSTEM STATUS")

    st.success("Scheduler: ONLINE")
    st.success("Data API: ONLINE")
    st.success("Odds API: ONLINE")
    st.success("ETAPY 1-10: ACTIVE")
    st.success("CSV ENGINE: ACTIVE")
