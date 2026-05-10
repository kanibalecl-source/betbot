import streamlit as st
import pandas as pd
from pathlib import Path
import time

st.set_page_config(
    page_title="BetBot Dashboard",
    layout="wide"
)

DATA_DIR = Path("data")

PREMATCH_FILE = DATA_DIR / "auto_all_picks.csv"

st.title("⚽ BETBOT AI DASHBOARD")


def safe_load_csv(path):

    if not path.exists():
        return pd.DataFrame()

    try:

        df = pd.read_csv(path)

        # =========================
        # FIX BIAŁEJ STRONY
        # =========================

        df = df.fillna("")

        for col in df.columns:
            try:
                df[col] = df[col].astype(str)
            except Exception:
                pass

        return df

    except Exception as e:

        st.error(f"CSV ERROR: {e}")

        return pd.DataFrame()


def cleanup_dataframe(df):

    hide_cols = [
        "pick_id",
        "fixture_id",
        "odds_event_id",
        "home_team",
        "away_team",
        "home",
        "away",
    ]

    for col in hide_cols:
        if col in df.columns:
            df = df.drop(columns=[col])

    rename_map = {
        "mecz": "MATCH",
        "liga": "LEAGUE",
        "typ": "PICK",
        "kurs_buk": "ODDS",
        "confidence": "CONFIDENCE %",
        "ev_percent": "EV %",
        "tempo_level": "TEMPO",
        "tempo_score": "TEMPO SCORE",
        "risk_level": "RISK",
        "recommended_stake": "STAKE",
        "market_direction": "MARKET MOVE",
        "clv_percent": "CLV %",
        "minute": "MIN",
        "score": "SCORE",
        "status": "STATUS",
    }

    existing = {
        k: v for k, v in rename_map.items()
        if k in df.columns
    }

    df = df.rename(columns=existing)

    preferred_order = [
        "MATCH",
        "LEAGUE",
        "PICK",
        "ODDS",
        "CONFIDENCE %",
        "EV %",
        "TEMPO",
        "TEMPO SCORE",
        "RISK",
        "STAKE",
        "MARKET MOVE",
        "CLV %",
        "MIN",
        "SCORE",
        "STATUS",
        "match_date"
    ]

    final_cols = [
        c for c in preferred_order
        if c in df.columns
    ]

    other_cols = [
        c for c in df.columns
        if c not in final_cols
    ]

    df = df[final_cols + other_cols]

    return df


def render_prematch():

    st.subheader("🎯 PREMATCH")

    df = safe_load_csv(PREMATCH_FILE)

    if df.empty:
        st.warning("Brak danych PREMATCH")
        return

    df = cleanup_dataframe(df)

    st.success(f"Załadowano {len(df)} typów")

    st.dataframe(
        df,
        use_container_width=True,
        height=750
    )


tab1, tab2 = st.tabs([
    "🎯 PREMATCH",
    "📡 LIVE"
])

with tab1:
    render_prematch()

with tab2:
    st.info("LIVE będzie rozwijany w kolejnych etapach.")

st.caption(
    f"Ostatnie odświeżenie: {time.strftime('%Y-%m-%d %H:%M:%S')}"
)

time.sleep(30)
st.rerun()
