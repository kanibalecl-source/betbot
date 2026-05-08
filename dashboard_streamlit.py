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
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def badge(value, kind="green"):
    value = safe_text(value)

    colors = {
        "green": ("#58ff2f", "rgba(88,255,47,0.12)", "rgba(88,255,47,0.35)"),
        "yellow": ("#ffd21a", "rgba(255,210,26,0.12)", "rgba(255,210,26,0.35)"),
        "red": ("#ff3b30", "rgba(255,59,48,0.12)", "rgba(255,59,48,0.35)"),
        "gray": ("#d7d7d7", "rgba(255,255,255,0.06)", "rgba(255,255,255,0.12)")
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
    except Exception:
        value = 0

    color = "#58ff2f"
    if value < 60:
        color = "#ff3b30"
    elif value < 80:
        color = "#ffd21a"

    return f"""
    <div style="display:flex;align-items:center;gap:10px;">
        <span style="width:42px;font-weight:800;color:#ffffff;">{value}%</span>
        <div style="height:8px;background:#2b2f33;border-radius:999px;width:110px;overflow:hidden;">
            <div style="height:8px;background:{color};width:{max(0, min(value, 100))}%;border-radius:999px;"></div>
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

        .kanibal-banner {
            width: 100%;
            border-radius: 18px;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.08);
            box-shadow: 0 20px 60px rgba(0,0,0,0.55);
            margin-bottom: 18px;
        }

        .nav {
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 12px;
            overflow: hidden;
            margin: 18px 0;
            background: rgba(255,255,255,0.025);
        }

        .nav div {
            padding: 18px 10px;
            text-align: center;
            font-weight: 800;
            font-size: 13px;
            color: #d7d7d7;
            border-right: 1px solid rgba(255,255,255,0.07);
        }

        .nav div:last-child {
            border-right: none;
        }

        .nav .active {
            color: #70ff2f;
            border-bottom: 3px solid #70ff2f;
            background: rgba(112,255,47,0.08);
        }

        .panel {
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px;
            background:
                linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.018));
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

        .metric-grid {
            display:grid;
            grid-template-columns: repeat(4, 1fr);
            gap:12px;
            margin-top:15px;
        }

        .metric-card {
            background:rgba(255,255,255,0.035);
            border:1px solid rgba(255,255,255,0.07);
            border-radius:12px;
            padding:16px;
        }

        .metric-label {
            color:#8f969d;
            font-size:11px;
            text-transform:uppercase;
            letter-spacing:.7px;
        }

        .metric-value {
            color:#ffffff;
            font-size:28px;
            font-weight:900;
            margin-top:5px;
        }

        .metric-change {
            color:#70ff2f;
            font-size:13px;
            margin-top:3px;
        }

        .small-list {
            display:flex;
            flex-direction:column;
            gap:12px;
            margin-top:18px;
        }

        .rank-row {
            display:flex;
            justify-content:space-between;
            align-items:center;
            padding:12px;
            border-bottom:1px solid rgba(255,255,255,0.08);
        }

        .rank-number {
            width:28px;
            height:28px;
            border-radius:50%;
            border:1px solid rgba(112,255,47,0.6);
            color:#70ff2f;
            display:flex;
            align-items:center;
            justify-content:center;
            font-weight:900;
            margin-right:12px;
        }

        .footer {
            color:#6f767d;
            font-size:12px;
            letter-spacing:.8px;
            margin-top:20px;
            padding-bottom:30px;
        }

        @media (max-width: 900px) {
            .nav {
                grid-template-columns: repeat(2, 1fr);
            }

            .metric-grid {
                grid-template-columns: repeat(2, 1fr);
            }

            .table th, .table td {
                font-size:12px;
                padding:10px 6px;
            }
        }
    </style>
    """,
    unsafe_allow_html=True
)

if BANNER_FILE.exists():
    st.image(str(BANNER_FILE), use_container_width=True)
else:
    st.markdown(
        """
        <div class="panel">
            <h1>KANIBAL ANALYTICS</h1>
            <div class="subtitle">ANALIZA. PRZEWAGA. ZYSK.</div>
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown(
    """
    <div class="nav">
        <div class="active">📡 LIVE</div>
        <div>⚽ PREMATCH</div>
        <div>📊 ANALYTICS</div>
        <div>🕘 HISTORY</div>
        <div>🏆 RANKING</div>
        <div>🔔 ALERTS</div>
        <div>⚙️ SETTINGS</div>
    </div>
    """,
    unsafe_allow_html=True
)

live_df = load_csv(LIVE_FILE)
prematch_df = load_csv(PREMATCH_FILE)

# =========================
# LIVE PANEL
# =========================

st.markdown(
    """
    <div class="panel">
        <div class="panel-title">
            <div class="green-dot"></div>
            <h2 style="margin:0;">LIVE SIGNALS</h2>
        </div>
        <div class="subtitle">AKTUALIZOWANE CO 60 SEKUND</div>
    """,
    unsafe_allow_html=True
)

if live_df.empty:
    st.markdown(
        """
        <div style="
            padding:20px;
            border:1px solid rgba(255,210,26,0.25);
            background:rgba(255,210,26,0.08);
            color:#ffd21a;
            border-radius:12px;
            font-weight:800;">
            Brak danych LIVE
        </div>
        """,
        unsafe_allow_html=True
    )
else:
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
        value = row.get("value", 0)
        ev = row.get("ev", 0)
        cashout = row.get("cashout", "NO CASHOUT")
        stake = safe_text(row.get("stake", "-"))
        risk = row.get("risk", "-")

        try:
            value_num = float(value)
        except Exception:
            value_num = 0

        try:
            ev_num = float(ev)
        except Exception:
            ev_num = 0

        value_class = "positive" if value_num >= 0 else "negative"
        ev_class = "positive" if ev_num >= 0 else "negative"

        rows += f"""
        <tr>
            <td>{league}</td>
            <td><b>{home}</b><br><span style="color:#9aa0a6;">{away}</span></td>
            <td><span class="minute">{minute}'</span></td>
            <td><b>{score}</b></td>
            <td>{signal_badge(signal)}</td>
            <td>{confidence_bar(confidence)}</td>
            <td>{odds}</td>
            <td class="{value_class}">{safe_text(value)}%</td>
            <td class="{ev_class}">{safe_text(ev)}%</td>
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

st.markdown("</div>", unsafe_allow_html=True)

# =========================
# ANALYTICS PANELS
# =========================

total_live = len(live_df) if not live_df.empty else 0

avg_confidence = 0
avg_value = 0
avg_ev = 0

if not live_df.empty:
    if "confidence" in live_df.columns:
        avg_confidence = round(pd.to_numeric(live_df["confidence"], errors="coerce").fillna(0).mean(), 2)
    if "value" in live_df.columns:
        avg_value = round(pd.to_numeric(live_df["value"], errors="coerce").fillna(0).mean(), 2)
    if "ev" in live_df.columns:
        avg_ev = round(pd.to_numeric(live_df["ev"], errors="coerce").fillna(0).mean(), 2)

col1, col2, col3 = st.columns([1.2, 0.8, 0.9])

with col1:
    st.markdown(
        f"""
        <div class="panel">
            <h3>STATS OVERVIEW</h3>
            <div class="metric-grid">
                <div class="metric-card">
                    <div class="metric-label">Total Signals</div>
                    <div class="metric-value">{total_live}</div>
                    <div class="metric-change">LIVE</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Avg Confidence</div>
                    <div class="metric-value">{avg_confidence}%</div>
                    <div class="metric-change">AI SCORE</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Avg Value</div>
                    <div class="metric-value">{avg_value}%</div>
                    <div class="metric-change">EDGE</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Avg EV</div>
                    <div class="metric-value">{avg_ev}%</div>
                    <div class="metric-change">EXPECTED VALUE</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col2:
    ranking_html = ""

    if not live_df.empty and "value" in live_df.columns:
        ranking_df = live_df.copy()
        ranking_df["value"] = pd.to_numeric(ranking_df["value"], errors="coerce").fillna(0)
        ranking_df = ranking_df.sort_values("value", ascending=False).head(5)

        for index, (_, row) in enumerate(ranking_df.iterrows(), start=1):
            match_name = f"{safe_text(row.get('home', '-'))} vs {safe_text(row.get('away', '-'))}"
            league = safe_text(row.get("league", "-"))
            value = safe_text(row.get("value", 0))

            ranking_html += f"""
            <div class="rank-row">
                <div style="display:flex;align-items:center;">
                    <div class="rank-number">{index}</div>
                    <div>
                        <b>{match_name}</b><br>
                        <span style="color:#8f969d;font-size:12px;">{league}</span>
                    </div>
                </div>
                <div class="positive">+{value}%</div>
            </div>
            """
    else:
        ranking_html = "<div style='color:#8f969d;padding:14px;'>Brak danych rankingu</div>"

    st.markdown(
        f"""
        <div class="panel">
            <h3>VALUE TOP 5</h3>
            <div class="small-list">
                {ranking_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col3:
    low = medium = high = 0

    if not live_df.empty and "risk" in live_df.columns:
        risk_series = live_df["risk"].astype(str).str.upper()
        low = int(risk_series.str.contains("LOW").sum())
        medium = int(risk_series.str.contains("MEDIUM").sum())
        high = int(risk_series.str.contains("HIGH").sum())

    st.markdown(
        f"""
        <div class="panel">
            <h3>RISK DISTRIBUTION</h3>
            <div style="display:flex;flex-direction:column;gap:14px;margin-top:22px;">
                <div style="display:flex;justify-content:space-between;">
                    <span>{badge("LOW", "green")}</span><b>{low}</b>
                </div>
                <div style="display:flex;justify-content:space-between;">
                    <span>{badge("MEDIUM", "yellow")}</span><b>{medium}</b>
                </div>
                <div style="display:flex;justify-content:space-between;">
                    <span>{badge("HIGH", "red")}</span><b>{high}</b>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# =========================
# PREMATCH PANEL
# =========================

st.markdown(
    """
    <div class="panel">
        <div class="panel-title">
            <div class="green-dot"></div>
            <h2 style="margin:0;">PREMATCH PICKS</h2>
        </div>
        <div class="subtitle">CORE VALUE ENGINE</div>
    """,
    unsafe_allow_html=True
)

if prematch_df.empty:
    st.markdown(
        """
        <div style="
            padding:20px;
            border:1px solid rgba(255,210,26,0.25);
            background:rgba(255,210,26,0.08);
            color:#ffd21a;
            border-radius:12px;
            font-weight:800;">
            Brak danych PREMATCH
        </div>
        """,
        unsafe_allow_html=True
    )
else:
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

    st.dataframe(
        prematch_df,
        use_container_width=True,
        height=min(420, 36 * len(prematch_df) + 80)
    )

st.markdown("</div>", unsafe_allow_html=True)

# =========================
# CASHOUT GUIDE
# =========================

st.markdown(
    """
    <div class="panel">
        <h3>CASHOUT AI GUIDE</h3>

        <div style="
            margin-top:14px;
            padding:16px;
            border-radius:12px;
            border:1px solid rgba(88,255,47,0.35);
            background:rgba(88,255,47,0.08);
        ">
            <b style="color:#70ff2f;">HOLD POSITION</b><br>
            <span style="color:#cfd4d8;">Wysoka presja i momentum. Trzymaj zakład.</span>
        </div>

        <div style="
            margin-top:12px;
            padding:16px;
            border-radius:12px;
            border:1px solid rgba(255,210,26,0.35);
            background:rgba(255,210,26,0.08);
        ">
            <b style="color:#ffd21a;">PARTIAL CASHOUT</b><br>
            <span style="color:#cfd4d8;">Spadający confidence. Rozważ częściowe wyjście.</span>
        </div>

        <div style="
            margin-top:12px;
            padding:16px;
            border-radius:12px;
            border:1px solid rgba(255,59,48,0.35);
            background:rgba(255,59,48,0.08);
        ">
            <b style="color:#ff3b30;">FULL CASHOUT</b><br>
            <span style="color:#cfd4d8;">Niski momentum i presja. Wyjdź z zakładu.</span>
        </div>
    </div>

    <div class="footer">
        KANIBAL ANALYTICS | ANALIZA. PRZEWAGA. ZYSK.
    </div>
    """,
    unsafe_allow_html=True
)
