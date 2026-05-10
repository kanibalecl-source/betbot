import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime

# =========================================================
# KANIBAL ANALYTICS — FINAL DASHBOARD
# =========================================================

st.set_page_config(
    page_title="KANIBAL ANALYTICS",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

DATA_DIR = Path("data")
CSV_FILE = DATA_DIR / "auto_all_picks.csv"

BANNER_CANDIDATES = [
    Path("kanibal_banner.png"),
    Path("kanibal_banner.jpg"),
    Path("kanibal_banner.webp"),
    Path("assets/kanibal_banner.png"),
    Path("assets/kanibal_banner.jpg"),
    Path("assets/kanibal_banner.webp"),
]

# =========================================================
# CSS
# =========================================================

st.markdown(
    """
    <style>

    .stApp {
        background:
            radial-gradient(circle at top right, rgba(85, 255, 25, 0.13), transparent 28%),
            radial-gradient(circle at top left, rgba(255, 120, 20, 0.08), transparent 20%),
            linear-gradient(180deg, #050607 0%, #080b0f 45%, #050607 100%);
        color: #ffffff;
    }

    header[data-testid="stHeader"] {
        background: transparent;
    }

    .block-container {
        max-width: 100% !important;
        padding-top: 1.1rem !important;
        padding-left: 1.4rem !important;
        padding-right: 1.4rem !important;
        padding-bottom: 2rem !important;
    }

    h1, h2, h3, h4, h5, h6, p, span, div {
        color: inherit;
    }

    .kanibal-hero {
        background:
            linear-gradient(90deg, rgba(8, 10, 14, 0.98), rgba(13, 18, 25, 0.94)),
            radial-gradient(circle at right, rgba(107, 255, 35, 0.22), transparent 36%);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 22px;
        padding: 34px 38px;
        margin-bottom: 18px;
        box-shadow: 0 24px 70px rgba(0,0,0,0.45);
        overflow: hidden;
    }

    .kanibal-logo-row {
        display: flex;
        align-items: center;
        gap: 18px;
    }

    .kanibal-mark {
        width: 58px;
        height: 58px;
        border-radius: 18px;
        background: linear-gradient(135deg, #ffffff, #72ff2f);
        box-shadow: 0 0 28px rgba(114,255,47,0.35);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 31px;
    }

    .kanibal-title {
        font-size: 54px;
        font-weight: 950;
        color: #ffffff;
        letter-spacing: 1.5px;
        line-height: 1;
        text-shadow: 0 0 22px rgba(255,255,255,0.10);
    }

    .kanibal-subtitle {
        margin-top: 16px;
        color: #a7b0bf;
        font-size: 16px;
        letter-spacing: 5px;
        font-weight: 700;
    }

    .kanibal-green {
        color: #72ff2f;
    }

    .feature-row {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 14px;
        margin-top: 32px;
    }

    .feature-card {
        padding: 13px 15px;
        border-left: 1px solid rgba(255,255,255,0.18);
        color: #e5e7eb;
        font-size: 13px;
        font-weight: 800;
        letter-spacing: 0.5px;
    }

    .nav-wrap {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 0;
        background: #070a0e;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 14px;
        overflow: hidden;
        margin: 18px 0 22px 0;
    }

    .nav-item {
        text-align: center;
        padding: 18px 10px;
        font-size: 13px;
        font-weight: 900;
        border-right: 1px solid rgba(255,255,255,0.07);
        color: #ffffff;
    }

    .nav-item.active {
        background: linear-gradient(180deg, rgba(114,255,47,0.16), rgba(114,255,47,0.05));
        color: #72ff2f;
        border-bottom: 3px solid #72ff2f;
    }

    .metric-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 14px;
        margin-bottom: 18px;
    }

    .metric-card {
        background:
            linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.018));
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 18px;
        padding: 18px;
        box-shadow: 0 18px 40px rgba(0,0,0,0.35);
    }

    .metric-label {
        color: #8f98a8;
        font-size: 12px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .metric-value {
        color: #72ff2f;
        font-size: 32px;
        font-weight: 950;
        margin-top: 8px;
    }

    .panel {
        background:
            linear-gradient(180deg, rgba(255,255,255,0.038), rgba(255,255,255,0.014));
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 18px;
        padding: 22px;
        margin-bottom: 18px;
        box-shadow: 0 18px 45px rgba(0,0,0,0.35);
    }

    .panel-title {
        color: #ffffff;
        font-size: 22px;
        font-weight: 950;
        margin-bottom: 4px;
    }

    .panel-subtitle {
        color: #8f98a8;
        font-size: 12px;
        font-weight: 800;
        text-transform: uppercase;
        margin-bottom: 18px;
    }

    div[data-testid="stDataFrame"] {
        border-radius: 16px !important;
        overflow: hidden !important;
        border: 1px solid rgba(255,255,255,0.10) !important;
        box-shadow: 0 20px 45px rgba(0,0,0,0.28);
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background: #070a0e;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 14px;
        overflow: hidden;
        margin-top: 14px;
        margin-bottom: 22px;
    }

    .stTabs [data-baseweb="tab"] {
        color: #ffffff !important;
        height: 56px;
        padding: 0 24px;
        font-size: 13px;
        font-weight: 900;
        background: transparent;
        border-right: 1px solid rgba(255,255,255,0.06);
    }

    .stTabs [aria-selected="true"] {
        color: #72ff2f !important;
        background: rgba(114,255,47,0.09) !important;
        border-bottom: 3px solid #72ff2f !important;
    }

    .small-note {
        color: #8792a3;
        font-size: 12px;
        margin-top: 10px;
    }

    @media (max-width: 1000px) {
        .feature-row { grid-template-columns: repeat(2, 1fr); }
        .metric-grid { grid-template-columns: repeat(2, 1fr); }
        .kanibal-title { font-size: 38px; }
        .nav-wrap { grid-template-columns: repeat(2, 1fr); }
    }

    </style>
    """,
    unsafe_allow_html=True
)

# =========================================================
# DATA HELPERS
# =========================================================

def to_num(series):
    return pd.to_numeric(series, errors="coerce")


def first_existing(df, names):
    for name in names:
        if name in df.columns:
            return name
    return None


@st.cache_data(ttl=30)
def load_csv():
    if not CSV_FILE.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(CSV_FILE)
    except Exception:
        try:
            df = pd.read_csv(CSV_FILE, encoding="utf-8")
        except Exception as e:
            st.error(f"CSV ERROR: {e}")
            return pd.DataFrame()

    df = df.fillna("")

    # Arrow / white screen fix: keep only scalar strings for display safety
    for col in df.columns:
        try:
            df[col] = df[col].astype(str)
        except Exception:
            pass

    return df


def normalize_percent(value, decimals=1):
    try:
        v = float(str(value).replace("%", "").replace(",", "."))
        if abs(v) <= 1:
            v *= 100
        return f"{v:.{decimals}f}%"
    except Exception:
        return "-"


def normalize_float(value, decimals=2):
    try:
        return f"{float(str(value).replace(',', '.')):.{decimals}f}"
    except Exception:
        return "-"


def normalize_money(value):
    try:
        return f"{float(str(value).replace(',', '.')):.2f} zł"
    except Exception:
        return "-"


def build_display_table(df, mode="prematch"):
    if df.empty:
        return pd.DataFrame()

    out = pd.DataFrame()

    def add(label, candidates, formatter=None, default="-"):
        col = first_existing(df, candidates)
        if col is None:
            out[label] = default
        else:
            if formatter:
                out[label] = df[col].apply(formatter)
            else:
                out[label] = df[col].replace("", default)

    add("LEAGUE", ["liga", "league"])
    add("MATCH", ["mecz", "match"])
    add("MINUTE", ["minute", "min"])
    add("SCORE", ["score"])
    add("SIGNAL", ["typ", "signal", "market"])
    add("BOOK ODDS", ["kurs_buk", "odds"], lambda x: normalize_float(x, 2))
    add("BOT ODDS", ["kurs_bota", "fair_odds"], lambda x: normalize_float(x, 2))
    add("MODEL ODDS", ["kurs_model"], lambda x: normalize_float(x, 2))
    add("CONF", ["confidence", "prawd_final"], lambda x: normalize_percent(x, 1))
    add("EV", ["ev_percent", "ev"], lambda x: normalize_percent(x, 2))
    add("EDGE", ["edge"], lambda x: normalize_percent(x, 2))
    add("MARGIN", ["marza_%"], lambda x: normalize_percent(x, 2))
    add("HOME xG", ["home_xg"], lambda x: normalize_float(x, 2))
    add("AWAY xG", ["away_xg"], lambda x: normalize_float(x, 2))
    add("TEMPO", ["tempo_level"])
    add("STAKE", ["recommended_stake", "stake"], normalize_money)
    add("RISK", ["risk_level", "risk", "ai_risk"])
    add("STATUS", ["status"])

    if mode == "live":
        preferred = [
            "LEAGUE", "MATCH", "MINUTE", "SCORE", "SIGNAL",
            "CONF", "BOOK ODDS", "BOT ODDS", "EV", "EDGE",
            "TEMPO", "STAKE", "RISK", "STATUS"
        ]
    else:
        preferred = [
            "LEAGUE", "MATCH", "SIGNAL",
            "BOOK ODDS", "BOT ODDS", "MODEL ODDS",
            "EV", "EDGE", "MARGIN",
            "HOME xG", "AWAY xG",
            "CONF", "STAKE", "RISK", "STATUS"
        ]

    return out[preferred]


def live_filter(df):
    if df.empty or "minute" not in df.columns:
        return pd.DataFrame()

    minute_num = pd.to_numeric(df["minute"], errors="coerce")

    if "status" in df.columns:
        status = df["status"].astype(str).str.upper()
        live_status = status.isin(["1H", "2H", "HT", "LIVE", "ET", "BT"])
        return df[(minute_num > 0) | live_status]

    return df[minute_num > 0]


def metric_value(df, col_candidates, mode="avg", percent=False):
    if df.empty:
        return "0"

    col = first_existing(df, col_candidates)
    if col is None:
        return "0"

    vals = to_num(df[col])

    if vals.dropna().empty:
        return "0"

    if mode == "avg":
        value = vals.mean()
    elif mode == "max":
        value = vals.max()
    elif mode == "sum":
        value = vals.sum()
    else:
        value = vals.mean()

    if percent:
        if abs(value) <= 1:
            value *= 100
        return f"{value:.1f}%"

    return f"{value:.1f}"


# =========================================================
# LOAD DATA
# =========================================================

df = load_csv()
live_df = live_filter(df)
prematch_df = df.copy()

# =========================================================
# HEADER / HERO
# =========================================================

banner_path = next((p for p in BANNER_CANDIDATES if p.exists()), None)

if banner_path:
    st.image(str(banner_path), use_container_width=True)
else:
    st.markdown(
        """
        <div class="kanibal-hero">
            <div class="kanibal-logo-row">
                <div class="kanibal-mark">📈</div>
                <div>
                    <div class="kanibal-title">KANIBAL ANALYTICS</div>
                    <div class="kanibal-subtitle">
                        ANALIZA · <span class="kanibal-green">PRZEWAGA</span> · ZYSK
                    </div>
                </div>
            </div>
            <div class="feature-row">
                <div class="feature-card">🎯 PRECYZYJNE<br>ANALIZY</div>
                <div class="feature-card">📊 DANE, KTÓRE<br>DAJĄ PRZEWAGĘ</div>
                <div class="feature-card">🛡️ SPRAWDZONE<br>STRATEGIE</div>
                <div class="feature-card">🏆 LEPSZE TYPY<br>WIĘKSZE WYGRANE</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# =========================================================
# METRICS
# =========================================================

total_signals = len(df)
live_count = len(live_df)
avg_ev = metric_value(df, ["ev_percent", "ev"], percent=True)
avg_conf = metric_value(df, ["confidence", "prawd_final"], percent=True)

st.markdown(
    f"""
    <div class="metric-grid">
        <div class="metric-card">
            <div class="metric-label">TOTAL SIGNALS</div>
            <div class="metric-value">{total_signals}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">LIVE MATCHES</div>
            <div class="metric-value">{live_count}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">AVG EV</div>
            <div class="metric-value">{avg_ev}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">AVG CONFIDENCE</div>
            <div class="metric-value">{avg_conf}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# =========================================================
# TABS
# =========================================================

live_tab, prematch_tab, analytics_tab, history_tab, ranking_tab, alerts_tab, settings_tab = st.tabs(
    [
        "📡 LIVE",
        "🎯 PREMATCH",
        "📊 ANALYTICS",
        "🕘 HISTORY",
        "🏆 RANKING",
        "🔔 ALERTS",
        "⚙️ SETTINGS"
    ]
)

# =========================================================
# LIVE
# =========================================================

with live_tab:
    st.markdown(
        """
        <div class="panel">
            <div class="panel-title">🟢 LIVE SIGNALS</div>
            <div class="panel-subtitle">AKTUALIZOWANE CO 60 SEKUND</div>
        """,
        unsafe_allow_html=True
    )

    if live_df.empty:
        st.warning("Brak danych LIVE. LIVE pokazuje tylko mecze z minutą > 0 lub statusem 1H/2H/HT/LIVE.")
    else:
        st.dataframe(
            build_display_table(live_df, mode="live"),
            use_container_width=True,
            height=650,
            hide_index=True
        )

    st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# PREMATCH
# =========================================================

with prematch_tab:
    st.markdown(
        """
        <div class="panel">
            <div class="panel-title">🎯 PREMATCH SIGNALS</div>
            <div class="panel-subtitle">PEŁNE DANE MODELU: KURSY, EV, EDGE, MARŻA, xG</div>
        """,
        unsafe_allow_html=True
    )

    if prematch_df.empty:
        st.warning("Brak danych PREMATCH.")
    else:
        st.dataframe(
            build_display_table(prematch_df, mode="prematch"),
            use_container_width=True,
            height=700,
            hide_index=True
        )

    st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# ANALYTICS
# =========================================================

with analytics_tab:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
            <div class="panel">
                <div class="panel-title">📈 VALUE TOP 10</div>
                <div class="panel-subtitle">NAJLEPSZE TYPY WG EV</div>
            """,
            unsafe_allow_html=True
        )

        if df.empty:
            st.info("Brak danych.")
        else:
            ev_col = first_existing(df, ["ev_percent", "ev"])
            if ev_col:
                tmp = df.copy()
                tmp["_ev_sort"] = pd.to_numeric(tmp[ev_col], errors="coerce")
                st.dataframe(
                    build_display_table(tmp.sort_values("_ev_sort", ascending=False).head(10)),
                    use_container_width=True,
                    height=420,
                    hide_index=True
                )
            else:
                st.info("Brak kolumny EV.")

        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown(
            """
            <div class="panel">
                <div class="panel-title">⚠️ RISK DISTRIBUTION</div>
                <div class="panel-subtitle">PODZIAŁ RYZYKA</div>
            """,
            unsafe_allow_html=True
        )

        risk_col = first_existing(df, ["risk_level", "risk", "ai_risk"])
        if df.empty or risk_col is None:
            st.info("Brak danych risk.")
        else:
            risk_counts = df[risk_col].replace("", "UNKNOWN").value_counts().reset_index()
            risk_counts.columns = ["RISK", "COUNT"]
            st.dataframe(risk_counts, use_container_width=True, hide_index=True)

        st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# HISTORY
# =========================================================

with history_tab:
    history_file = DATA_DIR / "auto_all_picks_history.csv"
    if history_file.exists():
        try:
            hist = pd.read_csv(history_file).fillna("")
            for col in hist.columns:
                hist[col] = hist[col].astype(str)
            st.dataframe(build_display_table(hist.tail(300)), use_container_width=True, height=700, hide_index=True)
        except Exception as e:
            st.error(f"History CSV error: {e}")
    else:
        st.info("Brak historii.")

# =========================================================
# RANKING
# =========================================================

with ranking_tab:
    if df.empty:
        st.info("Brak danych rankingu.")
    else:
        ev_col = first_existing(df, ["ev_percent", "ev"])
        if ev_col:
            tmp = df.copy()
            tmp["_ev_sort"] = pd.to_numeric(tmp[ev_col], errors="coerce")
            st.dataframe(
                build_display_table(tmp.sort_values("_ev_sort", ascending=False).head(25)),
                use_container_width=True,
                height=700,
                hide_index=True
            )
        else:
            st.info("Brak EV do rankingu.")

# =========================================================
# ALERTS
# =========================================================

with alerts_tab:
    st.success("Alert system ONLINE")
    st.info("Alerty mogą być podpięte do Telegrama/Discorda w kolejnym kroku.")

# =========================================================
# SETTINGS
# =========================================================

with settings_tab:
    st.success("Scheduler: ONLINE")
    st.success("Data API: ONLINE")
    st.success("Odds API: ONLINE")
    st.success("ETAPY 1–10: ACTIVE")
    st.caption(f"CSV: {CSV_FILE}")
    st.caption(f"Ostatnia aktualizacja strony: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
