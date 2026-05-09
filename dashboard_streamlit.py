import streamlit as st
import pandas as pd
from pathlib import Path
import os

# =========================
# CONFIG
# =========================

st.set_page_config(
    page_title="KANIBAL ANALYTICS",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =========================
# AUTO CSV DETECTION
# =========================

POSSIBLE_PATHS = [
    Path("/app/data/auto_all_picks.csv"),
    Path("data/auto_all_picks.csv"),
    Path("auto_all_picks.csv"),
]

LIVE_FILE = None

for path in POSSIBLE_PATHS:
    if path.exists():
        LIVE_FILE = path
        break

if LIVE_FILE is None:
    LIVE_FILE = POSSIBLE_PATHS[0]

PREMATCH_FILE = LIVE_FILE

BANNER_FILE = Path("kanibal_banner_pro.webp")

print(f"📂 LIVE FILE -> {LIVE_FILE}")

# =========================
# DATA
# =========================

def load_csv(path: Path) -> pd.DataFrame:
    try:
        print(f"📡 LOADING -> {path}")

        if not path.exists():
            print(f"❌ FILE NOT FOUND -> {path}")
            return pd.DataFrame()

        df = pd.read_csv(path)

        print(f"✅ ROWS LOADED -> {len(df)}")

        return df

    except Exception as e:
        print(f"❌ CSV ERROR -> {e}")

        return pd.DataFrame()


live_df = load_csv(LIVE_FILE)

if live_df.empty:
    print("❌ LIVE EMPTY")
else:
    print(f"✅ LIVE ROWS -> {len(live_df)}")

prematch_df = load_csv(PREMATCH_FILE)

if prematch_df.empty:
    print("❌ PREMATCH EMPTY")
else:
    print(f"✅ PREMATCH ROWS -> {len(prematch_df)}")

# =========================
# CSS
# =========================

st.markdown(
    """
    <style>

        .stApp {
            background:
                radial-gradient(circle at top right, rgba(81,255,0,0.12), transparent 28%),
                radial-gradient(circle at top left, rgba(255,80,0,0.08), transparent 26%),
                linear-gradient(180deg, #050607 0%, #090b0d 45%, #050607 100%);
            color: white;
        }

        header[data-testid="stHeader"] {
            background: transparent;
        }

        .block-container {
            max-width: 100% !important;
            padding-top: 0.6rem;
            padding-left: 1rem;
            padding-right: 1rem;
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
            width: 100%;
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

        .stDataFrame {
            width: 100% !important;
            overflow-x: auto !important;
        }

        .stDataFrame table {
            min-width: 2800px !important;
        }

        iframe {
            width: 100% !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            background:
                linear-gradient(
                    180deg,
                    rgba(255,255,255,0.045),
                    rgba(255,255,255,0.018)
                );

            border: 1px solid rgba(255,255,255,0.08);

            border-radius: 18px;

            box-shadow: 0 18px 45px rgba(0,0,0,0.35);
        }

    </style>
    """,
    unsafe_allow_html=True
)

# =========================
# HEADER
# =========================

if BANNER_FILE.exists():
    st.image(str(BANNER_FILE), width="stretch")
else:
    st.title("KANIBAL ANALYTICS")
    st.caption("ANALIZA • PRZEWAGA • ZYSK")

# =========================
# TABS
# =========================

live_tab, prematch_tab, analytics_tab, history_tab, ranking_tab, alerts_tab = st.tabs(
    [
        "🚨 LIVE",
        "⚽ PREMATCH",
        "📊 ANALYTICS",
        "🕘 HISTORY",
        "🏆 RANKING",
        "🔔 ALERTS"
    ]
)

# =========================
# LIVE
# =========================

with live_tab:

    with st.container(border=True):
        st.header("🟢 LIVE SIGNALS")
        st.caption("AKTUALIZOWANE CO 60 SEKUND")

    if live_df.empty:

        st.warning("Brak danych LIVE")

    else:

        st.dataframe(
            live_df,
            width=3000,
            height=900,
            hide_index=True
        )

# =========================
# PREMATCH
# =========================

with prematch_tab:

    with st.container(border=True):
        st.header("🟢 PREMATCH PICKS")
        st.caption("CORE VALUE ENGINE")

    if prematch_df.empty:

        st.warning("Brak danych PREMATCH")

    else:

        st.dataframe(
            prematch_df,
            width=3000,
            height=900,
            hide_index=True
        )

# =========================
# ANALYTICS
# =========================

with analytics_tab:

    with st.container(border=True):
        st.header("📊 ANALYTICS ENGINE")
        st.caption("AI PERFORMANCE ANALYTICS")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("ROI", "+24.8%")

    with col2:
        st.metric("WIN RATE", "62.8%")

    with col3:
        st.metric("AI EDGE", "+13.4%")

    with col4:
        st.metric("TOTAL SIGNALS", len(live_df) + len(prematch_df))

# =========================
# HISTORY
# =========================

with history_tab:

    st.info("Historia zakładów będzie dostępna po wdrożeniu Settlement Engine.")

# =========================
# RANKING
# =========================

with ranking_tab:

    if prematch_df.empty:

        st.warning("Brak danych do rankingu")

    else:

        ranking_df = prematch_df.copy()

        if "ev" in ranking_df.columns:

            ranking_df["ev"] = pd.to_numeric(
                ranking_df["ev"],
                errors="coerce"
            ).fillna(0)

            ranking_df = ranking_df.sort_values(
                "ev",
                ascending=False
            ).head(10)

        st.dataframe(
            ranking_df,
            width=3000,
            height=700,
            hide_index=True
        )

# =========================
# ALERTS
# =========================

with alerts_tab:

    st.info("Alerty AI będą dostępne po podłączeniu systemu powiadomień.")
