"""Validated compatibility storage for LIVE rows.

This module no longer supplies default status, risk, confidence or score values.
"""

from typing import Any, Dict, Iterable, List

import pandas as pd

from live_pipeline_runtime import ACTIVE_STATUSES, LIVE_FILE, LiveDataError, save_live_matches


def is_live_match(match: Dict[str, Any]) -> bool:
    status = str(match.get("status") or "").upper().strip()
    source = str(match.get("source") or "")
    data_status = str(match.get("data_status") or "")
    try:
        minute = int(float(match.get("minute")))
    except (TypeError, ValueError):
        return False
    return bool(
        status in ACTIVE_STATUSES
        and 0 <= minute < 130
        and source.startswith("API-Football")
        and data_status.startswith("VERIFIED_FIXTURE")
        and match.get("fixture_id") is not None
        and str(match.get("match") or "").strip()
        and str(match.get("score") or "").strip()
    )


class LiveEngine:
    def save_live_matches(self, matches: Iterable[Dict[str, Any]]) -> None:
        rows: List[Dict[str, Any]] = list(matches or [])
        invalid = [row for row in rows if not is_live_match(row)]
        if invalid:
            raise LiveDataError("Refusing to save unverified LIVE rows")
        save_live_matches(rows)

    def load_live_matches(self) -> List[Dict[str, Any]]:
        if not LIVE_FILE.exists() or LIVE_FILE.stat().st_size == 0:
            return []
        frame = pd.read_csv(LIVE_FILE)
        if frame.empty:
            return []
        return [row for row in frame.to_dict(orient="records") if is_live_match(row)]
