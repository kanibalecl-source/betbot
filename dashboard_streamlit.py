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

    st.subheader("⚽ MECZE LIVE")

    for match in data["matches"]:

        st.markdown("---")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Mecz",
                f"{match['home']} vs {match['away']}"
            )

        with col2:
            st.metric(
                "Minuta",
                match['minute']
            )

        with col3:
            st.metric(
                "Confidence",
                f"{match['confidence']}%"
            )

        st.success(
            f"📈 Typ LIVE: {match['prediction']}"
        )

except Exception as e:

    st.warning("Brak danych — uruchom bota")

    st.code(str(e))
