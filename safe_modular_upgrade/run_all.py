from __future__ import annotations

import sys
from pathlib import Path

# Allow running as: python safe_modular_upgrade/run_all.py
CURRENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CURRENT_DIR))

from modules import (
    confidence_audit,
    league_profile_audit,
    clv_audit,
    market_movement_audit,
    risk_audit,
    self_learning_audit,
)

def run_all():
    results = []
    for module in [
        confidence_audit,
        league_profile_audit,
        clv_audit,
        market_movement_audit,
        risk_audit,
        self_learning_audit,
    ]:
        try:
            path = module.run()
            results.append(str(path))
            print(f"OK: {module.__name__} -> {path}")
        except Exception as exc:
            print(f"ERROR: {module.__name__}: {exc}")
    return results

if __name__ == "__main__":
    run_all()
