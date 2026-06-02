from __future__ import annotations

from pathlib import Path
import pandas as pd

def read_csv_safe(path: Path) -> pd.DataFrame:
    try:
        path = Path(path)
        if path.exists() and path.stat().st_size > 0:
            return pd.read_csv(path)
    except Exception:
        try:
            return pd.read_csv(path, encoding="utf-8")
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

def normalize_streamlit_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    for col in out.columns:
        out[col] = out[col].astype(str) if out[col].dtype == object else out[col]
    return out
