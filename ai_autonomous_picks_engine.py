"""Compatibility wrapper for autonomous AI picks.

The actual self-learning implementation lives in ai_self_learning_runtime.py.
This file is kept so the dashboard and older imports continue to work.
"""
from __future__ import annotations

from ai_self_learning_runtime import AI_COLUMNS, AI_PICKS_FILE, build_ai_picks, run_self_learning_cycle


def run_once(limit: int = 12) -> int:
    result = run_self_learning_cycle(limit=limit)
    return int(result.get("ai_picks", 0))


if __name__ == "__main__":
    run_once()
