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
# PREMATCH SECTION
# =========================

st.subheader("📊 PREMATCH PICKS")

prematch_file = Path("data/auto_all_picks.csv")

if prematch_file.exists():

    try:
        prematch_df = pd.read_csv(prematch_file)

        st.success(f"Załadowano {len(prematch_df)} prematch picks")

        st.dataframe(
            prematch_df,
            use_container_width=True,
            height=400
        )

    except Exception as e:
        st.error(f"Błąd PREMATCH: {e}")

else:
    st.warning("Brak danych PREMATCH")

st.markdown("---")

# =========================
# LIVE SECTION
# =========================

st.subheader("🔴 LIVE MATCHES")

live_file = Path("data/live_matches.csv")

if live_file.exists():

    try:
        live_df = pd.read_csv(live_file)

        st.success(f"Aktywne mecze LIVE: {len(live_df)}")

        st.dataframe(
            live_df,
            use_container_width=True,
            height=500
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
