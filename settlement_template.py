from datetime import datetime


def build_result_record(
    match,
    league,
    market,
    pick,
    odds,
    stake,
    confidence,
    ev,
    won
):

    profit = 0

    try:
        odds = float(odds)
        stake = float(stake)

        if won:
            profit = (odds - 1) * stake
        else:
            profit = -stake

    except:
        profit = 0

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "match": match,
        "league": league,
        "market": market,
        "pick": pick,
        "odds": odds,
        "stake": stake,
        "confidence": confidence,
        "ev": ev,
        "won": int(bool(won)),
        "profit": round(profit, 2)
    }
