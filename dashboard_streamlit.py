import streamlit as st

with open("styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Wklej poniżej resztę swojego oryginalnego dashboard_streamlit.py
