"""Compatibility entry point for the strict real-data LIVE pipeline.

The previous implementation maintained a second writer for live_matches.csv and could
silently keep stale data. All LIVE writes now go through live_pipeline_runtime.
"""

from live_pipeline_runtime import fetch_live_matches, main, run_once

get_live_matches = fetch_live_matches

__all__ = ["fetch_live_matches", "get_live_matches", "run_once", "main"]


if __name__ == "__main__":
    main()
