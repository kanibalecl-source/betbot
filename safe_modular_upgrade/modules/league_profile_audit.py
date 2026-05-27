from __future__ import annotations

from modules.common import first_existing_file, read_csv_safe, numeric_series, write_json, write_csv

def run():
    source = first_existing_file([
        "data/auto_all_picks.csv",
        "data/ai_picks.csv",
        "data/results_history.csv",
        "data/history.csv",
    ])

    if not source:
        return write_json("league_profile_audit.json", {
            "module": "league_profile_audit",
            "status": "no_source_file"
        })

    df = read_csv_safe(source)
    league_col = next((c for c in ["league", "League", "competition", "Competition"] if c in df.columns), None)

    if not league_col:
        return write_json("league_profile_audit.json", {
            "module": "league_profile_audit",
            "status": "no_league_column",
            "source": str(source),
            "columns": list(df.columns)
        })

    edge = numeric_series(df, ["edge", "Edge", "true_edge"])
    confidence = numeric_series(df, ["confidence", "Confidence", "ai_confidence", "model_confidence"])
    df["_edge_numeric"] = edge
    df["_confidence_numeric"] = confidence

    rows = []
    for league, g in df.groupby(league_col, dropna=False):
        rows.append({
            "league": str(league),
            "rows": int(len(g)),
            "avg_edge": float(g["_edge_numeric"].mean()) if g["_edge_numeric"].notna().any() else None,
            "avg_confidence": float(g["_confidence_numeric"].mean()) if g["_confidence_numeric"].notna().any() else None,
        })

    csv_path = write_csv("league_profile_audit.csv", rows)
    return write_json("league_profile_audit.json", {
        "module": "league_profile_audit",
        "status": "ok",
        "source": str(source),
        "league_column": league_col,
        "output_csv": str(csv_path),
        "league_count": len(rows),
        "note": "Audyt ligowy tylko agreguje dane historyczne. Nie zmienia progów ani filtrów bota."
    })

if __name__ == "__main__":
    print(run())
