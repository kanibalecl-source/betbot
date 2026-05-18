"""Compatibility wrapper for autonomous AI runtime.

Kept for existing imports. Real generation is handled by ai_autonomous_picks_engine.
"""
from ai_autonomous_picks_engine import run_once

def bootstrap_ai_picks():
    return run_once()

if __name__ == "__main__":
    bootstrap_ai_picks()
