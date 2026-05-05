from pathlib import Path
from datetime import datetime
import pandas as pd

from database import get_conn, init_db

REPORT_DIR = Path(__file__).parent / "reports"
REPORT_DIR.mkdir(exist_ok=True)


def main():
    init_db()
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM bets WHERE status = 'CLOSED'", conn)
    conn.close()

    if df.empty:
        print("Brak zamkniętych betów do raportu.")
        return

    total_stake = df["stake"].sum()
    total_profit = df["profit"].sum()
    roi = total_profit / total_stake if total_stake else 0
    winrate = (df["result"] == "WIN").mean()

    by_market = df.groupby("market").agg(
        bets=("id", "count"),
        stake=("stake", "sum"),
        profit=("profit", "sum"),
        avg_ev=("ev", "mean"),
        avg_edge=("edge", "mean"),
        avg_clv=("clv", "mean"),
    ).reset_index()

    by_market["roi"] = by_market["profit"] / by_market["stake"]

    month = datetime.now().strftime("%Y-%m")
    csv_path = REPORT_DIR / f"monthly_report_{month}.csv"
    html_path = REPORT_DIR / f"monthly_report_{month}.html"

    by_market.to_csv(csv_path, index=False)

    html = f"""
    <html>
    <head><meta charset='utf-8'><title>Raport miesięczny</title></head>
    <body>
    <h1>Raport miesięczny {month}</h1>
    <p><b>Liczba betów:</b> {len(df)}</p>
    <p><b>Suma stawek:</b> {total_stake:.2f}</p>
    <p><b>Profit:</b> {total_profit:.2f}</p>
    <p><b>ROI:</b> {roi:.2%}</p>
    <p><b>Winrate:</b> {winrate:.2%}</p>
    <h2>Wyniki według rynku</h2>
    {by_market.to_html(index=False)}
    </body>
    </html>
    """

    html_path.write_text(html, encoding="utf-8")

    print(f"Zapisano raport CSV: {csv_path}")
    print(f"Zapisano raport HTML: {html_path}")


if __name__ == "__main__":
    main()
