import streamlit as st
from trading_engine import load_bets

def run():

    st.subheader("📈 ROI")

    df = load_bets()

    if df.empty:
        st.warning("Brak danych")
        return

    stake = df["stawka"].sum()
    pnl = df["pnl"].sum()

    roi = (pnl / stake * 100) if stake > 0 else 0

    st.metric("💰 Zysk", round(pnl, 2))
    st.metric("📊 ROI", f"{round(roi,2)}%")

    st.dataframe(df)