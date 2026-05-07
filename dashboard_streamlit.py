import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="BETBOT AI",
    layout="wide"
)

st.title("⚽ BETBOT AI")

# =========================
# PREMATCH PICKS
# =========================

st.header("📊 PREMATCH PICKS")

prematch_file = Path("data/auto_all_picks.csv")

if prematch_file.exists():

    prematch_df = pd.read_csv(prematch_file)

    prematch_df = prematch_df.drop(
        columns=["pick_id", "odds_event_id"],
        errors="ignore"
    )

    st.dataframe(
        prematch_df,
        use_container_width=True,
        height=min(400, 35 * len(prematch_df) + 80)
    )

else:
    st.warning("Brak danych PREMATCH")

# =========================
# LIVE MATCHES
# =========================

st.header("🔴 LIVE MATCHES")

live_file = Path("data/live_matches.csv")

if live_file.exists():

    live_df = pd.read_csv(live_file)

    st.dataframe(
        live_df,
        use_container_width=True,
        height=min(600, 35 * len(live_df) + 80)
    )

else:
    st.warning("Brak danych LIVE")
