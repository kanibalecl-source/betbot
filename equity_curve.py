import pandas as pd


def build_equity(df: pd.DataFrame, pnl_col: str = "pnl", date_col: str = "data_rozliczenia") -> pd.DataFrame:
    if df.empty or pnl_col not in df.columns:
        return pd.DataFrame()

    out = df.copy()
    out[pnl_col] = pd.to_numeric(out[pnl_col], errors="coerce").fillna(0)

    if date_col in out.columns:
        out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
        out = out.sort_values(by=date_col, ascending=True)

    out["equity"] = out[pnl_col].cumsum()
    return out
