"""Autonomous Learning Governor v7.

The governor never trains on future data and never bypasses Champion-
Challenger gates.  It advances a candidate through evidence canary stages and
only calls the atomic registry promotion after Guardian, walk-forward and live
shadow are all positive.  Any ambiguity is fail-closed.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from quality_live_shadow import live_shadow_report
from quality_model_registry import (
    promote_candidate_automatically,
    rollback_automatic_promotion,
)
from storage_paths import get_data_dir


CANARY_STAGES = (10, 25, 50, 100)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _enabled(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return dict(value) if isinstance(value, Mapping) else {}
    except Exception:
        return {}


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _append(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


class AutonomousLearningGovernor:
    def __init__(self, data_dir: str | Path | None = None) -> None:
        self.root = Path(data_dir or get_data_dir()).resolve()
        self.work = self.root / "quality_retraining"
        self.state_path = self.work / "autonomous_governor_v7.json"
        self.events_path = self.work / "autonomous_governor_events.jsonl"
        self.lock_path = self.work / "autonomous_governor.lock"
        self.candidate_path = self.work / "quality_shadow_state.candidate.latest.json"
        self.guardian_path = self.root / "quality_monitoring" / "data_quality_guardian.json"
        self.active_path = Path(
            os.getenv("BETBOT_QUALITY_STATE", self.root / "quality_shadow_state.json")
        ).resolve()

    def _acquire(self) -> bool:
        self.work.mkdir(parents=True, exist_ok=True)
        try:
            with self.lock_path.open("x", encoding="utf-8") as handle:
                handle.write(f"pid={os.getpid()} at={_now()}\n")
            return True
        except FileExistsError:
            age = datetime.now(timezone.utc).timestamp() - self.lock_path.stat().st_mtime
            if age > 4 * 3600:
                self.lock_path.unlink(missing_ok=True)
                return self._acquire()
            return False

    def _guardian_gate(self) -> tuple[bool, dict[str, Any]]:
        report = _read(self.guardian_path)
        alerts = report.get("alerts", []) if isinstance(report.get("alerts"), list) else []
        critical = [item for item in alerts if str(item.get("severity", "")).upper() == "CRITICAL"]
        readiness = report.get("training_readiness", {})
        ready = bool(isinstance(readiness, Mapping) and readiness.get("ready_for_validation"))
        return bool(report and report.get("status") == "HEALTHY" and ready and not critical), report

    def _stage_requirement(self, stage: int) -> int:
        defaults = {10: 0, 25: 50, 50: 120, 100: 250}
        return max(0, int(os.getenv(f"BETBOT_GOVERNOR_CANARY_{stage}_NEW_SAMPLES", defaults[stage])))

    def _save(self, state: Mapping[str, Any], event: str) -> dict[str, Any]:
        payload = {**state, "updated_at": _now()}
        _atomic(self.state_path, payload)
        _append(self.events_path, {"event": event, **payload})
        return payload

    def _monitor_promoted(self, state: dict[str, Any], guardian_ok: bool) -> dict[str, Any]:
        expected = str(state.get("promoted_active_sha256", ""))
        if not self.active_path.is_file() or not expected:
            return self._save({**state, "phase": "LOCKED_ACTIVE_IDENTITY_MISSING"}, "LOCKED")
        current = _hash(self.active_path)
        if current != expected:
            return self._save({**state, "phase": "LOCKED_ACTIVE_CHANGED_EXTERNALLY"}, "LOCKED")
        if guardian_ok:
            return self._save({
                **state, "phase": "ACTIVE_MONITORING", "last_health": "PASS",
                "consecutive_health_failures": 0,
            }, "MONITOR")
        failures = int(state.get("consecutive_health_failures", 0)) + 1
        required = max(2, int(os.getenv("BETBOT_GOVERNOR_ROLLBACK_FAILURES", "3")))
        if failures < required:
            return self._save({
                **state, "phase": "ACTIVE_MONITORING", "last_health": "WARNING",
                "consecutive_health_failures": failures,
                "rollback_after_failures": required,
            }, "HEALTH_WARNING")
        if not _enabled("BETBOT_AUTONOMOUS_ROLLBACK_ENABLED", "1"):
            return self._save({**state, "phase": "ACTIVE_ALERT_ROLLBACK_DISABLED"}, "ALERT")
        rollback = rollback_automatic_promotion(
            expected,
            str(state.get("previous_champion_backup", "")),
            "Data Quality Guardian became unhealthy after autonomous promotion",
            self.root,
        )
        return self._save({
            **state, "phase": rollback.get("status"), "rollback": rollback,
            "quarantined_candidate_sha256": state.get("candidate_sha256", ""),
            "consecutive_health_failures": failures,
        }, "ROLLBACK")

    def run(self) -> dict[str, Any]:
        if not _enabled("BETBOT_AUTONOMOUS_GOVERNOR_ENABLED", "0"):
            return {"status": "DISABLED", "automatic_model_change": False}
        if not self._acquire():
            return {"status": "SKIPPED_LOCKED", "automatic_model_change": False}
        try:
            state = _read(self.state_path)
            guardian_ok, guardian = self._guardian_gate()
            if str(state.get("phase", "")).startswith("ACTIVE"):
                return {"status": "MONITORED", **self._monitor_promoted(state, guardian_ok)}
            if not self.candidate_path.is_file():
                return {"status": "WAITING_FOR_CANDIDATE", **self._save({"phase": "WAITING_FOR_CANDIDATE"}, "WAIT")}
            candidate_hash = _hash(self.candidate_path)
            candidate = _read(self.candidate_path)
            if (
                state.get("quarantined_candidate_sha256") == candidate_hash
                and state.get("phase") == "ROLLED_BACK_AUTOMATICALLY"
            ):
                return {
                    "status": "CANDIDATE_QUARANTINED_AFTER_ROLLBACK",
                    **self._save({
                        **state, "automatic_model_change": False,
                    }, "QUARANTINE_BLOCKED"),
                }
            validation = candidate.get("validation", {})
            live = live_shadow_report(self.root)
            gates = {
                "guardian_healthy_and_ready": guardian_ok,
                "candidate_immutable": bool(candidate_hash),
                "walk_forward_positive": validation.get("status") == "POSITIVE_VALIDATION_MANUAL_APPROVAL",
                "live_shadow_positive": live.get("status") == "POSITIVE_LIVE_SHADOW_MANUAL_APPROVAL",
                "candidate_declares_no_active_mutation": candidate.get("active_model_was_not_modified") is True,
            }
            if not all(gates.values()):
                waiting = {
                    "phase": "WAITING_FOR_ALL_GATES",
                    "candidate_sha256": candidate_hash,
                    "gates": gates,
                    "live_status": live.get("status"),
                    "guardian_status": guardian.get("status", "MISSING"),
                    "automatic_model_change": False,
                }
                return {"status": "WAITING_FOR_ALL_GATES", **self._save(waiting, "GATES_BLOCKED")}

            if state.get("candidate_sha256") != candidate_hash:
                state = self._save({
                    "phase": "CANARY_10",
                    "candidate_sha256": candidate_hash,
                    "candidate_id": live.get("candidate_id"),
                    "baseline_settled_samples": int(live.get("settled_samples", 0)),
                    "canary_percent": 10,
                    "gates": gates,
                    "automatic_model_change": False,
                }, "CANARY_STARTED")
                return {"status": "CANARY_STARTED", **state}

            baseline = int(state.get("baseline_settled_samples", live.get("settled_samples", 0)))
            fresh = max(0, int(live.get("settled_samples", 0)) - baseline)
            current_stage = int(state.get("canary_percent", 10))
            next_stage = next((stage for stage in CANARY_STAGES if stage > current_stage), None)
            if next_stage is not None and fresh >= self._stage_requirement(next_stage):
                state = self._save({
                    **state, "phase": f"CANARY_{next_stage}", "canary_percent": next_stage,
                    "fresh_settled_samples": fresh, "gates": gates,
                }, "CANARY_ADVANCED")
                current_stage = next_stage
            if current_stage < 100:
                return {"status": "CANARY_COLLECTING", **state, "fresh_settled_samples": fresh}

            promotion = promote_candidate_automatically(candidate_hash, self.root)
            if promotion.get("status") != "PROMOTED_AUTONOMOUSLY":
                return {"status": "PROMOTION_REFUSED", **self._save({
                    **state, "phase": "PROMOTION_REFUSED", "promotion": promotion,
                }, "PROMOTION_REFUSED")}
            promoted = self._save({
                **state,
                "phase": "ACTIVE_MONITORING",
                "promotion": promotion,
                "promoted_active_sha256": promotion["active_sha256"],
                "previous_champion_backup": promotion.get("previous_backup", ""),
                "automatic_model_change": True,
            }, "PROMOTED")
            return {"status": "PROMOTED_AUTONOMOUSLY", **promoted}
        finally:
            self.lock_path.unlink(missing_ok=True)


if __name__ == "__main__":
    print(json.dumps(AutonomousLearningGovernor().run(), ensure_ascii=False, indent=2))
