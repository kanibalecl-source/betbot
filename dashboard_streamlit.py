
import streamlit as st
import pandas as pd
from pathlib import Path
import base64

from auth_manager import require_login
from advanced_learning_engine import AdvancedLearningEngine

st.set_page_config(
    page_title="KANIBAL ANALYTICS",
    layout="wide",
    initial_sidebar_state="collapsed"
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

CSV_FILE = DATA_DIR / "auto_all_picks.csv"
BANNER_FILE = BASE_DIR / "kanibal_banner_pro.webp"


def image_to_base64(path: Path) -> str:
    try:
        return base64.b64encode(path.read_bytes()).decode("utf-8")
    except Exception:
        return ""


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


def only_existing_columns(dataframe, columns):
    existing = [c for c in columns if c in dataframe.columns]
    if not existing:
        return dataframe
    return dataframe[existing]


def normalize_label(value):
    return str(value if value is not None else "STANDARD").upper().strip()


def show_pick_badge(row):
    label = normalize_label(row.get("best_pick_label", "STANDARD"))
    score = row.get("ai_pick_score", "-")
    odds = row.get("kurs_buk", "-")
    ev = row.get("ev", "-")
    confidence = row.get("confidence", "-")

    text = f"{label} | AI SCORE: {score} | ODDS: {odds} | EV: {ev} | CONF: {confidence}"

    if label == "ULTRA ELITE":
        st.markdown(f"### 🟣 {text}")

    elif label == "TOP PICK":
        st.success(f"🟢 {text}")

    elif label == "BEST PICK":
        st.success(f"🟩 {text}")

    elif label == "VALUE PICK":
        st.warning(f"🟨 {text}")

    else:
        st.caption(f"⚪ {text}")


require_login()

df = load_csv()

TARGET_MARKETS = {
    "DOUBLE_1X",
    "DOUBLE_X2",
    "DOUBLE_12",
    "BTTS_YES",
    "BTTS_NO",
    "OVER_0.5",
    "OVER_1.5",
    "OVER_2.5",
    "OVER_3.5",
    "OVER_4.5",
    "UNDER_0.5",
    "UNDER_1.5",
    "UNDER_2.5",
    "UNDER_3.5",
    "UNDER_4.5",
}

if not df.empty and "market" in df.columns:
    df = df[df["market"].astype(str).isin(TARGET_MARKETS)].copy()

if not df.empty and "kurs_buk" in df.columns:
    df["_kurs_buk_num"] = pd.to_numeric(df["kurs_buk"], errors="coerce")
    df = df[(df["_kurs_buk_num"] >= 1.00) & (df["_kurs_buk_num"] <= 2.50)].copy()

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
        margin-bottom: 12px;
    }



    .kanibal-hero-banner {
        width: 100%;
        margin: 0 0 22px 0;
        padding: 0;
        border-radius: 22px;
        overflow: hidden;
        border: 1px solid rgba(88,255,47,0.18);
        box-shadow: 0 0 38px rgba(88,255,47,0.10), inset 0 0 30px rgba(0,0,0,0.25);
        background: linear-gradient(90deg, rgba(5,8,10,0.9), rgba(10,45,18,0.45), rgba(5,8,10,0.9));
    }

    .kanibal-hero-banner img {
        display: block;
        width: 100%;
        height: clamp(130px, 16vw, 245px);
        object-fit: cover;
        object-position: center;
    }

    div[data-testid="stTable"] {
        border-radius: 16px !important;
        overflow: hidden !important;
        border: 1px solid rgba(88,255,47,0.14) !important;
        box-shadow: 0 12px 35px rgba(0,0,0,0.28) !important;
        background: rgba(7,11,14,0.96) !important;
    }

    div[data-testid="stTable"] table {
        background: rgba(7,11,14,0.96) !important;
        color: #f2f6f2 !important;
    }

    div[data-testid="stTable"] th {
        background: linear-gradient(180deg, rgba(88,255,47,0.12), rgba(88,255,47,0.045)) !important;
        color: #7cff5b !important;
        font-weight: 900 !important;
        letter-spacing: 0.02em !important;
    }

    div[data-testid="stTable"] td {
        background: rgba(8,12,16,0.94) !important;
        color: #eef5ee !important;
    }

    div[data-testid="stDataFrame"] {
        border-radius: 16px !important;
        overflow: hidden !important;
        border: 1px solid rgba(88,255,47,0.14) !important;
        box-shadow: 0 12px 35px rgba(0,0,0,0.28) !important;
        background: rgba(7,11,14,0.96) !important;
    }

    </style>
    ''',
    unsafe_allow_html=True
)

if BANNER_FILE.exists():
    banner_b64 = image_to_base64(BANNER_FILE)
    st.markdown(
        f"""
        <div class="kanibal-hero-banner">
            <img src="data:image/webp;base64,{banner_b64}" alt="KANIBAL ANALYTICS">
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.title("KANIBAL ANALYTICS")

tabs = st.tabs([
    "🚨 LIVE",
    "⚽ PREMATCH",
    "🧠 AI",
    "📊 ANALYTICS",
    "🕘 HISTORY",
    "🏆 RANKING",
    "🔔 ALERTS"
])

live_tab, prematch_tab, ai_tab, analytics_tab, history_tab, ranking_tab, alerts_tab = tabs

with live_tab:
    st.header("🟢 LIVE SIGNALS")
    st.info("LIVE ENGINE ACTIVE")

    learning_engine = AdvancedLearningEngine()
    live_df = learning_engine.live_tempo_snapshot()
    if live_df.empty:
        st.warning("Brak zapisanych danych LIVE w data/live_matches.csv")
    else:
        st.subheader("Mecze LIVE i tempo")
        st.dataframe(live_df, use_container_width=True)

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
            "risk",
            "best_pick_label",
            "ai_pick_score",
        ]

        compact_view = only_existing_columns(df, compact_columns)
        st.table(compact_view)

with ai_tab:

    st.header("🧠 AI DETAILS")

    if df.empty:
        st.warning("Brak danych AI")
    else:
        for idx, row in df.iterrows():

            match_name = row.get("mecz", row.get("match", "BRAK MECZU"))
            market_name = row.get("typ", row.get("market", ""))

            with st.expander(f"📊 {match_name} | {market_name}"):

                show_pick_badge(row)

                c1, c2, c3 = st.columns(3)

                with c1:
                    st.markdown(
                        f'''
                        <div class="ai-box">
                        <h4 style="color:#58ff2f;">MODEL AI</h4>
                        <b>CONFIDENCE:</b> {row.get("confidence", "-")}<br>
                        <b>CALIBRATED:</b> {row.get("confidence_calibrated_v2", "-")}<br>
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
                        <h4 style="color:#58ff2f;">VALUE ENGINE</h4>
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
                        <h4 style="color:#58ff2f;">MARKET ENGINE</h4>
                        <b>BOOK ODDS:</b> {row.get("kurs_buk", "-")}<br>
                        <b>MODEL ODDS:</b> {row.get("kurs_model", "-")}<br>
                        <b>BOT ODDS:</b> {row.get("kurs_bota", "-")}<br>
                        <b>SHARP:</b> {row.get("sharp_label", "-")}<br>
                        </div>
                        ''',
                        unsafe_allow_html=True
                    )

                c4, c5, c6 = st.columns(3)

                with c4:
                    st.markdown(
                        f'''
                        <div class="ai-box">
                        <h4 style="color:#58ff2f;">xG ENGINE</h4>
                        <b>HOME xG:</b> {row.get("home_xg", "-")}<br>
                        <b>AWAY xG:</b> {row.get("away_xg", "-")}<br>
                        <b>ADV TOTAL xG:</b> {row.get("advanced_total_xg", "-")}<br>
                        <b>ADV OVER2.5:</b> {row.get("advanced_over25_prob", "-")}<br>
                        <b>MARGIN:</b> {row.get("marza_%", "-")}<br>
                        </div>
                        ''',
                        unsafe_allow_html=True
                    )

                with c5:
                    st.markdown(
                        f'''
                        <div class="ai-box">
                        <h4 style="color:#58ff2f;">MOMENTUM ENGINE</h4>
                        <b>MOMENTUM SCORE:</b> {row.get("momentum_score", "-")}<br>
                        <b>MOMENTUM LABEL:</b> {row.get("momentum_label", "-")}<br>
                        <b>SHARP SCORE:</b> {row.get("sharp_score", "-")}<br>
                        <b>SHARP SIGNALS:</b> {row.get("sharp_signals", "-")}<br>
                        </div>
                        ''',
                        unsafe_allow_html=True
                    )

                with c6:
                    st.markdown(
                        f'''
                        <div class="ai-box">
                        <h4 style="color:#58ff2f;">META AI ENGINE</h4>
                        <b>META PROB:</b> {row.get("meta_probability", "-")}<br>
                        <b>MODEL WEIGHT:</b> {row.get("meta_weight_model", "-")}<br>
                        <b>MARKET WEIGHT:</b> {row.get("meta_weight_market", "-")}<br>
                        <b>xG WEIGHT:</b> {row.get("meta_weight_xg", "-")}<br>
                        <b>MOMENTUM WEIGHT:</b> {row.get("meta_weight_momentum", "-")}<br>
                        <b>SHARP WEIGHT:</b> {row.get("meta_weight_sharp", "-")}<br>
                        <b>DYNAMIC STAKE:</b> {row.get("dynamic_stake", "-")}<br>
                        </div>
                        ''',
                        unsafe_allow_html=True
                    )

with analytics_tab:
    st.header("📊 ANALYTICS")

    if df.empty:
        st.warning("Brak danych")
    else:
        c1, c2, c3 = st.columns(3)

        with c1:
            st.metric("TOTAL PICKS", len(df))

        with c2:
            if "ai_pick_score" in df.columns:
                st.metric(
                    "AVG AI SCORE",
                    round(pd.to_numeric(df["ai_pick_score"], errors="coerce").mean(), 2)
                )

        with c3:
            if "best_pick_label" in df.columns:
                strong_count = len(
                    df[
                        df["best_pick_label"].astype(str).str.upper().isin(
                            ["ULTRA ELITE", "TOP PICK", "BEST PICK"]
                        )
                    ]
                )
                st.metric("STRONG PICKS", strong_count)

        st.markdown("---")
        st.subheader("🧠 Learning Analytics")
        learning_engine = AdvancedLearningEngine()
        summary = learning_engine.performance_summary()
        l1, l2, l3, l4 = st.columns(4)
        l1.metric("Learning Bets", summary.get("bets", 0))
        l2.metric("Winrate", f"{summary.get('winrate_pct', 0)}%")
        l3.metric("ROI", f"{summary.get('roi_pct', 0)}%")
        l4.metric("Profit", summary.get("profit", 0))

        insights = learning_engine.learning_insights()
        if insights:
            st.subheader("Wnioski systemu")
            for insight in insights:
                st.info(insight)

        curve = learning_engine.profit_curve()
        if not curve.empty:
            st.subheader("Profit curve")
            st.line_chart(curve.set_index(curve.columns[0]))

        conf = learning_engine.confidence_accuracy()
        if not conf.empty:
            st.subheader("Confidence accuracy")
            st.dataframe(conf, use_container_width=True)

        market_perf = learning_engine.group_performance("market")
        if not market_perf.empty:
            st.subheader("Market performance")
            st.dataframe(market_perf, use_container_width=True)

        league_col = "league" if "league" in learning_engine.load_results().columns else "liga"
        league_perf = learning_engine.group_performance(league_col)
        if not league_perf.empty:
            st.subheader("League performance")
            st.dataframe(league_perf, use_container_width=True)

with history_tab:
    st.header("🕘 HISTORY")

with ranking_tab:
    st.header("🏆 RANKING")

with alerts_tab:
    st.header("🔔 ALERTS")
