```python
import streamlit as st
import pandas as pd
from pathlib import Path

# =========================
# CONFIG
# =========================

st.set_page_config(
    page_title="KANIBAL ANALYTICS",
    layout="wide",
    initial_sidebar_state="collapsed"
)

DATA_DIR = Path("data")

PREMATCH_FILE = DATA_DIR / "auto_all_picks.csv"
LIVE_FILE = DATA_DIR / "live_matches.csv"
BANNER_FILE = Path("kanibal_banner_pro.webp")

# =========================
# DATA
# =========================

def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def only_existing_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    existing = [col for col in columns if col in df.columns]
    if not existing:
        return df
    return df[existing]


live_df = load_csv(LIVE_FILE)
prematch_df = load_csv(PREMATCH_FILE)

# =========================
# SAFE CSS ONLY
# =========================

st.markdown(
    """
    <style>
        .stApp {
            background:
                radial-gradient(circle at top right, rgba(81,255,0,0.12), transparent 28%),
                radial-gradient(circle at top left, rgba(255,80,0,0.08), transparent 26%),
                linear-gradient(180deg, #050607 0%, #090b0d 45%, #050607 100%);
            color: white;
        }

        header[data-testid="stHeader"] {
            background: transparent;
        }

        .block-container {
            max-width: 100% !important;
            padding-top: 0.6rem;
            padding-left: 2rem;
            padding-right: 2rem;
        }

        h1, h2, h3 {
            color: white !important;
            font-weight: 900 !important;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0;
            background: #090b0d;
            border-radius: 14px;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.08);
            margin-top: 16px;
            margin-bottom: 24px;
            width: 100%;
        }

        .stTabs [data-baseweb="tab"] {
            height: 68px;
            background: #090b0d;
            color: white;
            font-weight: 800;
            font-size: 13px;
            border-right: 1px solid rgba(255,255,255,0.06);
            flex-grow: 1;
        }

        .stTabs [aria-selected="true"] {
            background:
                linear-gradient(
                    180deg,
                    rgba(88,255,47,0.15),
                    rgba(88,255,47,0.05)
                ) !important;
            color: #58ff2f !important;
            border-bottom: 3px solid #58ff2f !important;
        }

        div[data-testid="stVerticalBlockBorderWrap
```
