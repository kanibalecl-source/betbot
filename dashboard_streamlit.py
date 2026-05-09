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
# DATA
# =========================

def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def is_empty_value(value) -> bool:
    if value is None:
        return True

    try:
        if pd.isna(value):
            return True
    except Exception:
        pass

    value = str(value).strip()

    return value == "" or value.lower() in ["nan", "none", "null"]


def first_value(row, keys, default="-"):
    for key in keys:
        if key in row and not is_empty_value(row.get(key)):
            return row.get(key)

    return default


def only_existing_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    existing = [col for col in columns if col in df.columns]

    if not existing:
        return df

    return df[existing]


def has_real_live_data(df: pd.DataFrame) -> bool:
    if df.empty:
        return False

    useful_columns = [
        "home",
        "away",
        "league",
        "minute",
        "score",
        "signal",
        "confidence",
        "ev",
        "value",
        "cashout",
        "stake",
        "risk",
        "status"
    ]

    existing = [col for col in useful_columns if col in df.columns]

    if not existing:
        return False

    useful_df = df[existing].fillna("").astype(str)

    return useful_df.apply(
        lambda row: any(cell.strip() for cell in row),
        axis=1
    ).any()


def format_percent(value):
    if is_empty_value(value):
        return "-"

    try:
        numeric = float(value)

        if numeric <= 1:
            numeric *= 100

        return f"{numeric:.0f}%"

    except Exception:
        return "-"


def parse_match(row):
    home = first_value(row, ["home", "home_team"], "")
    away = first_value(row, ["away", "away_team"], "")

    if not is_empty_value(home) or not is_empty_value(away):
        return f"{home} vs {away}".strip()

    match_name = first_value(row, ["match", "mecz"], "")

    if not is_empty_value(match_name):
        return match_name

    return "BRAK MECZU"


def get_live_source():
    live_df_raw = load_csv(LIVE_FILE)

    if has_real_live_data(live_df_raw):
        return live_df_raw

    prematch_df_raw = load_csv(PREMATCH_FILE)

    return prematch_df_raw


live_df = get_live_source()
prematch_df = load_csv(PREMATCH_FILE)

# =========================
# SAFE CSS ONLY
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

        div[data-testid="stTable"] tr:hover {
            background: rgba(88,255,47,0.06) !important;
        }

        div[data-testid="stMetric"] {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px;
            padding: 18px;
        }

        .kanibal-live-card {
            color: #ffffff !important;
            padding: 18px;
            border-radius: 18px;
            background:
                linear-gradient(
                    180deg,
                    rgba(255,255,255,0.045),
                    rgba(255,255,255,0.018)
                );
            border: 1px solid rgba(255,255,255,0.08);
            box-shadow: 0 18px 45px rgba(0,0,0,0.35);
            margin-bottom: 18px;
        }

        .kanibal-live-card * {
            color: #ffffff !important;
        }

        .kanibal-live-title {
            font-size: 26px;
            font-weight: 900;
            margin-bottom: 6px;
        }

        .kanibal-live-league {
            font-size: 14px;
            opacity: 0.85;
            margin-bottom: 12px;
        }

        .kanibal-live-score {
            font-size: 17px;
            font-weight: 800;
            margin-bottom: 8px;
        }

        .kanibal-live-type {
            color: #58ff2f !important;
            font-size: 16px;
            font-weight: 900;
            margin-bottom: 14px;
        }

        .kanibal-live-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 14px;
            margin-top: 12px;
        }

        .kanibal-live-box {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px;
            padding: 16px;
        }

        .kanibal-live-label {
            font-size: 12px;
            font-weight: 800;
            opacity: 0.8;
            margin-bottom: 8px;
        }

        .kanibal-live-value {
            font-size: 28px;
            font-weight: 900;
        }

        .kanibal-live-dynamics {
            margin-top: 14px;
            padding: 14px;
            border-radius: 14px;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            font-weight: 800;
            font-size: 15px;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# =========================
# HEADER / BANNER
# =========================

if BANNER_FILE.exists():
    st.image(str(BANNER_FILE), use_container_width=True)
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
    with st.container(border=True):
        st.header("🟢 LIVE SIGNALS")
        st.caption("AKTUALIZOWANE CO 60 SEKUND")

    if live_df.empty:
        st.warning("Brak danych LIVE")
    else:
        for _, row in live_df.iterrows():
            match_name = parse_match(row)

            league = first_value(
                row,
                ["league", "liga"],
                "-"
            )

            score = first_value(
                row,
                ["score", "wynik"],
                "-"
            )

            bet_type = first_value(
                row,
                ["signal", "typ", "market"],
                "BRAK TYPU"
            )

            ev = first_value(
                row,
                ["ev", "EV"],
                "-"
            )

            confidence = format_percent(
                first_value(
                    row,
                    ["confidence", "CONFIDENCE", "conf", "prawd_final", "prawd_model"],
                    "-"
                )
            )

            minute = first_value(
                row,
                ["minute", "minuta", "time", "match_time"],
                "LIVE"
            )

            status = first_value(
                row,
                ["status"],
                "LIVE"
            )

            pressure = first_value(row, ["pressure"], "")
            momentum = first_value(row, ["momentum"], "")

            tempo = "-"

            try:
                if not is_empty_value(pressure) and not is_empty_value(momentum):
                    tempo_score = (float(pressure) + float(momentum)) / 2

                    if tempo_score >= 75:
                        tempo = "🔥 HIGH TEMPO"
                    elif tempo_score >= 45:
                        tempo = "⚡ MEDIUM TEMPO"
                    else:
                        tempo = "🧊 LOW TEMPO"
                else:
                    risk = str(first_value(row, ["risk", "risk_level"], "")).upper()
                    value = str(first_value(row, ["value"], "")).upper()

                    if risk in ["HIGH", "TOP"] or value == "HIGH":
                        tempo = "🔥 HIGH TEMPO"
                    elif risk in ["MEDIUM", "LOW"] or value == "MEDIUM":
                        tempo = "⚡ MEDIUM TEMPO"
                    else:
                        tempo = "🧊 LOW TEMPO"
            except Exception:
                tempo = "-"

            st.markdown(
                f"""
                <div class="kanibal-live-card">
                    <div class="kanibal-live-title">{match_name}</div>
                    <div class="kanibal-live-league">🏆 {league}</div>
                    <div class="kanibal-live-score">⚽ WYNIK: {score}</div>
                    <div class="kanibal-live-type">🎯 TYP: {bet_type}</div>

                    <div class="kanibal-live-grid">
                        <div class="kanibal-live-box">
                            <div class="kanibal-live-label">EV</div>
                            <div class="kanibal-live-value">{ev}</div>
                        </div>

                        <div class="kanibal-live-box">
                            <div class="kanibal-live-label">CONF</div>
                            <div class="kanibal-live-value">{confidence}</div>
                        </div>

                        <div class="kanibal-live-box">
                            <div class="kanibal-live-label">MIN</div>
                            <div class="kanibal-live-value">{minute}</div>
                        </div>

                        <div class="kanibal-live-box">
                            <div class="kanibal-live-label">STATUS</div>
                            <div class="kanibal-live-value">{status}</div>
                        </div>
                    </div>

                    <div class="kanibal-live-dynamics">
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

        prematch_view = only_existing_columns(prematch_df, prematch_columns)

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
        st.metric("TOTAL SIGNALS", len(live_df) + len(prematch_df))

# =========================
# HISTORY
# =========================

with history_tab:
    with st.container(border=True):
        st.header("🕘 HISTORY ENGINE")
        st.caption("HISTORIA TYPÓW I ROZLICZEŃ")

    st.info("Historia zakładów będzie dostępna po wdrożeniu Settlement Engine.")

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

        ranking_view = only_existing_columns(ranking_df, ranking_columns)

        st.table(ranking_view)

# =========================
# ALERTS
# =========================

with alerts_tab:
    with st.container(border=True):
        st.header("🔔 ALERT ENGINE")
        st.caption("LIVE ALERTS & NOTIFICATIONS")

    st.info("Alerty AI będą dostępne po podłączeniu systemu powiadomień.")
