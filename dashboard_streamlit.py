import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(layout="wide")

DATA_FILE = Path("data/auto_all_picks.csv")


def load_data():
    if not DATA_FILE.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(DATA_FILE)
    except:
        return pd.DataFrame()


# 🔥 ZABEZPIECZENIE PRZED BRAKIEM KOLUMN
def ensure_columns(df):
    required = [
        "data_analizy",
        "liga",
        "mecz",
        "typ",
        "kod_rynku",
        "kurs_buk",
        "prawd_bota",
        "kurs_bota",
        "edge",
        "ocena",
        "stawka_pln"
    ]

    for col in required:
        if col not in df.columns:
            df[col] = ""

    return df


def render_table(df, title):
    st.subheader(title)

    if df.empty:
        st.write("Brak danych")
        return

    html = """
    <style>
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th { background: black; color: white; padding: 8px; }
    td { padding: 6px; text-align: center; color: white; }
    </style>
    <table><tr>
    """

    for col in df.columns:
        html += f"<th>{col}</th>"
    html += "</tr>"

    for _, row in df.iterrows():
        ocena = str(row.get("ocena", "")).upper()

        if ocena == "SAFE":
            color = "#0f5132"
        elif ocena == "LOW":
            color = "#8a6d1d"
        else:
            color = "#8b1e1e"

        html += f"<tr style='background-color:{color}'>"

        for col in df.columns:
            html += f"<td>{row[col]}</td>"

        html += "</tr>"

    html += "</table>"

    st.markdown(html, unsafe_allow_html=True)


def split_mecz(df):
    return df[df["kod_rynku"].isin([
        "HOME_WIN", "DRAW", "AWAY_WIN",
        "HOME_OR_DRAW", "AWAY_OR_DRAW", "HOME_OR_AWAY"
    ])]


def split_gole(df):
    return df[df["kod_rynku"].astype(str).str.contains("OVER|UNDER", na=False)]


def split_btts(df):
    return df[df["kod_rynku"].isin(["BTTS_YES", "BTTS_NO"])]


st.title("💰 BOT – PANEL TESTÓW")

df = load_data()

if df.empty:
    st.warning("Brak danych — uruchom bota")
    st.stop()

df = ensure_columns(df)

df = df.sort_values(by="edge", ascending=False)

st.header("🔥 TOP 3")
render_table(df.head(3), "Najlepsze typy")

st.markdown("---")

st.header("🟦 MECZ")
render_table(split_mecz(df), "Mecz")

st.markdown("---")

st.header("🟩 GOLE")
render_table(split_gole(df), "Gole")

st.markdown("---")

st.header("⚽ BTTS")
render_table(split_btts(df), "BTTS")