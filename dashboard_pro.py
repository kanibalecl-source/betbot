from shadow.shadow_logger import log_shadow_event
with open("styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ZAMIEŃ SEKCJĘ BANERA NA:

st.markdown("""
<div class="hero-banner">
    <img src="KANIBAL_ANALYTICS_BANNER.png">
</div>
""", unsafe_allow_html=True)

import streamlit as st
import pandas as pd

def run():
    st.subheader("🔥 TOP (PRO)")

    try:
        df = pd.read_csv("data/auto_all_picks.csv")
    except:
        st.warning("Brak danych")
        return

    if df.empty:
        st.warning("Brak typów")
        return

    if "edge" not in df.columns:
        st.warning("Brak kolumny edge")
        return

    st.dataframe(df, width="stretch")
