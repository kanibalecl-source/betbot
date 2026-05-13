def get_odds_drop_pct(opening_odds, current_odds):
    if not opening_odds or not current_odds or opening_odds <= 0:
        return 0.0
    return round((opening_odds - current_odds) / opening_odds, 4)

def timing_status(opening_odds, current_odds):
    drop = get_odds_drop_pct(opening_odds, current_odds)
    if drop <= 0.00:
        return "WAIT"
    if 0.00 < drop <= 0.04:
        return "GOOD"
    if 0.04 < drop <= 0.07:
        return "LATE"
    return "DEAD"

def timing_multiplier(opening_odds, current_odds):
    status = timing_status(opening_odds, current_odds)
    if status == "GOOD":
        return 1.0
    if status == "WAIT":
        return 0.9
    if status == "LATE":
        return 0.7
    return 0.0
