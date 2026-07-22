"""Train learned shadow weights from chronological, settled quality rows."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path

from quality_upgrade_engine import train_time_safe_state
from storage_paths import get_data_dir


def main() -> int:
    data_dir = get_data_dir()
    source = Path(os.getenv("BETBOT_QUALITY_TRAINING", data_dir / "quality_training.csv"))
    # Training creates an inert candidate. Runtime only reads
    # quality_shadow_state.json, so training can never activate itself.
    target = Path(
        os.getenv(
            "BETBOT_QUALITY_STATE_OUTPUT",
            data_dir / "quality_shadow_state.candidate.json",
        )
    )
    if not source.exists():
        print(f"NO TRAINING FILE: {source}")
        print(
            "Required columns: current_probability, dixon_coles_probability, "
            "market_probability, target"
        )
        return 2
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    state = train_time_safe_state(rows)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    if state.get("status") != "TRAINED_TIME_SAFE":
        return 3
    if target.exists() and os.getenv(
        "BETBOT_ALLOW_REPLACE_QUALITY_CANDIDATE", "0"
    ).strip().lower() not in {"1", "true", "yes", "on"}:
        print(f"CANDIDATE EXISTS, NOT OVERWRITTEN: {target}")
        return 4
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(temporary, target)
    print(f"SAVED INERT TIME-SAFE CANDIDATE: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
