import streamlit as st
import pandas as pd
from pathlib import Path
import random
from datetime import datetime

# =========================
# CONFIG
# =========================

st.set_page_config(
    page_title="KANIBAL ANALYTICS",
    layout="wide",
    initial_sidebar_state="collapsed"
)

DATA_DIR = Path("data")

PREMATCH_FILE = DATA_DIR / "auto_all_picks.csv"
LIVE_FILE = DATA_DIR / "live_matches.csv"

BANNER_FILE = Path("kanibal_banner_pro.webp")

# =========================
# LOAD DATA
# =========================

def load_csv(path):

    if path.exists():

        try:
            return pd.read_csv(path)

        except:
            return pd.DataFrame()

    return pd.DataFrame()

# =========================
# LOAD LIVE
# =========================

live_df = load_csv(LIVE_FILE)

# =========================
# AUTO GENERATE LIVE DATA
# =========================

if live_df.empty:

    sample_live = pd.DataFrame([

        {
            "home": "Barcelona",
            "away": "Real Madrid",
            "league": "La Liga",
            "minute": random.randint(1, 90),
            "score": "2-1",
            "signal": "OVER 3.5",
            "confidence": 92,
            "ev": 14.2,
            "value": "HIGH",
            "cashout": "HOLD",
            "stake": "3%",
            "risk": "LOW",
            "status": "LIVE",
            "updated_at": datetime.utcnow()
        },

        {
            "home": "Liverpool",
            "away": "Arsenal",
            "league": "Premier League",
            "minute": random.randint(1, 90),
            "score": "1-1",
            "signal": "BTTS YES",
            "confidence": 88,
            "ev": 11.4,
            "value": "MEDIUM",
            "cashout": "PARTIAL",
            "stake": "2%",
            "risk": "MEDIUM",
            "status": "LIVE",
            "updated_at": datetime.utcnow()
        }

    ])

    DATA_DIR.mkdir(exist_ok=True)

    sample_live.to_csv(LIVE_FILE, index=False)

    live_df = sample_live

# =========================
# LOAD PREMATCH
# =========================

prematch_df = load_csv(PREMATCH_FILE)

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

# =========================
# BANNER
# =========================

if BANNER_FILE.exists():

    st.image(
        str(BANNER_FILE),
        use_container_width=True
    )

# =========================
# TABS
# =========================

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([

    "🚨 LIVE",
    "⚽ PREMATCH",
    "📊 ANALYTICS",
    "🕘 HISTORY",
    "🏆 RANKING",
    "🔔 ALERTS"

])

# =========================
# LIVE
# =========================

with tab1:

    st.markdown(
        """
        <div class="panel">

            <h2>
                LIVE SIGNALS
            </h2>

            <div style="
                color:#8f969d;
                font-size:12px;
                letter-spacing:1px;
                text-transform:uppercase;
            ">
                AKTUALIZOWANE CO 60 SEKUND
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        live_df.to_html(
            index=False,
            classes="custom-table"
        ),
        unsafe_allow_html=True
    )

    st.markdown(
        """
        <div class="panel">

            <h2 style="margin-bottom:20px;">
                CASHOUT AI GUIDE
            </h2>

            <div style="
                padding:18px;
                border-radius:14px;
                background:rgba(88,255,47,0.08);
                border:1px solid rgba(88,255,47,0.25);
                margin-bottom:14px;
            ">

                <div style="
                    display:inline-block;
                    padding:8px 14px;
                    border-radius:10px;
                    background:rgba(88,255,47,0.15);
                    color:#58ff2f;
                    font-weight:800;
                    margin-bottom:10px;
                ">
                    HOLD POSITION
                </div>

                <div style="color:#cfd4d8;">
                    Wysoka presja i momentum. Trzymaj zakład.
                </div>

            </div>

            <div style="
                padding:18px;
                border-radius:14px;
                background:rgba(255,210,26,0.08);
                border:1px solid rgba(255,210,26,0.25);
                margin-bottom:14px;
            ">

                <div style="
                    display:inline-block;
                    padding:8px 14px;
                    border-radius:10px;
                    background:rgba(255,210,26,0.15);
                    color:#ffd21a;
                    font-weight:800;
                    margin-bottom:10px;
                ">
                    PARTIAL CASHOUT
                </div>

                <div style="color:#cfd4d8;">
                    Spadający confidence. Rozważ częściowe wyjście.
                </div>

            </div>

            <div style="
                padding:18px;
                border-radius:14px;
                background:rgba(255,59,48,0.08);
                border:1px solid rgba(255,59,48,0.25);
            ">

                <div style="
                    display:inline-block;
                    padding:8px 14px;
                    border-radius:10px;
                    background:rgba(255,59,48,0.15);
                    color:#ff3b30;
                    font-weight:800;
                    margin-bottom:10px;
                ">
                    FULL CASHOUT
                </div>

                <div style="color:#cfd4d8;">
                    Niski momentum i presja. Wyjdź z zakładu.
                </div>

            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

# =========================
# PREMATCH
# =========================

with tab2:

    st.markdown(
        """
        <div class="panel">

            <h2>
                PREMATCH PICKS
            </h2>

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

# =========================
# ANALYTICS
# =========================

with tab3:

    st.markdown(
        """
        <div class="panel">
            <h2>ANALYTICS ENGINE</h2>
        </div>
        """,
        unsafe_allow_html=True
    )

# =========================
# HISTORY
# =========================

with tab4:

    st.markdown(
        """
        <div class="panel">
            <h2>HISTORY ENGINE</h2>
        </div>
        """,
        unsafe_allow_html=True
    )

# =========================
# RANKING
# =========================

with tab5:

    st.markdown(
        """
        <div class="panel">
            <h2>RANKING ENGINE</h2>
        </div>
        """,
        unsafe_allow_html=True
    )

# =========================
# ALERTS
# =========================

with tab6:

    st.markdown(
        """
        <div class="panel">
            <h2>ALERT ENGINE</h2>
        </div>
        """,
        unsafe_allow_html=True
    )
