"""Autonomous data-to-quality orchestration for BetBot v11.

The orchestrator owns the complete derived learning cycle: audit immutable
evidence, wait for sufficient quality, train an isolated challenger, validate
it chronologically and in live shadow, promote through guarded canary stages,
then monitor and roll back regressions.

It never edits source history, enables betting, or bypasses a component gate.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from autonomous_learning_governor import AutonomousLearningGovernor
from quality_auto_retraining import ControlledQualityRetrainer
from quality_data_guardian import run_guardian
from settings_v81 import RuntimeSettings, load_settings
from staged_capital_governor import StagedCapitalGovernor
from statistical_evidence_scorecard import StatisticalEvidenceScorecard
from storage_paths import get_data_dir
from multisport_quality_audit_v12 import MultisportQualityAuditV12
from market_integrity_audit_v13 import MarketIntegrityAuditV13


SCHEMA = "betbot.autonomous_quality_orchestrator.v11"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return dict(value) if isinstance(value, Mapping) else {}
    except Exception:
        return {}


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


def readiness_from_guardian(
    guardian: Mapping[str, Any],
    *,
    minimum_settled: int,
    minimum_settlement_coverage: float,
    minimum_closing_coverage: float,
) -> dict[str, Any]:
    metrics = guardian.get("metrics", {}) if isinstance(guardian.get("metrics"), Mapping) else {}
    readiness = (
        guardian.get("training_readiness", {})
        if isinstance(guardian.get("training_readiness"), Mapping)
        else {}
    )
    settled = max(0, int(readiness.get("settled", 0) or 0))
    settlement_coverage = float(metrics.get("settlement_coverage", 0.0) or 0.0)
    closing_coverage = float(metrics.get("closing_odds_coverage", 0.0) or 0.0)
    alerts = guardian.get("alerts", []) if isinstance(guardian.get("alerts"), list) else []
    critical = any(
        str(item.get("severity", "")).upper() == "CRITICAL"
        for item in alerts
        if isinstance(item, Mapping)
    )
    gates = {
        "guardian_healthy": guardian.get("status") == "HEALTHY",
        "minimum_settled_samples": settled >= minimum_settled,
        "settlement_coverage": settlement_coverage >= minimum_settlement_coverage,
        "closing_odds_coverage": closing_coverage >= minimum_closing_coverage,
        "guardian_validation_ready": readiness.get("ready_for_validation") is True,
        "no_critical_alerts": not critical,
    }
    return {
        "ready": all(gates.values()),
        "gates": gates,
        "observed": {
            "settled_samples": settled,
            "settlement_coverage": settlement_coverage,
            "closing_odds_coverage": closing_coverage,
        },
        "required": {
            "settled_samples": minimum_settled,
            "settlement_coverage": minimum_settlement_coverage,
            "closing_odds_coverage": minimum_closing_coverage,
        },
    }


def _phase(
    readiness: Mapping[str, Any],
    retraining: Mapping[str, Any],
    scorecard: Mapping[str, Any],
    governor: Mapping[str, Any],
) -> tuple[str, str]:
    if not readiness.get("ready"):
        return "COLLECTING_QUALITY_DATA", "Zbieranie i rozliczanie danych do progów jakości"
    if retraining.get("status") in {"WAITING_FOR_NEW_SETTLED_ROWS", "SKIPPED_NOT_DUE"}:
        return "WAITING_FOR_FRESH_TRAINING_BATCH", "Oczekiwanie na nową niezależną partię danych"
    if not scorecard.get("confirmed_statistical_edge"):
        return "CHALLENGER_VALIDATION", "Walk-forward i live shadow kandydata"
    status = str(governor.get("status", ""))
    if status in {"CANARY_STARTED", "CANARY_COLLECTING"}:
        return "AUTONOMOUS_CANARY", "Zbieranie świeżych rozliczeń dla kolejnego etapu canary"
    if status in {"PROMOTED_AUTONOMOUSLY", "MONITORED"}:
        return "AUTONOMOUS_CHAMPION", "Monitorowanie jakości i automatyczny rollback"
    return "READY_FOR_GOVERNOR", "Ocena wszystkich bramek promocji"


class AutonomousQualityOrchestrator:
    def __init__(
        self,
        data_dir: str | Path | None = None,
        settings: RuntimeSettings | None = None,
        *,
        guardian_runner=run_guardian,
        retrainer=None,
        scorecard=None,
        model_governor=None,
        capital_governor=None,
        multisport_audit=None,
        market_integrity_audit=None,
    ) -> None:
        self.root = Path(data_dir or get_data_dir()).resolve()
        self.work = self.root / "quality_retraining"
        self.state_path = self.work / "autonomy_v11_state.json"
        self.events_path = self.work / "autonomy_v11_events.jsonl"
        self.guardian_path = self.work / "data_quality_guardian.json"
        self.settings = settings or load_settings()
        self.guardian_runner = guardian_runner
        self.retrainer = retrainer or ControlledQualityRetrainer(
            self.root,
            min_new_rows=self.settings.quality_retrain_min_new_rows,
            min_hours=self.settings.quality_retrain_min_hours,
        )
        self.scorecard = scorecard or StatisticalEvidenceScorecard(self.root)
        self.model_governor = model_governor or AutonomousLearningGovernor(self.root)
        self.capital_governor = capital_governor or StagedCapitalGovernor(self.root)
        self.multisport_audit = multisport_audit or MultisportQualityAuditV12(self.root)
        self.market_integrity_audit = market_integrity_audit or MarketIntegrityAuditV13(
            self.root
        )

    def run(self) -> dict[str, Any]:
        started_at = _now()
        guardian_result = self.guardian_runner(self.root)
        market_integrity = self.market_integrity_audit.run()
        guardian = _read(self.guardian_path)
        readiness = readiness_from_guardian(
            guardian,
            minimum_settled=max(
                100,
                int(os.getenv("BETBOT_AUTONOMY_MIN_SETTLED_FOR_TRAINING", "300")),
            ),
            minimum_settlement_coverage=float(
                os.getenv("BETBOT_GUARDIAN_MIN_SETTLEMENT_COVERAGE", "0.95")
            ),
            minimum_closing_coverage=float(
                os.getenv("BETBOT_QUALITY_MIN_CLOSING_COVERAGE", "0.80")
            ),
        )
        football_integrity_ready = bool(
            market_integrity.get("sports", {})
            .get("football", {})
            .get("training_admission_ready")
        )
        readiness["gates"]["market_data_integrity_v13"] = football_integrity_ready
        readiness["ready"] = all(readiness["gates"].values())
        retraining = (
            self.retrainer.run()
            if readiness["ready"]
            else {"status": "WAITING_FOR_QUALITY_DATA", "active_model_modified": False}
        )

        # Generate evidence before the governor so promotion consumes the
        # scorecard created for this exact candidate and cycle.
        scorecard = self.scorecard.run()
        governor = self.model_governor.run()
        capital = self.capital_governor.run()
        multisport = self.multisport_audit.run()
        phase, next_action = _phase(readiness, retraining, scorecard, governor)
        payload = {
            "schema_version": SCHEMA,
            "status": "HEALTHY",
            "phase": phase,
            "next_action": next_action,
            "cycle_started_at": started_at,
            "updated_at": _now(),
            "fully_automatic_learning": (
                self.settings.autonomous_governor_enabled
                and self.settings.autonomous_promotion_enabled
            ),
            "data_readiness": readiness,
            "components": {
                "guardian": guardian_result,
                "retraining": retraining,
                "scorecard": scorecard,
                "model_governor": governor,
                "capital_governor": capital,
                "multisport_v12": multisport,
                "market_integrity_v13": market_integrity,
            },
            "active_model_changed": governor.get("status") == "PROMOTED_AUTONOMOUSLY",
            "automatic_rollback_enabled": os.getenv(
                "BETBOT_AUTONOMOUS_ROLLBACK_ENABLED", "1"
            ).strip().lower() in {"1", "true", "yes", "on"},
            "source_history_modified": False,
            "financial_execution_modified": False,
        }
        _atomic(self.state_path, payload)
        _append(
            self.events_path,
            {
                "updated_at": payload["updated_at"],
                "phase": phase,
                "retraining_status": retraining.get("status"),
                "scorecard_status": scorecard.get("status"),
                "governor_status": governor.get("status"),
                "source_history_modified": False,
            },
        )
        return payload


if __name__ == "__main__":
    print(json.dumps(AutonomousQualityOrchestrator().run(), ensure_ascii=False, indent=2))
