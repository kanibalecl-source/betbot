import streamlit as st
import pandas as pd
from pathlib import Path
import time

st.set_page_config(
    page_title="BetBot Dashboard",
    layout="wide"
)

DATA_DIR = Path("data")

AUTO_FILE = DATA_DIR / "auto_all_picks.csv"

st.title("📊 BETBOT DASHBOARD")


def safe_load_csv(path):

    if not path.exists():
        return pd.DataFrame()

    try:

        df = pd.read_csv(path)

        # =========================
        # FIX BIAŁEJ STRONY
        # =========================

        df = df.fillna("")

        for col in df.columns:

            try:
                df[col] = df[col].astype(str)
            except Exception:
                pass

        return df

    except Exception as e:

        st.error(f"CSV ERROR: {e}")

        return pd.DataFrame()


while True:

    st.subheader("🎯 PREMATCH PICKS")

    df = safe_load_csv(AUTO_FILE)

    if df.empty:

        st.warning("Brak danych")

    else:

        st.success(f"Załadowano {len(df)} typów")

        st.dataframe(
            df,
            use_container_width=True,
            height=700
        )

    st.caption(
        f"Ostatnie odświeżenie: {time.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    time.sleep(30)

    st.rerun()
