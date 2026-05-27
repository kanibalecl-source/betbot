from __future__ import annotations

from modules.common import first_existing_file, read_csv_safe, numeric_series, write_json

def run():
    source = first_existing_file([
        "data/clv_history.csv",
        "data/auto_all_picks.csv",
        "data/history.csv",
    ])

    if not source:
        return write_json("clv_audit.json", {
            "module": "clv_audit",
            "status": "no_source_file"
        })

    df = read_csv_safe(source)
    clv = numeric_series(df, ["clv", "CLV", "closing_line_value"])
    opening = numeric_series(df, ["opening_odds", "open_odds"])
    closing = numeric_series(df, ["closing_odds", "close_odds"])

    payload = {
        "module": "clv_audit",
        "status": "ok",
        "source": str(source),
        "rows": int(len(df)),
        "clv_available": bool(len(clv.dropna())),
        "avg_clv": float(clv.mean()) if len(clv.dropna()) else None,
        "positive_clv_count": int((clv > 0).sum()) if len(clv.dropna()) else None,
        "opening_odds_available": bool(len(opening.dropna())),
        "closing_odds_available": bool(len(closing.dropna())),
        "note": "Moduł tylko mierzy CLV. Nie wpływa na ranking ani decyzje BET/PASS."
    }
    return write_json("clv_audit.json", payload)

if __name__ == "__main__":
    print(run())
