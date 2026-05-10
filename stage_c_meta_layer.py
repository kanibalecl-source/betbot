from meta_ensemble_ai import MetaEnsembleAI
from dynamic_bankroll_ai import DynamicBankrollAI
from auto_optimizer_v2 import AutoOptimizerV2


class StageCMetaLayer:
    def __init__(self):
        self.meta = MetaEnsembleAI()
        self.bankroll = DynamicBankrollAI()
        self.optimizer = AutoOptimizerV2()

    def enrich_pick(self, pick, market, model_prob, market_prob, xg_prob, momentum_prob, sharp_prob, base_stake, confidence, ev, risk_label, sharp_score=0, clv_percent=0, momentum_score=0):
        weights = self.meta.dynamic_weights(market=market, sharp_score=sharp_score, momentum_score=momentum_score, clv_percent=clv_percent)
        meta_probability = self.meta.combine(model_prob=model_prob, market_prob=market_prob, xg_prob=xg_prob, momentum_prob=momentum_prob, sharp_prob=sharp_prob, weights=weights)
        adjusted_stake = self.bankroll.adjusted_stake(base_stake=base_stake, confidence=confidence, ev=ev, risk_label=risk_label, sharp_score=sharp_score, clv_percent=clv_percent)
        result = dict(pick)
        result.update({
            "meta_probability": meta_probability,
            "meta_weight_model": weights.get("model"),
            "meta_weight_market": weights.get("market"),
            "meta_weight_xg": weights.get("xg"),
            "meta_weight_momentum": weights.get("momentum"),
            "meta_weight_sharp": weights.get("sharp"),
            "dynamic_stake": adjusted_stake,
        })
        return result
