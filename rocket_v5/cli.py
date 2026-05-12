from __future__ import annotations

import argparse
import json
from pathlib import Path

from .rocket_pipeline import RocketPipelineV5
from .auto_retraining import AutoRetrainingEngineV5


def main() -> None:
    parser = argparse.ArgumentParser(description="Rocket V5 professional predictive stack")
    sub = parser.add_subparsers(dest="cmd", required=True)

    analyze = sub.add_parser("analyze")
    analyze.add_argument("--input", required=True, help="JSON file with match payload")
    analyze.add_argument("--market", default="OVER_2_5")
    analyze.add_argument("--odds", type=float, default=None)
    analyze.add_argument("--runs", type=int, default=75000)

    retrain = sub.add_parser("retrain")
    retrain.add_argument("--data-dir", default="data/rocket_v5")

    providers = sub.add_parser("providers")
    providers.add_argument("--data-dir", default="data/rocket_v5")

    args = parser.parse_args()
    if args.cmd == "analyze":
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        bot = RocketPipelineV5(monte_carlo_runs=args.runs)
        print(json.dumps(bot.analyze(payload, market=args.market, bookmaker_odds=args.odds), ensure_ascii=False, indent=2))
    elif args.cmd == "retrain":
        print(json.dumps(AutoRetrainingEngineV5(args.data_dir).nightly_retrain(), ensure_ascii=False, indent=2))
    elif args.cmd == "providers":
        from .multi_source import MultiSourceHubV5
        print(json.dumps(MultiSourceHubV5(args.data_dir).provider_status(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
