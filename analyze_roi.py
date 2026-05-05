import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
HISTORY_FILE = DATA_DIR / "history_results.csv"


def load_history() -> pd.DataFrame:
    if not HISTORY_FILE.exists():
        print("❌ Brak pliku history_results.csv")
        return pd.DataFrame()

    try:
        df = pd.read_csv(HISTORY_FILE)
    except Exception as e:
        print(f"❌ Błąd odczytu pliku: {e}")
        return pd.DataFrame()

    required_cols = [
        "liga",
        "kod_rynku",
        "ocena",
        "stawka_pln",
        "pnl",
        "settlement",
        "kurs_buk",
    ]

    for col in required_cols:
        if col not in df.columns:
            df[col] = None

    df["stawka_pln"] = pd.to_numeric(df["stawka_pln"], errors="coerce").fillna(0.0)
    df["pnl"] = pd.to_numeric(df["pnl"], errors="coerce").fillna(0.0)
    df["kurs_buk"] = pd.to_numeric(df["kurs_buk"], errors="coerce")

    return df


def calc_roi(df: pd.DataFrame) -> float:
    stake_sum = df["stawka_pln"].sum()
    if stake_sum <= 0:
        return 0.0
    return round((df["pnl"].sum() / stake_sum) * 100, 2)


def calc_win_rate(df: pd.DataFrame) -> float:
    bets = len(df)
    if bets == 0:
        return 0.0
    wins = (df["settlement"] == "WIN").sum()
    return round((wins / bets) * 100, 2)


def summary_block(df: pd.DataFrame, title: str):
    bets = len(df)
    wins = (df["settlement"] == "WIN").sum()
    losses = (df["settlement"] == "LOSE").sum()
    pnl = round(df["pnl"].sum(), 2)
    stake = round(df["stawka_pln"].sum(), 2)
    roi = calc_roi(df)
    wr = calc_win_rate(df)
    avg_odds = round(df["kurs_buk"].dropna().mean(), 2) if not df["kurs_buk"].dropna().empty else 0.0

    print("=" * 60)
    print(title)
    print("=" * 60)
    print(f"Liczba zakładów : {bets}")
    print(f"Wygrane         : {wins}")
    print(f"Przegrane       : {losses}")
    print(f"Stawki razem    : {stake} PLN")
    print(f"PNL             : {pnl} PLN")
    print(f"ROI             : {roi}%")
    print(f"Win rate        : {wr}%")
    print(f"Średni kurs     : {avg_odds}")
    print()


def grouped_report(df: pd.DataFrame, group_col: str, min_bets: int = 3):
    print("=" * 60)
    print(f"ANALIZA WG: {group_col}")
    print("=" * 60)

    rows = []

    for key, part in df.groupby(group_col):
        if len(part) < min_bets:
            continue

        rows.append({
            group_col: key,
            "bets": len(part),
            "wins": int((part["settlement"] == "WIN").sum()),
            "losses": int((part["settlement"] == "LOSE").sum()),
            "stake_sum": round(part["stawka_pln"].sum(), 2),
            "pnl_sum": round(part["pnl"].sum(), 2),
            "roi": calc_roi(part),
            "win_rate": calc_win_rate(part),
            "avg_odds": round(part["kurs_buk"].dropna().mean(), 2) if not part["kurs_buk"].dropna().empty else 0.0,
        })

    if not rows:
        print("Brak wystarczających danych.\n")
        return

    out = pd.DataFrame(rows).sort_values(by="roi", ascending=False)
    print(out.to_string(index=False))
    print()


def top_bottom_report(df: pd.DataFrame, group_col: str, min_bets: int = 3):
    rows = []

    for key, part in df.groupby(group_col):
        if len(part) < min_bets:
            continue

        rows.append({
            group_col: key,
            "bets": len(part),
            "roi": calc_roi(part),
            "pnl": round(part["pnl"].sum(), 2),
        })

    if not rows:
        return

    out = pd.DataFrame(rows).sort_values(by="roi", ascending=False)

    print("=" * 60)
    print(f"TOP 5 / BOTTOM 5 WG: {group_col}")
    print("=" * 60)
    print("TOP 5:")
    print(out.head(5).to_string(index=False))
    print()
    print("BOTTOM 5:")
    print(out.tail(5).sort_values(by="roi", ascending=True).to_string(index=False))
    print()


def main():
    df = load_history()

    if df.empty:
        print("❌ Brak danych do analizy.")
        return

    # tylko rozliczone zakłady
    df = df[df["settlement"].isin(["WIN", "LOSE"])].copy()

    if df.empty:
        print("❌ Brak rozliczonych zakładów.")
        return

    summary_block(df, "PODSUMOWANIE GLOBALNE")

    # SAFE / LOW / RISK
    grouped_report(df, "ocena", min_bets=1)

    # Rynki
    grouped_report(df, "kod_rynku", min_bets=3)
    top_bottom_report(df, "kod_rynku", min_bets=3)

    # Ligi
    grouped_report(df, "liga", min_bets=3)
    top_bottom_report(df, "liga", min_bets=3)

    # Dodatkowy szybki wniosek
    print("=" * 60)
    print("WNIOSKI ROBOCZE")
    print("=" * 60)

    if "ocena" in df.columns:
        for rating in ["SAFE", "LOW", "RISK"]:
            part = df[df["ocena"] == rating]
            if len(part) == 0:
                continue
            print(f"{rating}: ROI={calc_roi(part)}% | Bets={len(part)} | WR={calc_win_rate(part)}%")

    print()
    print("✅ Analiza zakończona.")


if __name__ == "__main__":
    main()