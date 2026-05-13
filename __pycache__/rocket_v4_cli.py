from __future__ import annotations

import argparse
import json
from pathlib import Path

from rocket_v4.orchestrator import RocketOrchestratorV4
from rocket_v4.data_hub import DataHubV4


def main() -> None:
    parser = argparse.ArgumentParser(description="Rocket V4 autonomous BetBot pipeline")
    sub = parser.add_subparsers(dest="cmd")
    a = sub.add_parser("analyze")
    a.add_argument("--match-json", required=True, help="Path to match JSON payload")
    a.add_argument("--market", default="OVER_2_5")
    a.add_argument("--odds", type=float, default=None)
    a.add_argument("--bankroll", type=float, default=1000.0)
    sub.add_parser("providers")
    args = parser.parse_args()

    if args.cmd == "providers":
        print(json.dumps(DataHubV4().provider_status(), ensure_ascii=False, indent=2))
        return
    if args.cmd == "analyze":
        match = json.loads(Path(args.match_json).read_text(encoding="utf-8"))
        bot = RocketOrchestratorV4(bankroll=args.bankroll)
        print(json.dumps(bot.analyze(match, args.market, args.odds, args.bankroll), ensure_ascii=False, indent=2))
        return
    parser.print_help()


if __name__ == "__main__":
    main()
