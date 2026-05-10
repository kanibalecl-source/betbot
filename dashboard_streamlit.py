
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

# =========================
# DISPLAY FILTER: ODDS 1.00–2.50
# =========================
if not df.empty and "kurs_buk" in df.columns:
    df["_kurs_buk_num"] = pd.to_numeric(df["kurs_buk"], errors="coerce")
    df = df[(df["_kurs_buk_num"] >= 1.00) & (df["_kurs_buk_num"] <= 2.50)].copy()

# =========================
# BEST PICK FALLBACK SCORE
# =========================
if not df.empty:
    if "ai_pick_score" not in df.columns:
        def _num(row, key, default=0):
            try:
                return float(row.get(key, default))
            except Exception:
                return default

        def _score(row):
            confidence = _num(row, "confidence")
            calibrated = _num(row, "confidence_calibrated_v2", confidence)
            ev = _num(row, "ev_percent", _num(row, "ev"))
            edge = _num(row, "edge") * 100
            meta = _num(row, "meta_probability")
            sharp = _num(row, "sharp_score")
            momentum = _num(row, "momentum_score")
            return round(
                confidence * 0.25
                + calibrated * 0.20
                + ev * 0.20
                + edge * 0.15
                + meta * 0.10
                + sharp * 0.05
                + momentum * 0.05,
                2
            )

        df["ai_pick_score"] = df.apply(_score, axis=1)

    if "best_pick_label" not in df.columns:
        df["best_pick_label"] = df.apply(
            lambda row: "BEST PICK" if float(row.get("ai_pick_score", 0) or 0) >= 70 else "STANDARD",
            axis=1
        )


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
        margin-bottom: 12px;
    }

    
    .best-pick-box {
        background: linear-gradient(90deg, rgba(88,255,47,0.20), rgba(88,255,47,0.05));
        border: 1px solid rgba(88,255,47,0.55);
        border-radius: 14px;
        padding: 12px 14px;
        margin-bottom: 12px;
        box-shadow: 0 0 24px rgba(88,255,47,0.10);
    }

    .best-pick-title {
        color: #58ff2f;
        font-weight: 900;
        font-size: 18px;
    }


    </style>
    ''',
    unsafe_allow_html=True
)

if BANNER_FILE.exists():
    st.image(str(BANNER_FILE), use_container_width=True)
else:
    st.title("KANIBAL ANALYTICS")

tabs = st.tabs([
    "🚨 LIVE",
    "⚽ PREMATCH",
    "📊 ANALYTICS",
    "🕘 HISTORY",
    "🏆 RANKING",
    "🔔 ALERTS"
])

live_tab, prematch_tab, analytics_tab, history_tab, ranking_tab, alerts_tab = tabs

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
            "risk",
            "ai_pick_score",
            "best_pick_label"
        ]

        compact_view = only_existing_columns(df, compact_columns)

        st.table(compact_view)

        st.markdown("## 🔍 AI DETAILS")

        for idx, row in df.iterrows():

            match_name = row.get("mecz", row.get("match", "BRAK MECZU"))

            with st.expander(f"📊 {match_name}"):

                if str(row.get("best_pick_label", "")).upper() == "BEST PICK":
                    st.markdown(
                        f"""
                        <div class="best-pick-box">
                            <div class="best-pick-title">✅ BEST PICK</div>
                            <div>AI SCORE: {row.get("ai_pick_score", "-")} | Kurs: {row.get("kurs_buk", "-")} | EV: {row.get("ev", "-")} | Confidence: {row.get("confidence", "-")}</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

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

                c4, c5 = st.columns(2)

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

with analytics_tab:
    st.header("📊 ANALYTICS")

with history_tab:
    st.header("🕘 HISTORY")

with ranking_tab:
    st.header("🏆 RANKING")

with alerts_tab:
    st.header("🔔 ALERTS")


# META AI ENGINE ENABLED
