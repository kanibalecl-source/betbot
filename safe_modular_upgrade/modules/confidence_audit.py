from __future__ import annotations

from modules.common import first_existing_file, read_csv_safe, numeric_series, write_json

def run():
    source = first_existing_file([
        "data/auto_all_picks.csv",
        "data/ai_picks.csv",
        "data/history.csv",
    ])

    if not source:
        return write_json("confidence_audit.json", {
            "module": "confidence_audit",
            "status": "no_source_file",
            "message": "Nie znaleziono pliku picków do audytu confidence."
        })

    df = read_csv_safe(source)
    confidence = numeric_series(df, ["confidence", "Confidence", "ai_confidence", "model_confidence"])
    edge = numeric_series(df, ["edge", "Edge", "true_edge"])
    ev = numeric_series(df, ["ev", "EV", "expected_value"])

    payload = {
        "module": "confidence_audit",
        "status": "ok",
        "source": str(source),
        "rows": int(len(df)),
        "columns": list(df.columns),
        "confidence_available": bool(len(confidence.dropna())),
        "confidence_mean": float(confidence.mean()) if len(confidence.dropna()) else None,
        "confidence_min": float(confidence.min()) if len(confidence.dropna()) else None,
        "confidence_max": float(confidence.max()) if len(confidence.dropna()) else None,
        "edge_mean": float(edge.mean()) if len(edge.dropna()) else None,
        "ev_mean": float(ev.mean()) if len(ev.dropna()) else None,
        "note": "Moduł tylko analizuje istniejące dane. Nie zmienia picków ani confidence w runtime."
    }
    return write_json("confidence_audit.json", payload)

if __name__ == "__main__":
    print(run())
