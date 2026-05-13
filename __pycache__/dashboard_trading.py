import streamlit as st
from trading_engine import load_bets, settle_bet

def run():

    st.subheader("💸 Trading / Zakłady")

    df = load_bets()

    if df.empty:
        st.info("Brak zakładów")
        return

    for i, row in df.iterrows():

        col1, col2, col3 = st.columns([5, 1, 1])

        col1.write(f"{row['mecz']} | {row['typ']} | kurs {row['kurs']}")

        if row["result"] == "OPEN":

            if col2.button(f"WIN_{i}"):
                settle_bet(i, "WIN")

            if col3.button(f"LOSE_{i}"):
                settle_bet(i, "LOSE")

        else:
            col2.write(row["result"])
            col3.write(row["pnl"])

    st.dataframe(df)