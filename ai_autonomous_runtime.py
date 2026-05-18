"""Runtime entrypoint for autonomous self-learning AI."""
from __future__ import annotations

from ai_self_learning_runtime import run_self_learning_cycle


def bootstrap_ai_picks(limit: int = 12) -> int:
    """Backward-compatible name used by older scheduler patches."""
    result = run_self_learning_cycle(limit=limit)
    return int(result.get("ai_picks", 0))


def run_once(limit: int = 12) -> int:
    return bootstrap_ai_picks(limit=limit)


if __name__ == "__main__":
    run_once()
