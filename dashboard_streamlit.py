import streamlit as st
import pandas as pd
from pathlib import Path

# =========================
# CONFIG
# =========================

st.set_page_config(
    page_title="KANIBAL ANALYTICS",
    layout="wide",
    initial_sidebar_state="collapsed"
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

PREMATCH_FILE = DATA_DIR / "auto_all_picks.csv"
LIVE_FILE = DATA_DIR / "live_matches.csv"

BANNER_FILE = BASE_DIR / "kanibal_banner_pro.webp"

# =========================
# HELPERS
# =========================

def load_csv(path: Path):

    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path)

    except Exception:
        return pd.DataFrame()


def first_existing(row, columns, default="-"):

    for col in columns:

        if col in row:

            value = row.get(col)

            if pd.notna(value):

                value = str(value).strip()

                if value != "" and value.lower() != "nan":
                    return value

    return default


def format_confidence(value):

    try:

        value = float(value)

        if value <= 1:
            value *= 100

        return f"{value:.0f}%"

    except:
        return "-"


# =========================
# LOAD DATA
# =========================

live_df = load_csv(LIVE_FILE)

# fallback gdy live pusty
if live_df.empty or len(live_df.columns) <= 1:

    live_df = load_csv(PREMATCH_FILE)

# dodatkowy fallback
if live_df.empty:

    live_df = pd.DataFrame()

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

    .live-card {

        background:
            linear-gradient(
                180deg,
                rgba(255,255,255,0.045),
                rgba(255,255,255,0.018)
            );

        border: 1px solid rgba(255,255,255,0.08);

        border-radius: 18px;

        box-shadow: 0 18px 45px rgba(0,0,0,0.35);

        margin-bottom: 18px;

        padding: 20px;

        color: white;
    }

    .live-title {
        font-size: 34px;
        font-weight: 900;
        color: white;
        margin-bottom: 6px;
    }

    .live-league {
        color: rgba(255,255,255,0.82);
        font-size: 15px;
        margin-bottom: 16px;
    }

    .live-score {
        font-size: 18px;
        font-weight: 800;
        margin-bottom: 10px;
        color: white;
    }

    .live-type {
        color: #58ff2f;
        font-size: 20px;
        font-weight: 900;
        margin-bottom: 18px;
    }

    .live-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin-top: 10px;
    }

    .live-box {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px;
        padding: 18px;
    }

    .live-label {
        color: rgba(255,255,255,0.75);
        font-size: 13px;
        font-weight: 800;
        margin-bottom: 10px;
    }

    .live-value {
        color: white;
        font-size: 34px;
        font-weight: 900;
    }

    .tempo-box {
        margin-top: 16px;
        padding: 14px;
        border-radius: 14px;
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        color: white;
        font-size: 16px;
        font-weight: 800;
    }

    div[data-testid="stTable"] table {
        width: 100% !important;
        border-collapse: collapse !important;
        background: #0d1014 !important;
        color: #f2f2f2 !important;
        font-size: 14px !important;
    }

    div[data-testid="stTable"] th {
        background: #11161c !important;
        color: #58ff2f !important;
        padding: 14px 12px !important;
        text-align: left !important;
        border-bottom: 1px solid rgba(255,255,255,0.08) !important;
        font-weight: 900 !important;
    }

    div[data-testid="stTable"] td {
        padding: 13px 12px !important;
        border-bottom: 1px solid rgba(255,255,255,0.05) !important;
        color: #f2f2f2 !important;
    }

    </style>
    """,
    unsafe_allow_html=True
)

# =========================
# HEADER
# =========================

if BANNER_FILE.exists():

    st.image(
        str(BANNER_FILE),
        use_container_width=True
    )

else:

    st.title("KANIBAL ANALYTICS")

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

    st.header("🟢 LIVE SIGNALS")
    st.caption("AKTUALIZOWANE CO 60 SEKUND")

    if live_df.empty:

        st.warning("Brak danych LIVE")

    else:

        for _, row in live_df.iterrows():

            home = first_existing(
                row,
                ["home", "home_team", "gospodarze"],
                "HOME"
            )

            away = first_existing(
                row,
                ["away", "away_team", "goscie"],
                "AWAY"
            )

            match_name = f"{home} vs {away}"

            league = first_existing(
                row,
                ["league", "liga"],
                "-"
            )

            score = first_existing(
                row,
                ["score"],
                "-"
            )

            signal = first_existing(
                row,
                ["signal", "typ", "market"],
                "BRAK TYPU"
            )

            ev = first_existing(
                row,
                ["ev"],
                "-"
            )

            confidence = format_confidence(
                first_existing(
                    row,
                    ["confidence"],
                    0
                )
            )

            minute = first_existing(
                row,
                ["minute"],
                "LIVE"
            )

            status = first_existing(
                row,
                ["status"],
                "LIVE"
            )

            risk = first_existing(
                row,
                ["risk"],
                "LOW"
            )

            risk_upper = str(risk).upper()

            if risk_upper in ["HIGH", "TOP"]:
                tempo = "🔥 HIGH TEMPO"

            elif risk_upper in ["MEDIUM"]:
                tempo = "⚡ MEDIUM TEMPO"

            else:
                tempo = "🧊 LOW TEMPO"

            st.markdown(
                f"""
                <div class="live-card">

                    <div class="live-title">
                        {match_name}
                    </div>

                    <div class="live-league">
                        🏆 {league}
                    </div>

                    <div class="live-score">
                        ⚽ WYNIK: {score}
                    </div>

                    <div class="live-type">
                        🎯 TYP: {signal}
                    </div>

                    <div class="live-grid">

                        <div class="live-box">
                            <div class="live-label">EV</div>
                            <div class="live-value">{ev}</div>
                        </div>

                        <div class="live-box">
                            <div class="live-label">CONF</div>
                            <div class="live-value">{confidence}</div>
                        </div>

                        <div class="live-box">
                            <div class="live-label">MIN</div>
                            <div class="live-value">{minute}</div>
                        </div>

                        <div class="live-box">
                            <div class="live-label">STATUS</div>
                            <div class="live-value">{status}</div>
                        </div>

                    </div>

                    <div class="tempo-box">
                        📈 DYNAMIKA MECZU: {tempo}
                    </div>

                </div>
                """,
                unsafe_allow_html=True
            )

# =========================
# PREMATCH
# =========================

with prematch_tab:

    st.header("🟢 PREMATCH PICKS")

    if prematch_df.empty:

        st.warning("Brak danych PREMATCH")

    else:

        st.table(prematch_df)

# =========================
# ANALYTICS
# =========================

with analytics_tab:

    st.header("📊 ANALYTICS")

    st.metric(
        "TOTAL SIGNALS",
        len(live_df)
    )

# =========================
# HISTORY
# =========================

with history_tab:

    st.info("Historia będzie dostępna później.")

# =========================
# RANKING
# =========================

with ranking_tab:

    st.info("Ranking będzie dostępny później.")

# =========================
# ALERTS
# =========================

with alerts_tab:

    st.info("Alerty będą dostępne później.")
