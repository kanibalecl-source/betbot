from __future__ import annotations
from math import prod


def _odds(item):
    try:
        return float(item.get("odds") or item.get("kurs") or 1.0)
    except Exception:
        return 1.0


def _conf(item):
    try:
        return float(item.get("confidence", 0))
    except Exception:
        return 0.0


def build_ako_coupons(analyses):
    playable = [x for x in analyses if str(x.get("decision", "")).upper() == "PLAY"]
    playable.sort(key=lambda x: (_conf(x), float(x.get("value_score", 0) or 0)), reverse=True)

    safe = [x for x in playable if _conf(x) >= 78 and str(x.get("risk", "")).lower() in ("low", "medium")][:3]
    balanced = [x for x in playable if _conf(x) >= 70][:5]
    aggressive = [x for x in playable if _conf(x) >= 62][:7]

    def pack(name, picks, label):
        if not picks:
            return {"name": name, "label": label, "picks": [], "total_odds": 0, "avg_confidence": 0, "risk": "brak"}
        total = round(prod([_odds(p) for p in picks]), 2)
        avg = round(sum(_conf(p) for p in picks) / len(picks), 1)
        risk = "low" if avg >= 80 and len(picks) <= 3 else "medium" if avg >= 70 else "high"
        return {"name": name, "label": label, "picks": picks, "total_odds": total, "avg_confidence": avg, "risk": risk}

    return [
        pack("SAFE_AKO", safe, "Najbezpieczniejszy kupon"),
        pack("BALANCED_AKO", balanced, "Najlepszy balans kurs/ryzyko"),
        pack("AGGRESSIVE_AKO", aggressive, "Wyższy kurs, większe ryzyko"),
    ]
