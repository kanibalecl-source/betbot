from __future__ import annotations

from pathlib import Path

REQUIRED_FILES = [
    "app_launcher.py", "scheduler_engine.py", "bot.py", "dashboard_streamlit.py",
    "data_api.py", "manual_betting.py", "agi_storage.py", "persistence_runtime.py",
    "settle_loop.py", "live_pipeline_runtime.py", "config_strategy.json",
]

def check(base_dir: str | Path | None = None) -> dict:
    base = Path(base_dir or Path(__file__).resolve().parents[2])
    missing = [name for name in REQUIRED_FILES if not (base / name).exists()]
    return {"ok": not missing, "missing": missing, "base_dir": str(base)}

if __name__ == "__main__":
    print(check())
