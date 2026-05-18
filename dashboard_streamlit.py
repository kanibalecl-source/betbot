
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
    "🧠 AI",
    "📊 ANALYTICS",
    "🕘 HISTORY",
    "🏆 RANKING",
    "🔔 ALERTS",
    "🤖 GPT"
])

live_tab, prematch_tab, ai_tab, analytics_tab, history_tab, ranking_tab, alerts_tab, gpt_tab = tabs

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

with history_tab:
    st.header("🕘 HISTORY")

with ranking_tab:
    st.header("🏆 RANKING")

with alerts_tab:
    st.header("🔔 ALERTS")

with gpt_tab:
    st.header("🤖 ANALIZA GPT")
    st.caption("Opisowe analizy ChatGPT dla typów znalezionych przez bota + propozycje kuponów AKO.")

    try:
        from gpt_match_value_engine import load_latest_report, run_full_gpt_analysis

        c1, c2, c3 = st.columns([1, 1, 2])

        with c1:
            limit = st.number_input(
                "Limit meczów do analizy",
                min_value=1,
                max_value=50,
                value=10,
                step=1,
                help="Na start ustaw mały limit, żeby kontrolować koszt API."
            )

        with c2:
            run_gpt = st.button("🚀 Uruchom analizę GPT", use_container_width=True)

        if run_gpt:
            with st.spinner("ChatGPT analizuje mecze i buduje kupony AKO..."):
                report = run_full_gpt_analysis(BASE_DIR, limit=int(limit))
            st.success(f"Gotowe. Przeanalizowano: {report.get('count', 0)}")
        else:
            report = load_latest_report(BASE_DIR)

        if report.get("message"):
            st.info(report.get("message"))
            st.caption(f"Kandydaci znalezieni przez bota: {report.get('candidates_found', 0)}")

        analyses = report.get("analyses", []) or []
        coupons = report.get("coupons", []) or []

        if report.get("generated_at"):
            st.caption(f"Ostatnia analiza: {report.get('generated_at')}")

        if analyses:
            st.subheader("📋 Oceny meczów")

            for item in analyses:
                decision = str(item.get("decision", "SKIP")).upper()
                confidence = item.get("confidence", 0)
                value_score = item.get("value_score", 0)
                risk = item.get("risk", "-")
                match_name = item.get("match", "Brak meczu")
                bet_name = item.get("bet", "Brak typu")
                odds = item.get("odds", "-")

                title_icon = "✅" if decision == "PLAY" else "⛔"
                with st.expander(f"{title_icon} {match_name} | {bet_name} | CONF {confidence}%"):
                    m1, m2, m3, m4 = st.columns(4)
                    with m1:
                        st.metric("Decyzja", decision)
                    with m2:
                        st.metric("Confidence", f"{confidence}%")
                    with m3:
                        st.metric("Value", value_score)
                    with m4:
                        st.metric("Risk", str(risk).upper())

                    st.markdown(
                        f"""
                        <div class="ai-box">
                        <h4 style="color:#58ff2f;">PODSUMOWANIE GPT</h4>
                        <b>Mecz:</b> {match_name}<br>
                        <b>Typ:</b> {bet_name}<br>
                        <b>Kurs:</b> {odds}<br><br>
                        {item.get('summary', '-')}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    analysis = item.get("analysis", {}) or {}
                    sections = [
                        ("🔥 Forma", analysis.get("forma")),
                        ("🚑 Kontuzje i kadra", analysis.get("kontuzje_kadra")),
                        ("⚔️ Styl gry i matchup", analysis.get("styl_matchup")),
                        ("🧠 Motywacja i atmosfera", analysis.get("motywacja_atmosfera")),
                        ("💎 Value kursu", analysis.get("value_kurs")),
                        ("⚠️ Ryzyka", analysis.get("ryzyka")),
                        ("✅ Rekomendacja", analysis.get("rekomendacja")),
                    ]

                    for header, body in sections:
                        if body:
                            st.markdown(f"### {header}")
                            st.write(body)

        if coupons:
            st.subheader("💎 Kupony AKO GPT")

            for coupon in coupons:
                picks = coupon.get("picks", []) or []
                if not picks:
                    continue

                with st.container(border=True):
                    st.markdown(f"### {coupon.get('name', 'AKO')} — {coupon.get('label', '')}")

                    k1, k2, k3 = st.columns(3)
                    with k1:
                        st.metric("Kurs łączny", coupon.get("total_odds", 0))
                    with k2:
                        st.metric("Śr. confidence", f"{coupon.get('avg_confidence', 0)}%")
                    with k3:
                        st.metric("Ryzyko", str(coupon.get("risk", "-")).upper())

                    for pick in picks:
                        st.markdown(
                            f"- **{pick.get('match', '-')}** — {pick.get('bet', '-')} "
                            f"@ {pick.get('odds', '-')} | CONF {pick.get('confidence', 0)}%"
                        )

        if not analyses and not report.get("message"):
            st.warning("Brak analiz GPT. Kliknij przycisk, aby uruchomić analizę.")

    except Exception as exc:
        st.error("Nie udało się załadować modułu GPT.")
        st.code(str(exc))
        st.info("Sprawdź, czy pliki gpt_match_value_engine.py i ako_coupon_builder.py są w głównym folderze bota oraz czy OPENAI_API_KEY jest ustawiony w Railway Variables.")

