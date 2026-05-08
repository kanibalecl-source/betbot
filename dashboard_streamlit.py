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
        background:linear-gradient(180deg, rgba(88,255,47,0.15), rgba(88,255,47,0.05)) !important;
        color:#58ff2f !important;
        border-bottom:3px solid #58ff2f !important;
    }

    .panel {
        border:1px solid rgba(255,255,255,0.08);
        border-radius:18px;
        background:linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.018));
        padding:26px;
        margin-bottom:22px;
        box-shadow:0 18px 45px rgba(0,0,0,0.35);
    }

    .live-grid {
        display:grid;
        grid-template-columns:repeat(auto-fit, minmax(340px, 1fr));
        gap:18px;
    }

    .live-card {
        border:1px solid rgba(88,255,47,0.18);
        border-radius:18px;
        padding:20px;
        background:linear-gradient(180deg, rgba(255,255,255,0.055), rgba(255,255,255,0.02));
        box-shadow:0 14px 40px rgba(0,0,0,0.35);
    }

    .league {
        color:#8f969d;
        font-size:12px;
        text-transform:uppercase;
        letter-spacing:1px;
        margin-bottom:10px;
    }

    .match {
        font-size:22px;
        font-weight:900;
        color:white;
        margin-bottom:12px;
    }

    .minute {
        color:#58ff2f;
        font-size:26px;
        font-weight:900;
    }

    .score {
        font-size:26px;
        font-weight:900;
        color:white;
    }

    .badge {
        display:inline-block;
        padding:7px 12px;
        border-radius:10px;
        font-weight:900;
        font-size:12px;
        margin-top:10px;
        margin-right:8px;
    }

    .green {
        color:#58ff2f;
        background:rgba(88,255,47,0.10);
        border:1px solid rgba(88,255,47,0.35);
    }

    .yellow {
        color:#ffd21a;
        background:rgba(255,210,26,0.10);
        border:1px solid rgba(255,210,26,0.35);
    }

    .red {
        color:#ff3b30;
        background:rgba(255,59,48,0.10);
        border:1px solid rgba(255,59,48,0.35);
    }

    .gray {
        color:#cfd4d8;
        background:rgba(255,255,255,0.06);
        border:1px solid rgba(255,255,255,0.12);
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
    </style>
    """,
    unsafe_allow_html=True
)

if BANNER_FILE.exists():
    st.image(str(BANNER_FILE), use_container_width=True)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🚨 LIVE",
    "⚽ PREMATCH",
    "📊 ANALYTICS",
    "🕘 HISTORY",
    "🏆 RANKING",
    "🔔 ALERTS"
])

with tab1:
    st.markdown(
        """
        <div class="panel">
            <h2>LIVE SIGNALS</h2>
            <div style="color:#8f969d;font-size:12px;letter-spacing:1px;text-transform:uppercase;">
                AKTUALIZOWANE CO 60 SEKUND
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if not live_df.empty:
        cards = ""

        for _, row in live_df.iterrows():
            home = row.get("home", "-")
            away = row.get("away", "-")
            league = row.get("league", "-")
            minute = row.get("minute", "-")
            score = row.get("score", "-")
            signal = row.get("signal", "NO SIGNAL")
            confidence = row.get("confidence", 0)
            ev = row.get("ev", "-")
            value = row.get("value", "-")
            cashout = row.get("cashout", "NO CASHOUT")
            risk = row.get("risk", "-")
            stake = row.get("stake", "-")

            signal_class = "green" if "OVER" in str(signal).upper() else "yellow" if "BTTS" in str(signal).upper() else "gray"
            cashout_class = "green" if "HOLD" in str(cashout).upper() else "yellow" if "PARTIAL" in str(cashout).upper() else "red" if "FULL" in str(cashout).upper() else "gray"

            cards += f"""
            <div class="live-card">
                <div class="league">{league}</div>
                <div class="match">{home}<br><span style="color:#9aa0a6;">vs {away}</span></div>

                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                    <div class="minute">{minute}'</div>
                    <div class="score">{score}</div>
                </div>

                <span class="badge {signal_class}">{signal}</span>
                <span class="badge green">CONF {confidence}%</span>
                <span class="badge yellow">VALUE {value}</span>
                <span class="badge green">EV {ev}</span>
                <span class="badge {cashout_class}">{cashout}</span>
                <span class="badge gray">STAKE {stake}</span>
                <span class="badge gray">{risk}</span>
            </div>
            """

        st.markdown(f'<div class="live-grid">{cards}</div>', unsafe_allow_html=True)

    else:
        st.warning("Brak danych LIVE")

    st.markdown(
        """
        <div class="panel">
            <h2>CASHOUT AI GUIDE</h2>

            <div class="badge green">HOLD POSITION</div>
            <p style="color:#cfd4d8;">Wysoka presja i momentum. Trzymaj zakład.</p>

            <div class="badge yellow">PARTIAL CASHOUT</div>
            <p style="color:#cfd4d8;">Spadający confidence. Rozważ częściowe wyjście.</p>

            <div class="badge red">FULL CASHOUT</div>
            <p style="color:#cfd4d8;">Niski momentum i presja. Wyjdź z zakładu.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

with tab2:
    st.markdown(
        """
        <div class="panel">
            <h2>PREMATCH PICKS</h2>
            <div style="color:#8f969d;font-size:12px;letter-spacing:1px;text-transform:uppercase;">
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

        existing_columns = [col for col in wanted_columns if col in prematch_df.columns]
        prematch_df = prematch_df[existing_columns]

        st.markdown(
            prematch_df.to_html(index=False, classes="custom-table"),
            unsafe_allow_html=True
        )
    else:
        st.warning("Brak danych PREMATCH")

with tab3:
    st.markdown('<div class="panel"><h2>ANALYTICS ENGINE</h2></div>', unsafe_allow_html=True)

with tab4:
    st.markdown('<div class="panel"><h2>HISTORY ENGINE</h2></div>', unsafe_allow_html=True)

with tab5:
    st.markdown('<div class="panel"><h2>RANKING ENGINE</h2></div>', unsafe_allow_html=True)

with tab6:
    st.markdown('<div class="panel"><h2>ALERT ENGINE</h2></div>', unsafe_allow_html=True)
