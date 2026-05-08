import streamlit as st
import pandas as pd
from pathlib import Path
import html

st.set_page_config(
    page_title="KANIBAL ANALYTICS",
    layout="wide",
    initial_sidebar_state="collapsed"
)

DATA_DIR = Path("data")

PREMATCH_FILE = DATA_DIR / "auto_all_picks.csv"
LIVE_FILE = DATA_DIR / "live_matches.csv"

BANNER_FILE = Path("kanibal_banner_pro.webp")


def safe_text(value):

    if pd.isna(value):
        return "-"

    return html.escape(str(value))


def load_csv(path):

    if path.exists():

        try:
            return pd.read_csv(path)

        except:
            return pd.DataFrame()

    return pd.DataFrame()


def badge(value, kind="green"):

    value = safe_text(value)

    colors = {

        "green": (
            "#58ff2f",
            "rgba(88,255,47,0.12)",
            "rgba(88,255,47,0.35)"
        ),

        "yellow": (
            "#ffd21a",
            "rgba(255,210,26,0.12)",
            "rgba(255,210,26,0.35)"
        ),

        "red": (
            "#ff3b30",
            "rgba(255,59,48,0.12)",
            "rgba(255,59,48,0.35)"
        ),

        "gray": (
            "#d7d7d7",
            "rgba(255,255,255,0.06)",
            "rgba(255,255,255,0.12)"
        )
    }

    fg, bg, border = colors.get(kind, colors["gray"])

    return f"""
    <span style="
        color:{fg};
        background:{bg};
        border:1px solid {border};
        padding:6px 10px;
        border-radius:8px;
        font-weight:800;
        font-size:12px;
        letter-spacing:.4px;
        display:inline-block;
        min-width:70px;
        text-align:center;
    ">
        {value}
    </span>
    """


def confidence_bar(value):

    try:
        value = int(float(value))

    except:
        value = 0

    color = "#58ff2f"

    if value < 60:
        color = "#ff3b30"

    elif value < 80:
        color = "#ffd21a"

    return f"""
    <div style="display:flex;align-items:center;gap:10px;">
        <span style="width:42px;font-weight:800;color:#ffffff;">
            {value}%
        </span>

        <div style="
            height:8px;
            background:#2b2f33;
            border-radius:999px;
            width:110px;
            overflow:hidden;
        ">

            <div style="
                height:8px;
                background:{color};
                width:{max(0, min(value, 100))}%;
                border-radius:999px;
            "></div>

        </div>
    </div>
    """


def risk_badge(value):

    value_text = str(value).upper()

    if "LOW" in value_text:
        return badge("LOW", "green")

    if "MEDIUM" in value_text:
        return badge("MEDIUM", "yellow")

    if "HIGH" in value_text:
        return badge("HIGH", "red")

    return badge(value, "gray")


def cashout_badge(value):

    value_text = str(value).upper()

    if "HOLD" in value_text:
        return badge("HOLD", "green")

    if "PARTIAL" in value_text:
        return badge("PARTIAL", "yellow")

    if "FULL" in value_text:
        return badge("FULL", "red")

    return badge(value, "gray")


def signal_badge(value):

    value_text = str(value).upper()

    if "OVER" in value_text:
        return badge(value, "green")

    if "BTTS" in value_text:
        return badge(value, "yellow")

    if "NO SIGNAL" in value_text:
        return badge("NO SIGNAL", "gray")

    return badge(value, "green")


st.markdown(
    """
    <style>

    .stApp {

        background:
            radial-gradient(circle at top right, rgba(81,255,0,0.14), transparent 28%),
            radial-gradient(circle at top left, rgba(255,80,0,0.08), transparent 26%),
            linear-gradient(180deg, #050607 0%, #090b0d 45%, #050607 100%);

        color: #f5f5f5;
    }

    header[data-testid="stHeader"] {
        background: transparent;
    }

    .block-container {

        padding-top: 1.2rem;
        padding-left: 1rem;
        padding-right: 1rem;
        max-width: 1500px;
    }

    h1, h2, h3 {

        color: #ffffff !important;
        font-family: Arial, Helvetica, sans-serif;
        letter-spacing: .5px;
    }

    .panel {

        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px;

        background:
            linear-gradient(
                180deg,
                rgba(255,255,255,0.045),
                rgba(255,255,255,0.018)
            );

        box-shadow: 0 18px 45px rgba(0,0,0,0.35);

        padding: 22px;
        margin-bottom: 18px;
    }

    .panel-title {

        display:flex;
        align-items:center;
        gap:12px;
        margin-bottom:6px;
    }

    .green-dot {

        width:14px;
        height:14px;
        border-radius:50%;
        background:#58ff2f;
        box-shadow:0 0 16px rgba(88,255,47,0.9);
    }

    .subtitle {

        color:#8f969d;
        font-size:12px;
        letter-spacing:.9px;
        text-transform:uppercase;
        margin-bottom:20px;
    }

    .table {

        width:100%;
        border-collapse:collapse;
        overflow:hidden;
    }

    .table th {

        color:#9aa0a6;
        font-size:12px;
        text-transform:uppercase;
        letter-spacing:.6px;
        padding:12px 10px;
        text-align:left;
        border-bottom:1px solid rgba(255,255,255,0.09);
    }

    .table td {

        padding:14px 10px;
        border-bottom:1px solid rgba(255,255,255,0.07);
        color:#f2f2f2;
        font-size:14px;
        vertical-align:middle;
    }

    .table tr:hover {
        background:rgba(112,255,47,0.04);
    }

    .minute {

        color:#70ff2f;
        font-weight:900;
        font-size:18px;
    }

    .positive {

        color:#70ff2f;
        font-weight:900;
    }

    .negative {

        color:#ff3b30;
        font-weight:900;
    }

    </style>
    """,
    unsafe_allow_html=True
)

if BANNER_FILE.exists():

    st.image(
        str(BANNER_FILE),
        use_container_width=True
    )

live_df = load_csv(LIVE_FILE)

prematch_df = load_csv(PREMATCH_FILE)

# =========================
# LIVE SIGNALS
# =========================

st.markdown(
    """
    <div class="panel">

        <div class="panel-title">

            <div class="green-dot"></div>

            <h2 style="margin:0;">
                LIVE SIGNALS
            </h2>

        </div>

        <div class="subtitle">
            AKTUALIZOWANE CO 60 SEKUND
        </div>

    """,
    unsafe_allow_html=True
)

if not live_df.empty:

    rows = ""

    for _, row in live_df.iterrows():

        home = safe_text(row.get("home", "-"))
        away = safe_text(row.get("away", "-"))

        league = safe_text(row.get("league", "-"))

        minute = safe_text(row.get("minute", "-"))

        score = safe_text(row.get("score", "-"))

        signal = row.get("signal", "NO SIGNAL")

        confidence = row.get("confidence", 0)

        odds = safe_text(row.get("odds", "-"))

        value = safe_text(row.get("value", 0))

        ev = safe_text(row.get("ev", 0))

        cashout = row.get("cashout", "NO CASHOUT")

        stake = safe_text(row.get("stake", "-"))

        risk = row.get("risk", "-")

        rows += f"""

        <tr>

            <td>{league}</td>

            <td>
                <b>{home}</b><br>
                <span style="color:#9aa0a6;">
                    {away}
                </span>
            </td>

            <td>
                <span class="minute">
                    {minute}'
                </span>
            </td>

            <td><b>{score}</b></td>

            <td>{signal_badge(signal)}</td>

            <td>{confidence_bar(confidence)}</td>

            <td>{odds}</td>

            <td class="positive">
                {value}%
            </td>

            <td class="positive">
                {ev}%
            </td>

            <td>{cashout_badge(cashout)}</td>

            <td>{stake}</td>

            <td>{risk_badge(risk)}</td>

        </tr>
        """

    st.markdown(
        f"""
        <table class="table">

            <thead>

                <tr>

                    <th>League</th>
                    <th>Match</th>
                    <th>Minute</th>
                    <th>Score</th>
                    <th>Signal</th>
                    <th>Confidence</th>
                    <th>Odds</th>
                    <th>Value</th>
                    <th>EV</th>
                    <th>Cashout</th>
                    <th>Stake</th>
                    <th>Risk</th>

                </tr>

            </thead>

            <tbody>

                {rows}

            </tbody>

        </table>
        """,
        unsafe_allow_html=True
    )

else:

    st.warning("Brak danych LIVE")

st.markdown(
    "</div>",
    unsafe_allow_html=True
)

# =========================
# PREMATCH
# =========================

st.markdown(
    """
    <div class="panel">

        <div class="panel-title">

            <div class="green-dot"></div>

            <h2 style="margin:0;">
                PREMATCH PICKS
            </h2>

        </div>

        <div class="subtitle">
            CORE VALUE ENGINE
        </div>
    """,
    unsafe_allow_html=True
)

if not prematch_df.empty:

    prematch_df = prematch_df.drop(
        columns=[
            "pick_id",
            "odds_event_id",
            "home_team",
            "away_team",
            "match_date"
        ],
        errors="ignore"
    )

    prematch_rows = ""

    for _, row in prematch_df.iterrows():

        liga = safe_text(row.get("liga", "-"))

        mecz = safe_text(row.get("mecz", "-"))

        market = safe_text(row.get("market", "-"))

        typ = safe_text(row.get("typ", "-"))

        kurs_buk = safe_text(row.get("kurs_buk", "-"))

        kurs_model = safe_text(row.get("kurs_model", "-"))

        kurs_bota = safe_text(row.get("kurs_bota", "-"))

        prawd_model = safe_text(row.get("prawd_model", "-"))

        prematch_rows += f"""

        <tr>

            <td>{liga}</td>

            <td>
                <b>{mecz}</b>
            </td>

            <td>
                {signal_badge(market)}
            </td>

            <td>{typ}</td>

            <td>{kurs_buk}</td>

            <td>{kurs_model}</td>

            <td>{kurs_bota}</td>

            <td>{prawd_model}</td>

        </tr>
        """

    st.markdown(
        f"""
        <table class="table">

            <thead>

                <tr>

                    <th>League</th>
                    <th>Match</th>
                    <th>Market</th>
                    <th>Pick</th>
                    <th>Bookmaker</th>
                    <th>Model</th>
                    <th>Bot</th>
                    <th>Probability</th>

                </tr>

            </thead>

            <tbody>

                {prematch_rows}

            </tbody>

        </table>
        """,
        unsafe_allow_html=True
    )

else:

    st.warning("Brak danych PREMATCH")

st.markdown(
    "</div>",
    unsafe_allow_html=True
)

# =========================
# CASHOUT GUIDE
# =========================

st.markdown(
    """
    <div class="panel">

        <h2>
            CASHOUT AI GUIDE
        </h2>

        <div style="
            margin-top:14px;
            padding:16px;
            border-radius:12px;
            border:1px solid rgba(88,255,47,0.35);
            background:rgba(88,255,47,0.08);
        ">

            <b style="color:#70ff2f;">
                HOLD POSITION
            </b><br>

            <span style="color:#cfd4d8;">
                Wysoka presja i momentum. Trzymaj zakład.
            </span>

        </div>

        <div style="
            margin-top:12px;
            padding:16px;
            border-radius:12px;
            border:1px solid rgba(255,210,26,0.35);
            background:rgba(255,210,26,0.08);
        ">

            <b style="color:#ffd21a;">
                PARTIAL CASHOUT
            </b><br>

            <span style="color:#cfd4d8;">
                Spadający confidence. Rozważ częściowe wyjście.
            </span>

        </div>

        <div style="
            margin-top:12px;
            padding:16px;
            border-radius:12px;
            border:1px solid rgba(255,59,48,0.35);
            background:rgba(255,59,48,0.08);
        ">

            <b style="color:#ff3b30;">
                FULL CASHOUT
            </b><br>

            <span style="color:#cfd4d8;">
                Niski momentum i presja. Wyjdź z zakładu.
            </span>

        </div>

    </div>
    """,
    unsafe_allow_html=True
)
