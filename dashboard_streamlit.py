import streamlit as st
import pandas as pd
from pathlib import Path

# =====================================
# CONFIG
# =====================================

st.set_page_config(
    page_title="KANIBAL ANALYTICS",
    layout="wide",
    initial_sidebar_state="collapsed"
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

CSV_FILE = DATA_DIR / "auto_all_picks.csv"

BANNER_FILE = BASE_DIR / "kanibal_banner_pro.webp"

# =====================================
# LOAD CSV
# =====================================

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

# =====================================
# HELPERS
# =====================================

def val(row, cols, default="-"):

    for c in cols:

        if c in row:

            v = row.get(c)

            try:
                if pd.isna(v):
                    continue
            except:
                pass

            v = str(v).strip()

            if v != "" and v.lower() not in ["nan", "none", "null"]:
                return v

    return default


def confidence_format(v):

    try:

        v = float(v)

        if v <= 1:
            v *= 100

        return f"{v:.0f}%"

    except:
        return "-"


def only_existing_columns(
    dataframe,
    columns
):

    existing = [
        c for c in columns
        if c in dataframe.columns
    ]

    if not existing:
        return dataframe

    return dataframe[existing]

# =====================================
# CSS
# =====================================

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

    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px;
        padding: 18px;
    }

    div[data-testid="stMetricLabel"] {
        color: #ffffff !important;
    }

    div[data-testid="stMetricValue"] {
        color: #ffffff !important;
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

# =====================================
# HEADER
# =====================================

if BANNER_FILE.exists():

    st.image(
        str(BANNER_FILE),
        use_container_width=True
    )

else:

    st.title("KANIBAL ANALYTICS")

# =====================================
# TABS
# =====================================

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

# =====================================
# LIVE
# =====================================

with live_tab:

    st.header("🟢 LIVE SIGNALS")
    st.caption("AKTUALIZOWANE CO 60 SEKUND")

    if df.empty:

        st.warning("Brak danych LIVE")

    else:

        for _, row in df.iterrows():

            home = val(
                row,
                ["home", "home_team"],
                ""
            )

            away = val(
                row,
                ["away", "away_team"],
                ""
            )

            if home != "" or away != "":

                match_name = f"{home} vs {away}"

            else:

                match_name = val(
                    row,
                    ["match", "mecz"],
                    "BRAK MECZU"
                )

            league = val(
                row,
                ["league", "liga"]
            )

            signal = val(
                row,
                ["signal", "typ", "market"],
                "BRAK TYPU"
            )

            score = val(
                row,
                ["score"],
                "-"
            )

            minute_raw = val(
                row,
                [
                    "minute",
                    "min",
                    "elapsed",
                    "time"
                ],
                ""
            )

            if minute_raw != "":
                minute = f"{minute_raw}'"
            else:
                minute = "LIVE"

            confidence = confidence_format(
                val(
                    row,
                    [
                        "confidence",
                        "conf",
                        "prawd_final",
                        "value"
                    ],
                    0
                )
            )

            ev = val(
                row,
                ["ev"],
                "-"
            )

            status = val(
                row,
                ["status"],
                "LIVE"
            )

            risk = val(
                row,
                ["risk"],
                "LOW"
            ).upper()

            if risk in ["HIGH", "TOP"]:
                tempo = "🔥 HIGH TEMPO"

            elif risk == "MEDIUM":
                tempo = "⚡ MEDIUM TEMPO"

            else:
                tempo = "🧊 LOW TEMPO"

            with st.container(border=True):

                st.subheader(match_name)

                st.caption(f"🏆 {league}")

                st.markdown(f"### ⚽ WYNIK: {score}")

                st.markdown(
                    f"""
                    <div style="
                        color:#58ff2f;
                        font-size:22px;
                        font-weight:900;
                        margin-bottom:14px;
                    ">
                        🎯 TYP: {signal}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                c1, c2, c3, c4 = st.columns(4)

                with c1:
                    st.metric("EV", ev)

                with c2:
                    st.metric("CONF", confidence)

                with c3:
                    st.metric("MIN", minute)

                with c4:
                    st.metric("STATUS", status)

                st.info(
                    f"📈 DYNAMIKA MECZU: {tempo}"
                )

# =====================================
# PREMATCH
# =====================================

with prematch_tab:

    st.header("🟢 PREMATCH PICKS")

    if df.empty:

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
            df,
            prematch_columns
        )

        st.table(prematch_view)

# =====================================
# ANALYTICS
# =====================================

with analytics_tab:

    st.header("📊 ANALYTICS")

    st.metric(
        "TOTAL SIGNALS",
        len(df)
    )

# =====================================
# HISTORY
# =====================================

with history_tab:

    st.info("Historia będzie dostępna później.")

# =====================================
# RANKING
# =====================================

with ranking_tab:

    st.info("Ranking będzie dostępny później.")

# =====================================
# ALERTS
# =====================================

with alerts_tab:

    st.info("Alerty będą dostępne później.")
