from __future__ import annotations

import json
from pathlib import Path

from auto_retraining_runtime import AutoRetrainingRuntime
from gpu_optimizer import GPUOptimizer
from multi_source_ingestion import MultiSourceIngestion
from rocket_v7_enterprise_orchestrator import RocketV7EnterpriseOrchestrator
from source_quality_engine import SourceQualityEngine


def main() -> None:
    data_dir = Path("data/enterprise")
    data_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "source_quality": SourceQualityEngine().evaluate({
            "fixture_id":"smoke", "home_team":"A", "away_team":"B", "league":"TEST", "start_time":"now",
            "home_shots":10, "away_shots":8, "home_shots_on_target":4, "away_shots_on_target":3,
            "home_possession":54, "away_possession":46
        }, "smoke"),
        "gpu_optimizer": GPUOptimizer().optimize(),
        "monte_carlo": GPUOptimizer().vectorized_monte_carlo(1.55, 1.15, runs=10000),
        "retraining": AutoRetrainingRuntime(data_dir, min_hours_between_runs=0).nightly_retrain(force=True),
        "orchestrator": RocketV7EnterpriseOrchestrator(str(data_dir)).analyze_fixture("smoke", 1.55, 1.15, bookmaker_odds=1.91),
    }
    path = data_dir / "v7_activation_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status":"V7_FULL_ACTIVATION_OK", "report": str(path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
