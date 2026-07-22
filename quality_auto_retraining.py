"""Controlled QUALITY SHADOW retraining with an immutable active-model boundary."""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from build_quality_training_from_history import build
from quality_champion_challenger import walk_forward_validate
from quality_upgrade_engine import BetaCalibrator, train_time_safe_state
from storage_paths import get_data_dir


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return dict(value) if isinstance(value, Mapping) else {}
    except Exception:
        return {}


def _atomic_json(path: Path, payload: Mapping[str, Any], *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _append_event(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _training_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _target(row: Mapping[str, Any]) -> int | None:
    value = str(row.get("target", "")).strip().upper()
    if value in {"1", "TRUE", "WON", "WIN"}:
        return 1
    if value in {"0", "FALSE", "LOST", "LOSS"}:
        return 0
    return None


def _clean_rows(rows: Iterable[Mapping[str, Any]]) -> list[tuple[list[float], int]]:
    clean: list[tuple[list[float], int]] = []
    keys = ("current_probability", "dixon_coles_probability", "market_probability")
    for row in rows:
        target = _target(row)
        try:
            values = [max(1e-5, min(1 - 1e-5, float(row[key]))) for key in keys]
        except (KeyError, TypeError, ValueError):
            continue
        if target is not None:
            clean.append((values, target))
    return clean


def _metrics(probabilities: list[float], targets: list[int]) -> dict[str, float]:
    if not targets:
        return {"brier_score": 1.0, "log_loss": 99.0}
    brier = sum((p - y) ** 2 for p, y in zip(probabilities, targets)) / len(targets)
    loss = -sum(
        y * math.log(max(1e-8, p)) + (1 - y) * math.log(max(1e-8, 1 - p))
        for p, y in zip(probabilities, targets)
    ) / len(targets)
    return {"brier_score": round(brier, 8), "log_loss": round(loss, 8)}


def score_state(rows: Iterable[Mapping[str, Any]], state: Mapping[str, Any] | None) -> dict[str, Any]:
    clean = _clean_rows(rows)
    holdout = clean[int(len(clean) * 0.82):]
    if not holdout:
        return {"samples": 0, "brier_score": 1.0, "log_loss": 99.0}
    targets = [target for _, target in holdout]
    if state is None:
        probabilities = [values[0] for values, _ in holdout]
    else:
        configured = state.get("stacking_weights", {})
        weights = [
            max(0.0, float(configured.get(name, default)))
            for name, default in zip(
                ("current", "dixon_coles", "market"), (0.45, 0.35, 0.20)
            )
        ]
        total = sum(weights) or 1.0
        weights = [weight / total for weight in weights]
        beta = state.get("beta_calibration", {})
        calibrator = BetaCalibrator(
            float(beta.get("a", 1.0)),
            float(beta.get("b", 1.0)),
            float(beta.get("c", 0.0)),
        )
        probabilities = [
            calibrator.predict(sum(weight * value for weight, value in zip(weights, values)))
            for values, _ in holdout
        ]
    return {"samples": len(targets), **_metrics(probabilities, targets)}


def validate_candidate(
    rows: list[dict[str, Any]],
    candidate: Mapping[str, Any],
    active: Mapping[str, Any],
    min_brier_improvement: float,
    min_log_loss_improvement: float,
) -> dict[str, Any]:
    # The final candidate is intentionally not scored on rows used to fit it.
    # Every walk-forward fold trains a separate challenger on past-only rows.
    report = walk_forward_validate(
        rows,
        active or None,
        min_brier_improvement=min_brier_improvement,
        min_log_loss_improvement=min_log_loss_improvement,
        min_test_samples=int(os.getenv("BETBOT_QUALITY_WF_MIN_TEST_SAMPLES", "300")),
        min_folds=int(os.getenv("BETBOT_QUALITY_WF_MIN_FOLDS", "4")),
        min_edge=float(os.getenv("BETBOT_QUALITY_WF_MIN_EDGE", "0.02")),
    )
    return {
        **report,
        "candidate_state_created": candidate.get("status") == "TRAINED_TIME_SAFE",
    }


class ControlledQualityRetrainer:
    """Create and validate candidates; never write the active state path."""

    def __init__(
        self,
        data_dir: str | Path | None = None,
        *,
        min_new_rows: int = 300,
        min_hours: int = 24,
        min_brier_improvement: float = 0.0002,
        min_log_loss_improvement: float = 0.0002,
    ) -> None:
        self.data_dir = Path(data_dir or get_data_dir()).resolve()
        self.work_dir = self.data_dir / "quality_retraining"
        self.candidates_dir = self.work_dir / "candidates"
        self.dataset_path = self.work_dir / "quality_training.latest.csv"
        self.control_path = self.work_dir / "control_state.json"
        self.events_path = self.work_dir / "retraining_events.jsonl"
        self.lock_path = self.work_dir / "retraining.lock"
        self.active_path = Path(
            os.getenv("BETBOT_QUALITY_STATE", self.data_dir / "quality_shadow_state.json")
        ).resolve()
        self.latest_candidate_path = self.work_dir / "quality_shadow_state.candidate.latest.json"
        self.min_new_rows = max(1, int(min_new_rows))
        self.min_hours = max(1, int(min_hours))
        self.min_brier_improvement = max(0.0, float(min_brier_improvement))
        self.min_log_loss_improvement = max(0.0, float(min_log_loss_improvement))

    def _acquire(self) -> bool:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        if self.lock_path.exists():
            age = _utc_now().timestamp() - self.lock_path.stat().st_mtime
            if age > 4 * 3600:
                self.lock_path.unlink(missing_ok=True)
        try:
            with self.lock_path.open("x", encoding="utf-8") as handle:
                handle.write(f"pid={os.getpid()} time={_utc_now().isoformat()}\n")
            return True
        except FileExistsError:
            return False

    def _due(self, control: Mapping[str, Any], force: bool) -> bool:
        if force:
            return True
        raw = control.get("last_check")
        if not raw:
            return True
        try:
            previous = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            return _utc_now() - previous >= timedelta(hours=self.min_hours)
        except Exception:
            return True

    def run(self, *, force: bool = False) -> dict[str, Any]:
        if not self._acquire():
            return {"status": "SKIPPED_LOCKED"}
        try:
            control = _read_json(self.control_path)
            if not self._due(control, force):
                return {"status": "SKIPPED_NOT_DUE", **control}
            metadata = build(self.data_dir, self.dataset_path, replace_derived=True)
            rows = _training_rows(self.dataset_path)
            active = _read_json(self.active_path)
            baseline_rows = int(
                control.get("last_trained_rows")
                or active.get("samples")
                or 0
            )
            new_rows = max(0, len(rows) - baseline_rows)
            now = _utc_now().isoformat()
            if new_rows < self.min_new_rows and not force:
                result = {
                    "status": "WAITING_FOR_NEW_SETTLED_ROWS",
                    "checked_at": now,
                    "training_rows": len(rows),
                    "baseline_rows": baseline_rows,
                    "new_rows": new_rows,
                    "required_new_rows": self.min_new_rows,
                    "source_hashes_unchanged": metadata.get("source_hashes_unchanged"),
                }
                _atomic_json(self.control_path, {
                    **control,
                    "last_check": now,
                    "last_seen_rows": len(rows),
                    "last_status": result["status"],
                    "last_trained_rows": baseline_rows,
                })
                _append_event(self.events_path, result)
                return result

            candidate = train_time_safe_state(rows)
            if candidate.get("status") != "TRAINED_TIME_SAFE":
                result = {"status": "TRAINING_REJECTED", "checked_at": now, "training": candidate}
                _append_event(self.events_path, result)
                return result
            validation = validate_candidate(
                rows,
                candidate,
                active,
                self.min_brier_improvement,
                self.min_log_loss_improvement,
            )
            stamp = _utc_now().strftime("%Y%m%dT%H%M%S_%fZ")
            version_path = self.candidates_dir / f"quality_shadow_candidate_{stamp}.json"
            document = {
                **candidate,
                "created_at": now,
                "dataset_rows": len(rows),
                "new_rows": new_rows,
                "validation": validation,
                "candidate_path": str(version_path),
                "active_model_was_not_modified": True,
            }
            _atomic_json(version_path, document, exclusive=True)
            _atomic_json(self.latest_candidate_path, document)
            result = {
                "status": "CANDIDATE_CREATED",
                "created_at": now,
                "candidate": str(version_path),
                "validation": validation,
                "active_model_modified": False,
            }
            _atomic_json(self.control_path, {
                **control,
                "last_check": now,
                "last_training": now,
                "last_seen_rows": len(rows),
                "last_trained_rows": len(rows),
                "last_candidate": str(version_path),
                "last_validation": validation.get("status"),
                "last_status": result["status"],
            })
            _append_event(self.events_path, result)
            return result
        finally:
            self.lock_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    retrainer = ControlledQualityRetrainer(
        min_new_rows=int(os.getenv("BETBOT_QUALITY_RETRAIN_MIN_NEW_ROWS", "300")),
        min_hours=int(os.getenv("BETBOT_QUALITY_RETRAIN_MIN_HOURS", "24")),
        min_brier_improvement=float(
            os.getenv("BETBOT_QUALITY_RETRAIN_MIN_BRIER_IMPROVEMENT", "0.0002")
        ),
        min_log_loss_improvement=float(
            os.getenv("BETBOT_QUALITY_RETRAIN_MIN_LOGLOSS_IMPROVEMENT", "0.0002")
        ),
    )
    result = retrainer.run(force=args.force)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") not in {"TRAINING_REJECTED"} else 3


if __name__ == "__main__":
    raise SystemExit(main())
