
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
BANNER_FILE = BASE_DIR / "kanibal_banner_pro.webp"

def load_csv():
    if not CSV_FILE.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(CSV_FILE)
    except Exception:
        try:
            return pd.read_csv(CSV_FILE, encoding="utf-8")
        except Exception:
            return pd.DataFrame()

df = load_csv()

def only_existing_columns(dataframe, columns):
    existing = [c for c in columns if c in dataframe.columns]
    if not existing:
        return dataframe
    return dataframe[existing]

st.markdown(
    '''
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
        padding-left: 2rem;
        padding-right: 2rem;
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

        margin-bottom: 18px;
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

    .ai-box {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(88,255,47,0.15);
        border-radius: 12px;
        padding: 12px;
        margin-bottom: 10px;
    }

    </style>
    ''',
    unsafe_allow_html=True
)

if BANNER_FILE.exists():
    st.image(str(BANNER_FILE), use_container_width=True)
else:
    st.title("KANIBAL ANALYTICS")

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

with live_tab:
    st.header("🟢 LIVE SIGNALS")
    st.info("LIVE ENGINE ACTIVE")

with prematch_tab:

    st.header("🟢 PREMATCH PICKS")

    if df.empty:
        st.warning("Brak danych PREMATCH")

    else:

        compact_columns = [
            "liga",
            "mecz",
            "market",
            "typ",
            "kurs_buk",
            "confidence",
            "ev",
            "edge",
            "risk"
        ]

        compact_view = only_existing_columns(df, compact_columns)

        st.table(compact_view)

        st.markdown("## 🔍 AI DETAILS")

        for idx, row in df.iterrows():

            match_name = row.get("mecz", row.get("match", "BRAK MECZU"))

            with st.expander(f"📊 {match_name}"):

                c1, c2, c3 = st.columns(3)

                with c1:
                    st.markdown(
                        f'''
                        <div class="ai-box">
                        <h4 style="color:#58ff2f;">MODEL AI</h4>
                        <b>CONFIDENCE:</b> {row.get("confidence", "-")}<br>
                        <b>MODEL PROB:</b> {row.get("prawd_model", "-")}<br>
                        <b>FINAL PROB:</b> {row.get("prawd_final", "-")}<br>
                        <b>STAGE A PROB:</b> {row.get("stage_a_probability", "-")}<br>
                        </div>
                        ''',
                        unsafe_allow_html=True
                    )

                with c2:
                    st.markdown(
                        f'''
                        <div class="ai-box">
                        <h4 style="color:#58ff2f;">VALUE</h4>
                        <b>EV:</b> {row.get("ev", "-")}<br>
                        <b>EDGE:</b> {row.get("edge", "-")}<br>
                        <b>KELLY:</b> {row.get("kelly_25", "-")}<br>
                        <b>RISK:</b> {row.get("risk", "-")}<br>
                        </div>
                        ''',
                        unsafe_allow_html=True
                    )

                with c3:
                    st.markdown(
                        f'''
                        <div class="ai-box">
                        <h4 style="color:#58ff2f;">MARKET</h4>
                        <b>BOOK ODDS:</b> {row.get("kurs_buk", "-")}<br>
                        <b>MODEL ODDS:</b> {row.get("kurs_model", "-")}<br>
                        <b>BOT ODDS:</b> {row.get("kurs_bota", "-")}<br>
                        <b>SHARP:</b> {row.get("sharp_label", "-")}<br>
                        </div>
                        ''',
                        unsafe_allow_html=True
                    )

                c4, c5 = st.columns(2)

                with c4:
                    st.markdown(
                        f'''
                        <div class="ai-box">
                        <h4 style="color:#58ff2f;">xG ENGINE</h4>
                        <b>HOME xG:</b> {row.get("home_xg", "-")}<br>
                        <b>AWAY xG:</b> {row.get("away_xg", "-")}<br>
                        <b>MARGIN:</b> {row.get("marza_%", "-")}<br>
                        </div>
                        ''',
                        unsafe_allow_html=True
                    )

                with c5:
                    st.markdown(
                        f'''
                        <div class="ai-box">
                        <h4 style="color:#58ff2f;">SHARP MONEY</h4>
                        <b>SCORE:</b> {row.get("sharp_score", "-")}<br>
                        <b>LABEL:</b> {row.get("sharp_label", "-")}<br>
                        <b>SIGNALS:</b> {row.get("sharp_signals", "-")}<br>
                        </div>
                        ''',
                        unsafe_allow_html=True
                    )

with analytics_tab:
    st.header("📊 ANALYTICS")

with history_tab:
    st.header("🕘 HISTORY")

with ranking_tab:
    st.header("🏆 RANKING")

with alerts_tab:
    st.header("🔔 ALERTS")
