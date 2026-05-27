from shadow.shadow_logger import log_shadow_event
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
        st.warning("Brak typów PRO")
        return

    st.dataframe(df, use_container_width=True)