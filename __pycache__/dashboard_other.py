import streamlit as st
import pandas as pd

def run():
    st.subheader("📊 Pozostałe typy")

    try:
        df = pd.read_csv("data/other_picks.csv")
    except:
        st.warning("Brak danych")
        return

    if df.empty:
        st.warning("Brak danych")
        return

    st.dataframe(df, use_container_width=True)