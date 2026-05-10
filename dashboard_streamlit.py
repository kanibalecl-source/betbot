import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="KANIBAL ANALYTICS",
    layout="wide",
    initial_sidebar_state="collapsed"
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CSV_FILE = DATA_DIR / "auto_all_picks.csv"

# =====================================================
# LOAD CSV
# =====================================================

def load_csv():

    if not CSV_FILE.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(CSV_FILE)

    except Exception:
        try:
            df = pd.read_csv(CSV_FILE, encoding="utf-8")
        except:
            return pd.DataFrame()

    # FIX WHITE SCREEN
    df = df.fillna("")

    for col in df.columns:
        try:
            df[col] = df[col].astype(str)
        except:
            pass

    return df


df = load_csv()

# =====================================================
# HELPERS
# =====================================================

def only_existing_columns(dataframe, columns):

    existing = [
        c for c in columns
        if c in dataframe.columns
    ]

    return dataframe[existing]


# =====================================================
# CSS
# =====================================================

st.markdown("""
<style>

.stApp {
    background:
        radial-gradient(circle at top right, rgba(81,255,0,0.12), transparent 28%),
        linear-gradient(180deg, #050607 0%, #090b0d 100%);
    color: white;
}

header[data-testid="stHeader"] {
    background: transparent;
}

.block-container {
    max-width: 100% !important;
    padding-top: 0.6rem;
    padding-left: 1.8rem;
    padding-right: 1.8rem;
}

h1, h2, h3 {
    color: white !important;
    font-weight: 900 !important;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    background: #090b0d;
    border-radius: 14px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.08);
    margin-top: 16px;
    margin-bottom: 24px;
}

.stTabs [data-baseweb="tab"] {
    height: 68px;
    background: #090b0d;
    color: white;
    font-weight: 800;
    font-size: 13px;
    border-right: 1px solid rgba(255,255,255,0.06);
    flex-grow: 1;
}

.stTabs [aria-selected="true"] {
    background:
        linear-gradient(
            180deg,
            rgba(88,255,47,0.15),
            rgba(88,255,47,0.05)
        ) !important;

    color: #58ff2f !important;
    border-bottom: 3px solid #58ff2f !important;
}

div[data-testid="stDataFrame"] {
    background: rgba(8,12,18,0.96) !important;
    border: 1px solid rgba(114,255,47,0.16) !important;
    border-radius: 18px !important;
    overflow: hidden !important;
    box-shadow: 0 0 28px rgba(114,255,47,0.08) !important;
}

div[data-testid="stDataFrame"] table {
    background: #0d1014 !important;
    color: #f2f2f2 !important;
}

div[data-testid="stDataFrame"] th {
    background: #11161c !important;
    color: #58ff2f !important;
    font-weight: 900 !important;
    font-size: 12px !important;
    text-align:center !important;
}

div[data-testid="stDataFrame"] td {
    color: #f2f2f2 !important;
    font-size: 12px !important;
    text-align:center !important;
}

div[data-testid="stDataFrame"] tbody tr:hover {
    background: rgba(88,255,47,0.08) !important;
    transition: 0.2s ease;
}

.metric-box {
    background:
        linear-gradient(
            180deg,
            rgba(255,255,255,0.04),
            rgba(255,255,255,0.015)
        );

    border: 1px solid rgba(255,255,255,0.08);

    border-radius: 18px;

    padding: 20px;

    margin-bottom: 18px;
}

.hero {
    background:
        linear-gradient(
            90deg,
            rgba(8,10,14,0.98),
            rgba(13,18,25,0.94)
        );

    border: 1px solid rgba(255,255,255,0.08);

    border-radius: 24px;

    padding: 34px;

    margin-bottom: 20px;

    box-shadow: 0 24px 70px rgba(0,0,0,0.45);
}

.hero-title {
    font-size: 54px;
    font-weight: 900;
    color: white;
}

.hero-sub {
    color: #9ca3af;
    letter-spacing: 4px;
    margin-top: 10px;
}

</style>
""", unsafe_allow_html=True)

# =====================================================
# HERO
# =====================================================

st.markdown("""
<div class="hero">
<div class="hero-title">⚽ KANIBAL ANALYTICS</div>
<div class="hero-sub">ANALIZA • PRZEWAGA • ZYSK</div>
</div>
""", unsafe_allow_html=True)

# =====================================================
# METRICS
# =====================================================

c1, c2, c3, c4 = st.columns(4)

live_df = pd.DataFrame()

if not df.empty and "minute" in df.columns:
    try:
        live_df = df[
            pd.to_numeric(
                df["minute"],
                errors="coerce"
            ).fillna(0) > 0
        ]
    except:
        pass

with c1:
    st.metric("TOTAL SIGNALS", len(df))

with c2:
    st.metric("LIVE MATCHES", len(live_df))

with c3:

    if "ev_percent" in df.columns:
        try:
            avg_ev = pd.to_numeric(
                df["ev_percent"],
                errors="coerce"
            ).mean()

            st.metric("AVG EV", f"{avg_ev:.2f}%")
        except:
            st.metric("AVG EV", "-")

with c4:

    if "confidence" in df.columns:
        try:
            avg_conf = pd.to_numeric(
                df["confidence"],
                errors="coerce"
            ).mean()

            st.metric("AVG CONFIDENCE", f"{avg_conf:.0f}%")
        except:
            st.metric("AVG CONFIDENCE", "-")

# =====================================================
# TABS
# =====================================================

live_tab, prematch_tab, analytics_tab = st.tabs([
    "🚨 LIVE",
    "⚽ PREMATCH",
    "📊 ANALYTICS"
])

# =====================================================
# LIVE
# =====================================================

with live_tab:

    st.header("🟢 LIVE SIGNALS")

    if live_df.empty:

        st.warning("Brak danych LIVE")

    else:

        st.dataframe(
            live_df,
            use_container_width=True,
            hide_index=True,
            height=700
        )

# =====================================================
# PREMATCH
# =====================================================

with prematch_tab:

    st.header("🟢 PREMATCH PICKS")

    if df.empty:

        st.warning("Brak danych PREMATCH")

    else:

        prematch_columns = [
            "data",
            "liga",
            "mecz",
            "typ",
            "confidence",
            "prawd_final",
            "kurs_buk",
            "kurs_model",
            "kurs_bota",
            "prawd_model",
            "prawd_rynek",
            "edge",
            "ev",
            "ev_percent",
            "kelly_full",
            "kelly_25",
            "home_xg",
            "away_xg",
            "marza_sum",
            "marza_%",
            "status"
        ]

        prematch_view = only_existing_columns(
            df,
            prematch_columns
        )

        st.dataframe(
            prematch_view,
            use_container_width=True,
            hide_index=True,
            height=720
        )

# =====================================================
# ANALYTICS
# =====================================================

with analytics_tab:

    st.header("📊 ANALYTICS")

    st.metric("TOTAL SIGNALS", len(df))
