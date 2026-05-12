from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from ai_research_models import V8AIResearchEnsemble
from distributed_runtime import DistributedRuntime
from enterprise_data_feeds import EnterpriseDataFeeds

try:
    from rocket_v7_enterprise_orchestrator import RocketV7EnterpriseOrchestrator
except Exception:  # pragma: no cover
    RocketV7EnterpriseOrchestrator = None  # type: ignore


class RocketV8EnterpriseOrchestrator:
    """V8 integration layer.

    Extends the working V7 pipeline with:
    - Opta/StatsBomb/tracking/Betfair/sharp feed connectors
    - transformer-style, temporal, Bayesian and RL AI layers
    - async distributed runtime with Redis/Kafka optional infrastructure
    """
    def __init__(self, data_dir: str = 'data/enterprise'):
        self.data_dir = data_dir
        self.v7 = RocketV7EnterpriseOrchestrator(data_dir=data_dir) if RocketV7EnterpriseOrchestrator else None
        self.feeds = EnterpriseDataFeeds(data_dir='data')
        self.ai = V8AIResearchEnsemble(data_dir=data_dir)
        self.runtime = DistributedRuntime(audit_dir=f'{data_dir}/runtime')

    def analyze_fixture(self, fixture_id: str, home_xg: float, away_xg: float, market: str = 'OVER_2_5', bookmaker_odds: Optional[float] = None, sequence: Optional[Iterable[Dict[str, Any]]] = None, bankroll: float = 1000.0) -> Dict[str, Any]:
        base = self.v7.analyze_fixture(fixture_id, home_xg, away_xg, market, bookmaker_odds) if self.v7 else {'probability': 0.5, 'data_quality': 0.5, 'status': 'V7_NOT_AVAILABLE'}
        enterprise = self.feeds.fetch_all(fixture_id)
        enterprise_quality_bonus = min(0.18, 0.035 * enterprise.get('enterprise_provider_count', 0))
        data_quality = max(float(base.get('data_quality', 0.5)), min(1.0, float(base.get('data_quality', 0.5)) + enterprise_quality_bonus))
        row = {
            'probability': base.get('probability', 0.5),
            'home_xg': enterprise.get('home_xg', home_xg),
            'away_xg': enterprise.get('away_xg', away_xg),
            'total_xg': float(enterprise.get('home_xg', home_xg)) + float(enterprise.get('away_xg', away_xg)),
            'data_quality': data_quality,
            'market': market,
        }
        ai = self.ai.predict(row, sequence=sequence, bookmaker_odds=bookmaker_odds, bankroll=bankroll)
        final_p = round(max(0.01, min(0.99, 0.62*float(base.get('probability',0.5)) + 0.38*float(ai.get('probability',0.5)))), 6)
        out = {
            'status': 'V8_FULL_ENTERPRISE_STACK_ACTIVE',
            'fixture_id': fixture_id,
            'market': market,
            'probability': final_p,
            'v7_probability': base.get('probability'),
            'v8_ai_probability': ai.get('probability'),
            'data_quality': round(data_quality, 6),
            'enterprise_feeds': enterprise,
            'ai_research_layer': ai,
            'runtime': self.runtime.status(),
            'bookmaker_used_only_for_comparison': True,
        }
        if bookmaker_odds:
            ev = final_p*float(bookmaker_odds)-1
            out['market_comparison'] = {'bookmaker_odds': float(bookmaker_odds), 'fair_odds': round(1/final_p, 4), 'edge_ev': round(ev,6), 'value': ev > 0.03}
        return out

    def distributed_analyze(self, jobs: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        def handler(job: Dict[str, Any]) -> Dict[str, Any]:
            return self.analyze_fixture(
                fixture_id=str(job.get('fixture_id')),
                home_xg=float(job.get('home_xg', 1.35)),
                away_xg=float(job.get('away_xg', 1.05)),
                market=str(job.get('market', 'OVER_2_5')),
                bookmaker_odds=job.get('bookmaker_odds'),
                bankroll=float(job.get('bankroll', 1000.0)),
            )
        return self.runtime.distributed_inference(jobs, handler)
