from __future__ import annotations

from modules.common import first_existing_file, read_csv_safe, numeric_series, write_json, write_csv

def run():
    source = first_existing_file([
        "data/auto_all_picks.csv",
        "data/ai_picks.csv",
        "data/history.csv",
    ])

    if not source:
        return write_json("risk_audit.json", {
            "module": "risk_audit",
            "status": "no_source_file"
        })

    df = read_csv_safe(source)
    stake = numeric_series(df, ["stake", "stake_pct", "Stake", "bet_size"])
    confidence = numeric_series(df, ["confidence", "Confidence", "ai_confidence", "model_confidence"])

    rows = []
    if len(stake.dropna()):
        rows.extend([
            {"metric": "stake_avg", "value": float(stake.mean())},
            {"metric": "stake_max", "value": float(stake.max())},
            {"metric": "stake_min", "value": float(stake.min())},
        ])

    if len(confidence.dropna()):
        rows.extend([
            {"metric": "confidence_avg", "value": float(confidence.mean())},
            {"metric": "low_confidence_count_lt_0_55", "value": int((confidence < 0.55).sum())},
        ])

    csv_path = write_csv("risk_audit.csv", rows)
    return write_json("risk_audit.json", {
        "module": "risk_audit",
        "status": "ok",
        "source": str(source),
        "rows": int(len(df)),
        "output_csv": str(csv_path),
        "note": "Audyt ryzyka tylko raportuje ekspozycję. Nie zmienia stakingu."
    })

if __name__ == "__main__":
    print(run())
