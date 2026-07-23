"""Statistical Evidence Scorecard v8.

Combines immutable settled-history evidence with walk-forward, live-shadow and
data-quality gates.  It writes derived reports only and never mutates history,
the active model or capital settings.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from diagnostic_advantage_report import generate_report, load_rows
from quality_live_shadow import live_shadow_report
from settings_v81 import load_settings
from storage_paths import get_data_dir


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


def build_scorecard(
    diagnostic: Mapping[str, Any],
    validation: Mapping[str, Any],
    live: Mapping[str, Any],
    guardian: Mapping[str, Any],
    *,
    minimum_samples: int = 1000,
    minimum_clv_samples: int = 200,
    maximum_ece: float = 0.05,
) -> dict[str, Any]:
    global_metrics = diagnostic.get("global", {})
    integrity = diagnostic.get("integrity", {})
    readiness = guardian.get("training_readiness", {})
    alerts = guardian.get("alerts", []) if isinstance(guardian.get("alerts"), list) else []
    critical = any(str(item.get("severity", "")).upper() == "CRITICAL" for item in alerts)
    clv_ci = global_metrics.get("clv_ci95", {})
    yield_ci = global_metrics.get("yield_ci95", {})

    gates = {
        "settled_sample_size": int(global_metrics.get("samples", 0)) >= minimum_samples,
        "data_integrity": integrity.get("status") in {"PASS", "PASS_WITH_WARNINGS"},
        "calibration_ece": float(
            global_metrics.get("ece", 1.0) if global_metrics.get("ece") is not None else 1.0
        ) <= maximum_ece,
        "positive_clv_confidence": (
            int(global_metrics.get("clv_samples", 0)) >= minimum_clv_samples
            and float(clv_ci.get("lower", -1.0)) > 0.0
        ),
        "walk_forward_positive": validation.get("status") == "POSITIVE_VALIDATION_MANUAL_APPROVAL",
        "walk_forward_confidence": (
            bool(validation.get("gates", {}).get("brier_confidence_interval_positive"))
            and bool(validation.get("gates", {}).get("log_loss_confidence_interval_positive"))
        ),
        "walk_forward_stability": (
            bool(validation.get("gates", {}).get("fold_stability"))
            and bool(validation.get("gates", {}).get("slice_stability"))
        ),
        "live_shadow_positive": live.get("status") == "POSITIVE_LIVE_SHADOW_MANUAL_APPROVAL",
        "live_shadow_clv": bool(live.get("gates", {}).get("positive_clv_confidence")),
        "guardian_healthy": (
            guardian.get("status") == "HEALTHY"
            and bool(isinstance(readiness, Mapping) and readiness.get("ready_for_validation"))
            and not critical
        ),
    }
    # All core gates are mandatory. Positive realized yield is reported as the
    # strongest capital-readiness gate, but is not used to rewrite model truth.
    positive_yield = (
        int(global_metrics.get("priced_samples", 0)) >= minimum_samples
        and float(yield_ci.get("lower", -1.0)) > 0.0
    )
    passed = sum(bool(value) for value in gates.values())
    confirmed = all(gates.values())
    status = "STATISTICAL_EDGE_CONFIRMED" if confirmed else "REVIEW" if passed >= 7 else "COLLECTING"
    return {
        "schema_version": "betbot.statistical_evidence_scorecard.v8",
        "version": 8,
        "created_at": _now(),
        "status": status,
        "score": passed,
        "maximum_score": len(gates),
        "confirmed_statistical_edge": confirmed,
        "capital_readiness": "EVIDENCE_READY" if confirmed and positive_yield else "NOT_READY",
        "gates": gates,
        "realized_yield_ci_positive": positive_yield,
        "thresholds": {
            "minimum_settled_samples": minimum_samples,
            "minimum_clv_samples": minimum_clv_samples,
            "maximum_ece": maximum_ece,
        },
        "evidence": {
            "samples": int(global_metrics.get("samples", 0)),
            "priced_samples": int(global_metrics.get("priced_samples", 0)),
            "clv_samples": int(global_metrics.get("clv_samples", 0)),
            "brier_score": global_metrics.get("brier_score"),
            "log_loss": global_metrics.get("log_loss"),
            "ece": global_metrics.get("ece"),
            "yield": global_metrics.get("yield"),
            "yield_ci95": yield_ci,
            "mean_clv": global_metrics.get("mean_clv"),
            "clv_ci95": clv_ci,
            "walk_forward_status": validation.get("status", "MISSING"),
            "live_shadow_status": live.get("status", "MISSING"),
            "guardian_status": guardian.get("status", "MISSING"),
        },
        "automatic_model_change": False,
        "automatic_capital_change": False,
        "source_history_modified": False,
    }


class StatisticalEvidenceScorecard:
    def __init__(self, data_dir: str | Path | None = None) -> None:
        self.root = Path(data_dir or get_data_dir()).resolve()
        self.work = self.root / "quality_retraining"
        self.training_path = self.root / "quality_training.csv"
        self.candidate_path = self.work / "quality_shadow_state.candidate.latest.json"
        self.guardian_path = self.work / "data_quality_guardian.json"
        self.output_path = self.work / "statistical_evidence_scorecard_v8.json"

    def run(self) -> dict[str, Any]:
        settings = load_settings()
        rows = load_rows(self.training_path) if self.training_path.is_file() else []
        minimum_segment = settings.evidence_min_segment_samples
        diagnostic, _ = generate_report(rows, minimum_segment_samples=minimum_segment)
        candidate = _read(self.candidate_path)
        scorecard = build_scorecard(
            diagnostic,
            candidate.get("validation", {}) if isinstance(candidate.get("validation"), Mapping) else {},
            live_shadow_report(self.root),
            _read(self.guardian_path),
            minimum_samples=settings.evidence_min_oos_samples,
            minimum_clv_samples=settings.evidence_min_clv_samples,
            maximum_ece=settings.evidence_max_ece,
        )
        _atomic(self.output_path, scorecard)
        return scorecard


if __name__ == "__main__":
    print(json.dumps(StatisticalEvidenceScorecard().run(), ensure_ascii=False, indent=2))
