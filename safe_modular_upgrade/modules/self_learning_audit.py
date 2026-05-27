from __future__ import annotations

from pathlib import Path
from modules.common import project_root, write_json

def run():
    root = project_root()
    candidates = [
        "data/ai_learning/ai_model_state.json",
        "data/ai_learning/ai_feature_store.csv",
        "data/ai_learning/ai_learning_events.csv",
        "data/ai_learning/ai_runtime_debug.json",
        "learning_data",
        "data/history.csv",
        "data/results_history.csv",
    ]

    found = []
    for rel in candidates:
        p = root / rel
        if p.exists():
            if p.is_file():
                found.append({"path": rel, "type": "file", "size": p.stat().st_size})
            elif p.is_dir():
                found.append({"path": rel, "type": "directory", "files": len([x for x in p.rglob("*") if x.is_file()])})

    return write_json("self_learning_audit.json", {
        "module": "self_learning_audit",
        "status": "ok",
        "found_learning_assets": found,
        "self_learning_assets_detected": bool(found),
        "note": "Moduł tylko sprawdza obecność danych uczenia. Nie uruchamia retrainingu ani nie zmienia state."
    })

if __name__ == "__main__":
    print(run())
