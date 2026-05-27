from __future__ import annotations

from modules.common import first_existing_file, read_csv_safe, numeric_series, write_json, write_csv

def run():
    source = first_existing_file([
        "data/odds_history.csv",
        "data/clv_history.csv",
        "data/auto_all_picks.csv",
    ])

    if not source:
        return write_json("market_movement_audit.json", {
            "module": "market_movement_audit",
            "status": "no_source_file"
        })

    df = read_csv_safe(source)
    opening = numeric_series(df, ["opening_odds", "open_odds"])
    current = numeric_series(df, ["odds", "current_odds", "kurs"])
    closing = numeric_series(df, ["closing_odds", "close_odds"])

    rows = []
    if len(opening.dropna()) and len(current.dropna()):
        diff = current - opening
        rows.append({"metric": "current_minus_opening_avg", "value": float(diff.mean())})
        rows.append({"metric": "current_minus_opening_abs_avg", "value": float(diff.abs().mean())})

    if len(opening.dropna()) and len(closing.dropna()):
        diff = closing - opening
        rows.append({"metric": "closing_minus_opening_avg", "value": float(diff.mean())})
        rows.append({"metric": "closing_minus_opening_abs_avg", "value": float(diff.abs().mean())})

    csv_path = write_csv("market_movement_audit.csv", rows)
    return write_json("market_movement_audit.json", {
        "module": "market_movement_audit",
        "status": "ok",
        "source": str(source),
        "rows": int(len(df)),
        "output_csv": str(csv_path),
        "note": "Moduł analizuje ruch kursów offline. Nie wykrywa ani nie blokuje picków w runtime."
    })

if __name__ == "__main__":
    print(run())
