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