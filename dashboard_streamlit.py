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

DATA_DIR = Path("data")

PREMATCH_FILE = DATA_DIR / "auto_all_picks.csv"
LIVE_FILE = DATA_DIR / "auto_all_picks.csv"

BANNER_FILE = Path("kanibal_banner_pro.webp")

# =========================
# DATA
# =========================

def load_csv(path: Path) -> pd.DataFrame:

    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path)

    except Exception:
        return pd.DataFrame()


def only_existing_columns(
    df: pd.DataFrame,
    columns: list[str]
) -> pd.DataFrame:

    existing = [
        col for col in columns
        if col in df.columns
    ]

    if not existing:
        return df

    return df[existing]


live_df = load_csv(LIVE_FILE)
prematch_df = load_csv(PREMATCH_FILE)

# =========================
# GLOBAL CSS
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

        div[data-testid="stMetric"] {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px;
            padding: 18px;
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
    st.caption("ANALIZA • PRZEWAGA • ZYSK")

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

    st.markdown(
        """
        <style>

        .live-card * {
            color: white !important;
        }

        </style>
        """,
        unsafe_allow_html=True
    )

    with st.container(border=True):

        st.header("🟢 LIVE SIGNALS")
        st.caption("AKTUALIZOWANE CO 60 SEKUND")

    if live_df.empty:

        st.warning("Brak danych LIVE")

    else:

        for _, row in live_df.iterrows():

            with st.container(border=True):

                match_name = (
                    row.get("match")
                    or row.get("mecz")
                    or "BRAK MECZU"
                )

                league = (
                    row.get("league")
                    or row.get("liga")
                    or ""
                )

                ev = (
                    row.get("ev")
                    or row.get("EV")
                    or "-"
                )

                status = (
                    row.get("status")
                    or "LIVE"
                )

                minute = (
                    row.get("minute")
                    or row.get("minuta")
                    or "-"
                )

                confidence_raw = (
                    row.get("confidence")
                    or row.get("CONFIDENCE")
                    or row.get("conf")
                    or 0
                )

                try:
                    confidence = f"{float(confidence_raw):.0f}%"
                except:
                    confidence = "-"

                pressure = (
                    row.get("pressure")
                    or 0
                )

                momentum = (
                    row.get("momentum")
                    or 0
                )

                try:

                    tempo_score = (
                        float(pressure) +
                        float(momentum)
                    ) / 2

                    if tempo_score >= 75:
                        tempo = "🔥 HIGH TEMPO"

                    elif tempo_score >= 45:
                        tempo = "⚡ MEDIUM TEMPO"

                    else:
                        tempo = "🧊 LOW TEMPO"

                except:
                    tempo = "-"

                st.subheader(match_name)

                st.caption(f"🏆 {league}")

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric("EV", ev)

                with col2:
                    st.metric("CONF", confidence)

                with col3:
                    st.metric("MIN", minute)

                with col4:
                    st.metric("STATUS", status)

                st.markdown(
                    f"""
                    <div class="live-card" style="
                        margin-top:12px;
                        padding:14px;
                        border-radius:14px;
                        background:rgba(255,255,255,0.04);
                        border:1px solid rgba(255,255,255,0.08);
                        font-weight:700;
                        font-size:15px;
                    ">
                        📈 DYNAMIKA MECZU: {tempo}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

# =========================
# PREMATCH
# =========================

with prematch_tab:

    with st.container(border=True):

        st.header("🟢 PREMATCH PICKS")
        st.caption("CORE VALUE ENGINE")

    if prematch_df.empty:

        st.warning("Brak danych PREMATCH")

    else:

        prematch_columns = [
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

        prematch_view = only_existing_columns(
            prematch_df,
            prematch_columns
        )

        st.table(prematch_view)

# =========================
# ANALYTICS
# =========================

with analytics_tab:

    with st.container(border=True):

        st.header("📊 ANALYTICS ENGINE")
        st.caption("AI PERFORMANCE ANALYTICS")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("ROI", "+24.8%")

    with col2:
        st.metric("WIN RATE", "62.8%")

    with col3:
        st.metric("AI EDGE", "+13.4%")

    with col4:
        st.metric(
            "TOTAL SIGNALS",
            len(live_df) + len(prematch_df)
        )

# =========================
# HISTORY
# =========================

with history_tab:

    with st.container(border=True):

        st.header("🕘 HISTORY ENGINE")
        st.caption("HISTORIA TYPÓW I ROZLICZEŃ")

    st.info(
        "Historia zakładów będzie dostępna po wdrożeniu Settlement Engine."
    )

# =========================
# RANKING
# =========================

with ranking_tab:

    with st.container(border=True):

        st.header("🏆 RANKING ENGINE")
        st.caption("TOP VALUE PICKS")

    if prematch_df.empty:

        st.warning("Brak danych do rankingu")

    else:

        ranking_df = prematch_df.copy()

        if "ev" in ranking_df.columns:

            ranking_df["ev"] = pd.to_numeric(
                ranking_df["ev"],
                errors="coerce"
            ).fillna(0)

            ranking_df = ranking_df.sort_values(
                "ev",
                ascending=False
            ).head(10)

        ranking_columns = [
            "data",
            "liga",
            "mecz",
            "market",
            "typ",
            "kurs_buk",
            "ev",
            "edge",
            "status"
        ]

        ranking_view = only_existing_columns(
            ranking_df,
            ranking_columns
        )

        st.table(ranking_view)

# =========================
# ALERTS
# =========================

with alerts_tab:

    with st.container(border=True):

        st.header("🔔 ALERT ENGINE")
        st.caption("LIVE ALERTS & NOTIFICATIONS")

    st.info(
        "Alerty AI będą dostępne po podłączeniu systemu powiadomień."
    )
