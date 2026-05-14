import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="KANIBAL ANALYTICS", layout="wide")

# LOAD CSS
css_path = Path("styles.css")
if css_path.exists():
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# HERO BANNER
st.markdown("""
<div class="hero-banner">
    <img src="https://i.imgur.com/3KXQk6x.jpeg">
</div>
""", unsafe_allow_html=True)

tabs = st.tabs([
    "🚨 NA ŻYWO",
    "⚽ PRZEDMECZOWE",
    "🧠 AI",
    "📊 ANALITYKA",
    "📜 HISTORIA",
    "🔔 ALERTY"
])

with tabs[0]:
    st.markdown("## 🚨 SYGNAŁY NA ŻYWO")
    live_path = Path("data/live_matches.csv")

    if live_path.exists():
        try:
            df = pd.read_csv(live_path)
            if len(df) > 0:
                st.dataframe(df, use_container_width=True)
            else:
                st.info("Brak aktywnych meczów LIVE.")
        except Exception as e:
            st.error(f"Błąd LIVE: {e}")
    else:
        st.warning("Brak pliku data/live_matches.csv")

with tabs[1]:
    st.markdown("## ⚽ PRZEDMECZOWE")
    picks_path = Path("data/auto_all_picks.csv")

    if picks_path.exists():
        try:
            df = pd.read_csv(picks_path)
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"Błąd PREMATCH: {e}")

with tabs[2]:
    st.markdown("## 🧠 AI ENGINE")
    st.success("AI / Learning Engine aktywny")

with tabs[3]:
    st.markdown("## 📊 ANALITYKA")
    st.info("Analytics engine aktywny")

with tabs[4]:
    st.markdown("## 📜 HISTORIA")
    history_path = Path("data/results_history.csv")

    if history_path.exists():
        try:
            df = pd.read_csv(history_path)
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"Błąd historii: {e}")

with tabs[5]:
    st.markdown("## 🔔 ALERTY")
    st.info("Alert system aktywny")
