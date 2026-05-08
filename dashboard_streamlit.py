import streamlit as st
import pandas as pd
from pathlib import Path

# =========================
# CONFIG
# =========================

st.set_page_config(
    page_title="KANIBAL ANALYTICS",
    layout="wide"
)

DATA_DIR = Path("data")

PREMATCH_FILE = DATA_DIR / "auto_all_picks.csv"
LIVE_FILE = DATA_DIR / "live_matches.csv"

# =========================
# CSS
# =========================

st.markdown(
    """
    <style>

    .stApp {

        background:
            linear-gradient(
                180deg,
                #050607 0%,
                #090b0d 100%
            );

        color:white;
    }

    .main-title {

        font-size:48px;
        font-weight:900;
        color:white;
        margin-bottom:0;
    }

    .subtitle {

        color:#58ff2f;
        font-size:16px;
        letter-spacing:2px;
        margin-bottom:30px;
    }

    .panel {

        background:
            linear-gradient(
                180deg,
                rgba(255,255,255,0.04),
                rgba(255,255,255,0.02)
            );

        border:1px solid rgba(255,255,255,0.08);

        border-radius:18px;

        padding:24px;

        margin-bottom:20px;
    }

    .section-title {

        color:white;
        font-size:34px;
        font-weight:900;
    }

    .section-sub {

        color:#8b949e;
        margin-bottom:20px;
    }

    </style>
    """,
    unsafe_allow_html=True
)

# =========================
# HEADER
# =========================

st.markdown(
    """
    <div class="main-title">
        🐺 KANIBAL ANALYTICS
    </div>

    <div class="subtitle">
        ANALIZA • PRZEWAGA • ZYSK
    </div>
    """,
    unsafe_allow_html=True
)

# =========================
# NAVBAR
# =========================

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🔴 LIVE",
    "📊 PREMATCH",
    "📈 ANALYTICS",
    "🕘 HISTORY",
    "🔔 ALERTS",
    "⚙️ SETTINGS"
])

# =========================
# LIVE TAB
# =========================

with tab1:

    st.markdown(
        """
        <div class="panel">

            <div class="section-title">
                LIVE ENGINE
            </div>

            <div class="section-sub">
                LIVE AI SIGNALS
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    if LIVE_FILE.exists():

        try:

            live_df = pd.read_csv(LIVE_FILE)

            st.dataframe(
                live_df,
                use_container_width=True,
                height=min(
                    700,
                    35 * len(live_df) + 120
                )
            )

        except:

            st.warning("Błąd LIVE DATA")

    else:

        st.warning("Brak danych LIVE")

# =========================
# PREMATCH TAB
# =========================

with tab2:

    st.markdown(
        """
        <div class="panel">

            <div class="section-title">
                PREMATCH ENGINE
            </div>

            <div class="section-sub">
                VALUE BETTING AI
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    if PREMATCH_FILE.exists():

        try:

            prematch_df = pd.read_csv(PREMATCH_FILE)

            st.dataframe(
                prematch_df,
                use_container_width=True,
                height=min(
                    700,
                    35 * len(prematch_df) + 120
                )
            )

        except:

            st.warning("Błąd PREMATCH DATA")

    else:

        st.warning("Brak danych PREMATCH")

# =========================
# ANALYTICS TAB
# =========================

with tab3:

    st.markdown(
        """
        <div class="panel">

            <div class="section-title">
                ANALYTICS ENGINE
            </div>

            <div class="section-sub">
                AI PERFORMANCE ANALYTICS
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "ROI",
            "+24.8%"
        )

    with col2:

        st.metric(
            "WIN RATE",
            "62.8%"
        )

    with col3:

        st.metric(
            "AI EDGE",
            "+13.4%"
        )

# =========================
# HISTORY TAB
# =========================

with tab4:

    st.markdown(
        """
        <div class="panel">

            <div class="section-title">
                HISTORY ENGINE
            </div>

            <div class="section-sub">
                HISTORY OF PICKS
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    st.info("Historia zakładów będzie tutaj.")

# =========================
# ALERTS TAB
# =========================

with tab5:

    st.markdown(
        """
        <div class="panel">

            <div class="section-title">
                ALERT ENGINE
            </div>

            <div class="section-sub">
                LIVE ALERTS & NOTIFICATIONS
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    st.info("Alerty AI będą tutaj.")

# =========================
# SETTINGS TAB
# =========================

with tab6:

    st.markdown(
        """
        <div class="panel">

            <div class="section-title">
                SETTINGS ENGINE
            </div>

            <div class="section-sub">
                BOT CONFIGURATION
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    st.toggle("LIVE ENGINE", value=True)

    st.toggle("PREMATCH ENGINE", value=True)

    st.toggle("CASHOUT AI", value=True)

    st.toggle("BANKROLL ENGINE", value=True)
