from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _num(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == '': return default
        return float(v)
    except Exception:
        return default


def _sigmoid(x: float) -> float:
    if x < -35: return 0.0
    if x > 35: return 1.0
    return 1.0/(1.0+math.exp(-x))


@dataclass
class AIModelOutput:
    model: str
    probability: float
    confidence: float
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TemporalNeuralNetLite:
    """Dependency-light temporal model.

    Uses exponentially weighted sequence features and a logistic layer. If you
    later install PyTorch, this file can be replaced without changing the V8
    orchestrator interface.
    """
    def __init__(self, data_dir: str | Path = 'data/enterprise'):
        self.path = Path(data_dir) / 'temporal_nn_lite.json'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load()

    def _load(self):
        if self.path.exists():
            try: return json.loads(self.path.read_text(encoding='utf-8'))
            except Exception: pass
        return {'weights': {'probability': 1.4, 'xg_trend': 0.42, 'tempo_trend': 0.25, 'quality': 0.35}, 'bias': -0.55, 'trained': 0}

    def save(self):
        self.path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding='utf-8')

    def sequence_features(self, events: Iterable[Dict[str, Any]]) -> Dict[str, float]:
        rows = list(events)[-12:]
        if not rows:
            return {'xg_trend': 0.0, 'tempo_trend': 0.0, 'quality': 0.5}
        weights = [0.82 ** (len(rows)-1-i) for i in range(len(rows))]
        sw = sum(weights) or 1.0
        xg = sum(w*(_num(r.get('home_xg'),1.1)+_num(r.get('away_xg'),1.0)) for w,r in zip(weights, rows))/sw
        tempo = sum(w*_num(r.get('tempo', r.get('pace')),1.0) for w,r in zip(weights, rows))/sw
        quality = sum(w*_num(r.get('data_quality'),0.55) for w,r in zip(weights, rows))/sw
        return {'xg_trend': xg, 'tempo_trend': tempo, 'quality': quality}

    def predict(self, row: Dict[str, Any], sequence: Optional[Iterable[Dict[str, Any]]] = None) -> AIModelOutput:
        feats = self.sequence_features(sequence or [])
        feats['probability'] = _num(row.get('probability'), 0.5)
        z = self.state['bias'] + sum(_num(self.state['weights'].get(k))*_num(v) for k,v in feats.items())
        p = max(0.01, min(0.99, _sigmoid(z)))
        return AIModelOutput('temporal_neural_net_lite', round(p,6), round(min(0.98, 0.45+0.5*feats['quality']),4), feats)


class TransformerSequenceModelLite:
    """Small attention-style model with no hard deep-learning dependency."""
    def __init__(self, data_dir: str | Path = 'data/enterprise'):
        self.path = Path(data_dir) / 'transformer_lite.json'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state = {'temperature': 0.82, 'recency_bias': 1.35}

    def predict(self, row: Dict[str, Any], sequence: Optional[Iterable[Dict[str, Any]]] = None) -> AIModelOutput:
        seq = list(sequence or [])[-20:]
        base = _num(row.get('probability'), 0.5)
        if not seq:
            return AIModelOutput('transformer_sequence_lite', round(base,6), 0.45, {'attention_rows': 0})
        scores = []
        for i, r in enumerate(seq):
            sim = 1.0 - min(1.0, abs(_num(r.get('total_xg'), _num(r.get('home_xg'),1)+_num(r.get('away_xg'),1)) - _num(row.get('total_xg'), _num(row.get('home_xg'),1)+_num(row.get('away_xg'),1))) / 5.0)
            rec = ((i+1)/len(seq)) ** self.state['recency_bias']
            scores.append(max(0.001, sim*rec))
        sw = sum(scores) or 1.0
        seq_prob = sum(s*_num(r.get('probability', r.get('model_prob')), base) for s,r in zip(scores, seq))/sw
        p = (base*0.55 + seq_prob*0.45)
        conf = min(0.96, 0.42 + 0.035*len(seq))
        return AIModelOutput('transformer_sequence_lite', round(max(0.01,min(0.99,p)),6), round(conf,4), {'attention_rows': len(seq), 'sequence_probability': round(seq_prob,6)})


class BayesianDeepLearningLite:
    """Monte-Carlo dropout style uncertainty layer without PyTorch dependency."""
    def __init__(self, samples: int = 64, seed: int = 7):
        self.samples = samples
        self.rng = random.Random(seed)

    def predict(self, row: Dict[str, Any]) -> AIModelOutput:
        base = _num(row.get('probability'), 0.5)
        quality = _num(row.get('data_quality'), 0.55)
        spread = max(0.015, 0.16*(1-quality))
        draws = [max(0.01,min(0.99, base + self.rng.gauss(0, spread))) for _ in range(self.samples)]
        mean = sum(draws)/len(draws)
        var = sum((x-mean)**2 for x in draws)/len(draws)
        confidence = max(0.15, min(0.98, 1.0 - math.sqrt(var)*3.2))
        return AIModelOutput('bayesian_deep_learning_lite', round(mean,6), round(confidence,4), {'posterior_std': round(math.sqrt(var),6), 'samples': self.samples})


class RLBettingAgentLite:
    """Risk-aware policy layer for bet/no-bet and stake scaling."""
    def __init__(self, data_dir: str | Path = 'data/enterprise'):
        self.path = Path(data_dir) / 'rl_policy_lite.json'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load()

    def _load(self):
        if self.path.exists():
            try: return json.loads(self.path.read_text(encoding='utf-8'))
            except Exception: pass
        return {'min_ev': 0.035, 'min_quality': 0.52, 'kelly_fraction': 0.22, 'risk_penalty': 0.45, 'updates': 0}

    def save(self):
        self.path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding='utf-8')

    def policy(self, probability: float, odds: Optional[float], data_quality: float, uncertainty: float = 0.08, bankroll: float = 1000.0) -> Dict[str, Any]:
        odds = float(odds or 2.0)
        ev = probability * odds - 1.0
        quality_ok = data_quality >= self.state['min_quality']
        edge_ok = ev >= self.state['min_ev']
        b = odds - 1.0
        kelly = max(0.0, min(0.08, ((probability*b)-(1-probability))/max(0.01,b)))
        stake_fraction = kelly * self.state['kelly_fraction'] * max(0.15, 1.0 - uncertainty*self.state['risk_penalty'])
        return {'action': 'BET' if quality_ok and edge_ok and stake_fraction > 0 else 'PASS', 'ev': round(ev,6), 'stake': round(bankroll*stake_fraction,4), 'stake_fraction': round(stake_fraction,6), 'quality_ok': quality_ok, 'edge_ok': edge_ok}

    def update_from_settled(self, rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        rows = list(rows)
        if not rows:
            return {'status': 'NO_SETTLED_ROWS'}
        roi = sum(_num(r.get('profit'), 0) for r in rows) / max(1.0, sum(abs(_num(r.get('stake'),1)) for r in rows))
        if roi < -0.03:
            self.state['min_ev'] = min(0.12, self.state['min_ev'] + 0.005)
            self.state['kelly_fraction'] = max(0.08, self.state['kelly_fraction'] - 0.02)
        elif roi > 0.04:
            self.state['min_ev'] = max(0.02, self.state['min_ev'] - 0.003)
            self.state['kelly_fraction'] = min(0.30, self.state['kelly_fraction'] + 0.01)
        self.state['updates'] += 1
        self.save()
        return {'status': 'UPDATED', 'roi': round(roi,6), 'policy': self.state}


class V8AIResearchEnsemble:
    def __init__(self, data_dir: str | Path = 'data/enterprise'):
        self.temporal = TemporalNeuralNetLite(data_dir)
        self.transformer = TransformerSequenceModelLite(data_dir)
        self.bayes = BayesianDeepLearningLite()
        self.rl = RLBettingAgentLite(data_dir)

    def predict(self, row: Dict[str, Any], sequence: Optional[Iterable[Dict[str, Any]]] = None, bookmaker_odds: Optional[float] = None, bankroll: float = 1000.0) -> Dict[str, Any]:
        outs = [self.temporal.predict(row, sequence), self.transformer.predict(row, sequence), self.bayes.predict(row)]
        weight_sum = sum(o.confidence for o in outs) or 1.0
        p = sum(o.probability*o.confidence for o in outs)/weight_sum
        uncertainty = 1.0 - min(0.99, weight_sum / (len(outs)*0.98))
        quality = _num(row.get('data_quality'), 0.55)
        policy = self.rl.policy(p, bookmaker_odds, quality, uncertainty, bankroll)
        return {'status': 'V8_AI_RESEARCH_ACTIVE', 'probability': round(max(0.01,min(0.99,p)),6), 'uncertainty': round(uncertainty,6), 'model_outputs': [o.to_dict() for o in outs], 'rl_policy': policy}
