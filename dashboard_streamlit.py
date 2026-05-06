import streamlit as st
import json

st.set_page_config(
    page_title="BOT TEST",
    layout="wide"
)

st.title("💰 BOT – PANEL TESTÓW")

try:
    with open("live_data.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    st.success("Dane LIVE załadowane ✅")

    st.json(data)

    st.subheader("⚽ MECZE LIVE")

    for match in data["matches"]:

        st.markdown("---")

        st.write(f"🏠 {match['home']}")
        st.write(f"🆚 {match['away']}")
        st.write(f"⏱ Minuta: {match['minute']}")
        st.write(f"📈 Typ: {match['prediction']}")
        st.write(f"🎯 Confidence: {match['confidence']}%")

except Exception as e:

    st.warning("Brak danych — uruchom bota")

    st.code(str(e))
