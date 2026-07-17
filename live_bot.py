"""Compatibility entry point for the strict real-data LIVE pipeline.

Legacy heuristic confidence, risk, stake and cash-out defaults were removed. Running
this module now uses the same verified provider path as the dashboard and scheduler.
"""

from live_pipeline_runtime import fetch_live_matches, main, run_once

get_live_matches = fetch_live_matches

__all__ = ["fetch_live_matches", "get_live_matches", "run_once", "main"]


if __name__ == "__main__":
    main()
