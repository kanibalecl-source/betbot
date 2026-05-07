import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="BETBOT AI",
    layout="wide"
)

# =========================
# HEADER
# =========================

st.title("⚽ BETBOT AI DASHBOARD")

st.markdown("---")

# =========================
# PREMATCH PICKS
# =========================

st.header("📊 PREMATCH PICKS")

prematch_file = Path("data/auto_all_picks.csv")

if prematch_file.exists():

    try:
        prematch_df = pd.read_csv(prematch_file)

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

        st.success(f"Załadowano {len(prematch_df)} prematch picks")

        st.dataframe(
            prematch_df,
            use_container_width=True,
            height=min(400, 35 * len(prematch_df) + 80)
        )

    except Exception as e:
        st.error(f"Błąd PREMATCH: {e}")

else:
    st.warning("Brak danych PREMATCH")

st.markdown("---")

# =========================
# LIVE MATCHES
# =========================

st.header("🔴 LIVE MATCHES")

live_file = Path("data/live_matches.csv")

if live_file.exists():

    try:
        live_df = pd.read_csv(live_file)

        st.success(f"Aktywne mecze LIVE: {len(live_df)}")

        st.dataframe(
            live_df,
            use_container_width=True,
            height=min(600, 35 * len(live_df) + 80)
        )

    except Exception as e:
        st.error(f"Błąd LIVE: {e}")

else:
    st.warning("Brak danych LIVE")

st.markdown("---")

# =========================
# FOOTER
# =========================

st.caption("BETBOT AI • LIVE ENGINE ACTIVE 🚀")
