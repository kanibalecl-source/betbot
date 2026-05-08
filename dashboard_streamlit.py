import streamlit as st
import pandas as pd
from pathlib import Path
import requests
import random

# =========================
# CONFIG
# =========================

st.set_page_config(
    page_title="KANIBAL ANALYTICS",
    layout="wide",
    initial_sidebar_state="collapsed"
)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

PREMATCH_FILE = DATA_DIR / "auto_all_picks.csv"
LIVE_FILE = DATA_DIR / "live_matches.csv"

# =========================
# LOAD CSV
# =========================

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

# =========================
# REAL LIVE DATA
# =========================

if live_df.empty:

    try:

        API_KEY = st.secrets["API_FOOTBALL_KEY"]

        URL = "https://v3.football.api-sports.io/fixtures?live=all"

        HEADERS = {

            "x-rapidapi-key": API_KEY,
            "x-rapidapi-host": "v3.football.api-sports.io"

        }

        response = requests.get(
            URL,
            headers=HEADERS,
            timeout=30
        )

        data = response.json()

        rows = []

        for item in data["response"]:

            rows.append({

                "home": item["teams"]["home"]["name"],
                "away": item["teams"]["away"]["name"],
                "league": item["league"]["name"],
                "minute": item["fixture"]["status"]["elapsed"],
                "score": f"{item['goals']['home']}-{item['goals']['away']}",
                "signal": random.choice([
                    "OVER 2.5",
                    "BTTS YES",
                    "HOME GOAL"
                ]),
                "confidence": random.randint(70, 95),
                "ev": round(random.uniform(3, 18), 2),
                "value": random.choice([
                    "LOW",
                    "MEDIUM",
                    "HIGH"
                ]),
                "cashout": random.choice([
                    "HOLD",
                    "PARTIAL",
                    "FULL"
                ]),
                "stake": random.choice([
                    "1%",
                    "2%",
                    "3%"
                ]),
                "risk": random.choice([
                    "LOW",
                    "MEDIUM",
                    "HIGH"
                ]),
                "status": "LIVE"

            })

        if rows:

            live_df = pd.DataFrame(rows)

            live_df.to_csv(
                LIVE_FILE,
                index=False
            )

    except Exception as e:

        print(e)

prematch_df = load_csv(PREMATCH_FILE)

# =========================
# STYLE
# =========================

st.markdown("""
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
    padding-top:1rem;
    padding-left:2rem;
    padding-right:2rem;
}

h1, h2, h3 {

    color:white !important;
    font-weight:900 !important;
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

.section-box {

    border:1px solid rgba(255,255,255,0.08);

    border-radius:18px;

    background:
        linear-gradient(
            180deg,
            rgba(255,255,255,0.045),
            rgba(255,255,255,0.018)
        );

    padding:24px;

    margin-bottom:24px;

    box-shadow:0 18px 45px rgba(0,0,0,0.35);
}

.live-card {

    padding:18px;
    border-radius:14px;
    margin-bottom:14px;
    font-weight:700;
}

.green {

    background:rgba(88,255,47,0.08);
    border:1px solid rgba(88,255,47,0.25);
    color:#58ff2f;
}

.yellow {

    background:rgba(255,210,26,0.08);
    border:1px solid rgba(255,210,26,0.25);
    color:#ffd21a;
}

.red {

    background:rgba(255,59,48,0.08);
    border:1px solid rgba(255,59,48,0.25);
    color:#ff3b30;
}

[data-testid="stTable"] {

    width:100%;
}

table {

    width:100% !important;
    border-collapse:collapse !important;
    background:#0d1014 !important;
    color:#f2f2f2 !important;
}

thead tr th {

    background:#11161c !important;
    color:#58ff2f !important;
    padding:14px !important;
    font-size:14px !important;
    border-bottom:1px solid rgba(255,255,255,0.08) !important;
}

tbody tr td {

    padding:14px !important;
    border-bottom:1px solid rgba(255,255,255,0.05) !important;
    font-size:13px !important;
}

tbody tr:hover {

    background:rgba(88,255,47,0.05) !important;
}

</style>
""", unsafe_allow_html=True)

# =========================
# BANNER
# =========================

banner = Path("kanibal_banner_pro.webp")

if banner.exists():

    st.image(
        str(banner),
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

    st.markdown('<div class="section-box">', unsafe_allow_html=True)

    st.title("LIVE SIGNALS")

    st.caption("AKTUALIZOWANE CO 60 SEKUND")

    st.markdown('</div>', unsafe_allow_html=True)

    if live_df.empty:

        st.warning("Brak danych LIVE")

    else:

        st.table(live_df)

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown('<div class="section-box">', unsafe_allow_html=True)

    st.title("CASHOUT AI GUIDE")

    st.markdown("""

    <div class="live-card green">
        HOLD POSITION — Wysoka presja i momentum. Trzymaj zakład.
    </div>

    <div class="live-card yellow">
        PARTIAL CASHOUT — Spadający confidence. Rozważ częściowe wyjście.
    </div>

    <div class="live-card red">
        FULL CASHOUT — Niski momentum i presja. Wyjdź z zakładu.
    </div>

    """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# PREMATCH
# =========================

with tab2:

    st.markdown('<div class="section-box">', unsafe_allow_html=True)

    st.title("PREMATCH PICKS")

    if prematch_df.empty:

        st.warning("Brak danych PREMATCH")

    else:

        columns = [

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

        existing = [c for c in columns if c in prematch_df.columns]

        st.table(
            prematch_df[existing]
        )

    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# ANALYTICS
# =========================

with tab3:

    st.markdown('<div class="section-box">', unsafe_allow_html=True)

    st.title("ANALYTICS ENGINE")

    st.metric("ROI", "+24.8%")

    st.metric("WIN RATE", "62.8%")

    st.metric("AI EDGE", "+13.4%")

    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# HISTORY
# =========================

with tab4:

    st.markdown('<div class="section-box">', unsafe_allow_html=True)

    st.title("HISTORY ENGINE")

    st.info("Historia zakładów będzie dostępna po wdrożeniu Settlement Engine.")

    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# RANKING
# =========================

with tab5:

    st.markdown('<div class="section-box">', unsafe_allow_html=True)

    st.title("RANKING ENGINE")

    st.info("TOP VALUE PICKS coming soon.")

    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# ALERTS
# =========================

with tab6:

    st.markdown('<div class="section-box">', unsafe_allow_html=True)

    st.title("ALERT ENGINE")

    st.info("Alerty AI będą dostępne po wdrożeniu Notification Engine.")

    st.markdown('</div>', unsafe_allow_html=True)
