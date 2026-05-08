import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="KANIBAL ANALYTICS",
    layout="wide",
    initial_sidebar_state="collapsed"
)

DATA_DIR = Path("data")

PREMATCH_FILE = DATA_DIR / "auto_all_picks.csv"
LIVE_FILE = DATA_DIR / "live_matches.csv"

BANNER_FILE = Path("kanibal_banner_pro.webp")


def load_csv(path):

    if path.exists():

        try:
            return pd.read_csv(path)

        except:
            return pd.DataFrame()

    return pd.DataFrame()


live_df = load_csv(LIVE_FILE)
prematch_df = load_csv(PREMATCH_FILE)

st.markdown(
    """
    <style>

    .stApp {

        background:
            radial-gradient(circle at top right, rgba(81,255,0,0.12), transparent 28%),
            radial-gradient(circle at top left, rgba(255,80,0,0.08), transparent 26%),
            linear-gradient(180deg, #050607 0%, #090b0d 45%, #050607 100%);

        color:white;
    }

    header[data-testid="stHeader"] {
        background:transparent;
    }

    .block-container {
        max-width:100% !important;
        padding-top:0.6rem;
        padding-left:2rem;
        padding-right:2rem;
    }

    .panel {

        border:1px solid rgba(255,255,255,0.08);
        border-radius:18px;

        background:
            linear-gradient(
                180deg,
                rgba(255,255,255,0.045),
                rgba(255,255,255,0.018)
            );

        padding:26px;
        margin-bottom:22px;
        box-shadow:0 18px 45px rgba(0,0,0,0.35);
    }

    .panel-title {
        display:flex;
        align-items:center;
        gap:12px;
        margin-bottom:6px;
    }

    .green-dot {
        width:14px;
        height:14px;
        border-radius:50%;
        background:#58ff2f;
        box-shadow:0 0 16px rgba(88,255,47,0.9);
    }

    .subtitle {
        color:#8f969d;
        font-size:12px;
        letter-spacing:1px;
        text-transform:uppercase;
        margin-top:8px;
    }

    h1, h2 {
        color:white !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap:0;
        background:#090b0d;
        border-radius:14px;
        overflow:hidden;
        border:1px solid rgba(255,255,255,0.08);
        margin-top:16px;
        margin-bottom:24px;
    }

    .stTabs [data-baseweb="tab"] {
        height:68px;
        background:#090b0d;
        color:white;
        font-weight:800;
        font-size:13px;
        border-right:1px solid rgba(255,255,255,0.06);
        flex-grow:1;
    }

    .stTabs [aria-selected="true"] {

        background:
            linear-gradient(
                180deg,
                rgba(88,255,47,0.15),
                rgba(88,255,47,0.05)
            ) !important;

        color:#58ff2f !important;
        border-bottom:3px solid #58ff2f !important;
    }

    .custom-table {
        width:100%;
        border-collapse:collapse;
        background:#0d1014;
        border-radius:14px;
        overflow:hidden;
        font-size:14px;
        margin-top:12px;
    }

    .custom-table th {
        background:#11161c;
        color:#58ff2f;
        padding:16px;
        text-align:left;
        border-bottom:1px solid rgba(255,255,255,0.08);
    }

    .custom-table td {
        padding:14px 16px;
        border-bottom:1px solid rgba(255,255,255,0.05);
        color:#f2f2f2;
    }

    .custom-table tr:hover {
        background:rgba(88,255,47,0.06);
    }

    table {
        width:100% !important;
    }

    </style>
    """,
    unsafe_allow_html=True
)

if BANNER_FILE.exists():

    st.image(
        str(BANNER_FILE),
        use_container_width=True
    )


live_tab, prematch_tab, analytics_tab, history_tab, ranking_tab, alerts_tab = st.tabs([

    "🚨 LIVE",
    "⚽ PREMATCH",
    "📊 ANALYTICS",
    "🕘 HISTORY",
    "🏆 RANKING",
    "🔔 ALERTS"

])


with live_tab:

    st.markdown(
        """
        <div class="panel">

            <div class="panel-title">
                <div class="green-dot"></div>

                <h2 style="margin:0;">
                    LIVE SIGNALS
                </h2>
            </div>

            <div class="subtitle">
                AKTUALIZOWANE CO 60 SEKUND
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    if not live_df.empty:

        st.markdown(
            live_df.to_html(
                index=False,
                classes="custom-table"
            ),
            unsafe_allow_html=True
        )

    else:

        st.warning("Brak danych LIVE")


with prematch_tab:

    st.markdown(
        """
        <div class="panel">

            <div class="panel-title">
                <div class="green-dot"></div>

                <h2 style="margin:0;">
                    PREMATCH PICKS
                </h2>
            </div>

            <div class="subtitle">
                CORE VALUE ENGINE
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    if not prematch_df.empty:

        st.markdown(
            prematch_df.to_html(
                index=False,
                classes="custom-table"
            ),
            unsafe_allow_html=True
        )

    else:

        st.warning("Brak danych PREMATCH")


with analytics_tab:

    st.markdown(
        """
        <div class="panel">
            <h2>ANALYTICS ENGINE</h2>
        </div>
        """,
        unsafe_allow_html=True
    )


with history_tab:

    st.markdown(
        """
        <div class="panel">
            <h2>HISTORY ENGINE</h2>
        </div>
        """,
        unsafe_allow_html=True
    )


with ranking_tab:

    st.markdown(
        """
        <div class="panel">
            <h2>RANKING ENGINE</h2>
        </div>
        """,
        unsafe_allow_html=True
    )


with alerts_tab:

    st.markdown(
        """
        <div class="panel">
            <h2>ALERT ENGINE</h2>
        </div>
        """,
        unsafe_allow_html=True
    )
