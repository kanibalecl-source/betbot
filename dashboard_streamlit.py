import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="BETBOT LIVE",
    layout="wide"
)

DATA_FILE = Path("data/auto_all_picks.csv")


def load_data():

    if not DATA_FILE.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(DATA_FILE)

    except Exception as e:
        st.error(f"Błąd odczytu CSV: {e}")
        return pd.DataFrame()


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
        st.warning("Brak danych")
        return

    html = """
    <style>
    table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
    }

    th {
        background: #111827;
        color: white;
        padding: 10px;
    }

    td {
        padding: 8px;
        text-align: center;
        color: white;
    }
    </style>

    <table>
    <tr>
    """

    for col in df.columns:
        html += f"<th>{col}</th>"

    html += "</tr>"

    for _, row in df.iterrows():

        ocena = str(row.get("ocena", "")).upper()

        if ocena == "SAFE":
            color = "#065f46"

        elif ocena == "LOW":
            color = "#92400e"

        elif ocena == "LIVE":
            color = "#1d4ed8"

        else:
            color = "#7f1d1d"

        html += f"<tr style='background-color:{color}'>"

        for col in df.columns:
            html += f"<td>{row[col]}</td>"

        html += "</tr>"

    html += "</table>"

    st.markdown(html, unsafe_allow_html=True)


def split_live(df):

    return df[df["kod_rynku"] == "LIVE"]


def split_mecz(df):

    return df[df["kod_rynku"].isin([
        "HOME_WIN",
        "DRAW",
        "AWAY_WIN",
        "HOME_OR_DRAW",
        "AWAY_OR_DRAW",
        "HOME_OR_AWAY"
    ])]


def split_gole(df):

    return df[
        df["kod_rynku"].astype(str).str.contains(
            "OVER|UNDER",
            na=False
        )
    ]


def split_btts(df):

    return df[
        df["kod_rynku"].isin([
            "BTTS_YES",
            "BTTS_NO"
        ])
    ]


st.title("🚀 BETBOT LIVE")

st.caption("Panel LIVE • Railway Production")

df = load_data()

if df.empty:

    st.warning("Brak danych LIVE — bot jeszcze nie wygenerował typów")

    st.stop()

df = ensure_columns(df)

try:
    df = df.sort_values(by="edge", ascending=False)

except:
    pass


# 🔥 LIVE
st.header("⚡ LIVE SIGNALS")

render_table(
    split_live(df),
    "LIVE"
)

st.markdown("---")


# 🔥 TOP
st.header("🔥 TOP PICKS")

render_table(
    df.head(5),
    "Najlepsze typy"
)

st.markdown("---")


# 🔥 MECZ
st.header("🟦 MECZ")

render_table(
    split_mecz(df),
    "Mecz"
)

st.markdown("---")


# 🔥 GOLE
st.header("🟩 GOLE")

render_table(
    split_gole(df),
    "Gole"
)

st.markdown("---")


# 🔥 BTTS
st.header("⚽ BTTS")

render_table(
    split_btts(df),
    "BTTS"
)

st.markdown("---")

st.success("System LIVE działa poprawnie ✅")
