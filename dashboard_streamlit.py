import streamlit as st
import pandas as pd
from pathlib import Path
import html

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
# HELPERS
# =========================

def safe_text(value):

    if pd.isna(value):
        return "-"

    return html.escape(str(value))


def load_csv(path):

    if path.exists():

        try:
            return pd.read_csv(path)

        except:
            return pd.DataFrame()

    return pd.DataFrame()


# =========================
# LOAD DATA
# =========================

live_df = load_csv(LIVE_FILE)

prematch_df = load_csv(PREMATCH_FILE)

# =========================
# CSS
# =========================

st.markdown(
    """
    <style>

    .stApp {

        background:
            radial-gradient(circle at top right, rgba(81,255,0,0.14), transparent 28%),
            radial-gradient(circle at top left, rgba(255,80,0,0.08), transparent 26%),
            linear-gradient(180deg, #050607 0%, #090b0d 45%, #050607 100%);

        color: #f5f5f5;
    }

    header[data-testid="stHeader"] {

        background: transparent;
    }

    .block-container {

        padding-top: 1.2rem;
        padding-left: 1rem;
        padding-right: 1rem;
        max-width: 1500px;
    }

    .panel {

        border: 1px solid rgba(255,255,255,0.08);

        border-radius: 16px;

        background:
            linear-gradient(
                180deg,
                rgba(255,255,255,0.045),
                rgba(255,255,255,0.018)
            );

        box-shadow: 0 18px 45px rgba(0,0,0,0.35);

        padding: 22px;

        margin-bottom: 18px;
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
        letter-spacing:.9px;
        text-transform:uppercase;
        margin-bottom:20px;
    }

    h1, h2 {

        color:white !important;
    }

    /* =========================
       NAVBAR
    ========================= */

    div[role="radiogroup"] {

        display:flex;
        gap:0;
        width:100%;
        border-radius:14px;
        overflow:hidden;
        border:1px solid rgba(255,255,255,0.08);
        margin-bottom:22px;
    }

    div[role="radiogroup"] label {

        flex:1;
        background:#090b0d;
        padding:18px 0;
        text-align:center;
        border-right:1px solid rgba(255,255,255,0.06);
    }

    div[role="radiogroup"] label:last-child {

        border-right:none;
    }

    div[role="radiogroup"] p {

        font-weight:800 !important;
        color:white !important;
        font-size:13px !important;
    }

    div[role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) {

        background:
            linear-gradient(
                180deg,
                rgba(88,255,47,0.15),
                rgba(88,255,47,0.05)
            );

        border-bottom:3px solid #58ff2f;
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
# NAVBAR
# =========================

selected_tab = st.radio(

    "",

    [
        "LIVE",
        "PREMATCH",
        "ANALYTICS",
        "HISTORY",
        "RANKING",
        "ALERTS",
        "SETTINGS"
    ],

    horizontal=True,
    label_visibility="collapsed"
)

# =========================
# LIVE
# =========================

if selected_tab == "LIVE":

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

        st.dataframe(
            live_df,
            use_container_width=True,
            height=min(
                700,
                35 * len(live_df) + 120
            )
        )

    else:

        st.warning("Brak danych LIVE")

    # =========================
    # CASHOUT GUIDE
    # =========================

    st.markdown(
        """
        <div class="panel">

            <h2>
                CASHOUT AI GUIDE
            </h2>

            <div style="
                margin-top:14px;
                padding:16px;
                border-radius:12px;
                border:1px solid rgba(88,255,47,0.35);
                background:rgba(88,255,47,0.08);
            ">

                <b style="color:#70ff2f;">
                    HOLD POSITION
                </b><br>

                <span style="color:#cfd4d8;">
                    Wysoka presja i momentum.
                </span>

            </div>

            <div style="
                margin-top:12px;
                padding:16px;
                border-radius:12px;
                border:1px solid rgba(255,210,26,0.35);
                background:rgba(255,210,26,0.08);
            ">

                <b style="color:#ffd21a;">
                    PARTIAL CASHOUT
                </b><br>

                <span style="color:#cfd4d8;">
                    Rozważ częściowe wyjście.
                </span>

            </div>

            <div style="
                margin-top:12px;
                padding:16px;
                border-radius:12px;
                border:1px solid rgba(255,59,48,0.35);
                background:rgba(255,59,48,0.08);
            ">

                <b style="color:#ff3b30;">
                    FULL CASHOUT
                </b><br>

                <span style="color:#cfd4d8;">
                    Wyjdź z zakładu.
                </span>

            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

# =========================
# PREMATCH
# =========================

elif selected_tab == "PREMATCH":

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

        wanted_columns = [

            "data",
            "liga",
            "mecz",
            "market",
            "typ",
            "kurs_buk",
            "kurs_model",
            "kurs_bota",
            "prawd_model",
            "prawd_rynek",
            "prawd_final",
            "edge",
            "ev",
            "kelly_full",
            "kelly_25",
            "home_xg",
            "away_xg",
            "marza_sum",
            "marza_%",
            "status"
        ]

        existing_columns = [

            col for col in wanted_columns
            if col in prematch_df.columns
        ]

        prematch_df = prematch_df[existing_columns]

        st.dataframe(
            prematch_df,
            use_container_width=True,
            height=min(
                700,
                35 * len(prematch_df) + 120
            )
        )

    else:

        st.warning("Brak danych PREMATCH")

# =========================
# ANALYTICS
# =========================

elif selected_tab == "ANALYTICS":

    st.markdown(
        """
        <div class="panel">

            <h2>
                ANALYTICS ENGINE
            </h2>

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
# HISTORY
# =========================

elif selected_tab == "HISTORY":

    st.markdown(
        """
        <div class="panel">

            <h2>
                HISTORY ENGINE
            </h2>

        </div>
        """,
        unsafe_allow_html=True
    )

    st.info("Historia zakładów.")

# =========================
# RANKING
# =========================

elif selected_tab == "RANKING":

    st.markdown(
        """
        <div class="panel">

            <h2>
                RANKING ENGINE
            </h2>

        </div>
        """,
        unsafe_allow_html=True
    )

    st.info("Ranking AI.")

# =========================
# ALERTS
# =========================

elif selected_tab == "ALERTS":

    st.markdown(
        """
        <div class="panel">

            <h2>
                ALERT ENGINE
            </h2>

        </div>
        """,
        unsafe_allow_html=True
    )

    st.info("Alerty AI.")

# =========================
# SETTINGS
# =========================

elif selected_tab == "SETTINGS":

    st.markdown(
        """
        <div class="panel">

            <h2>
                SETTINGS ENGINE
            </h2>

        </div>
        """,
        unsafe_allow_html=True
    )

    st.toggle("LIVE ENGINE", value=True)

    st.toggle("PREMATCH ENGINE", value=True)

    st.toggle("CASHOUT AI", value=True)

    st.toggle("BANKROLL ENGINE", value=True)
