def classify_bet(prob, book_odds, fair_odds):
    if prob is None or prob <= 0:
        return "NO BET", 0

    edge = (book_odds / fair_odds) - 1

    if book_odds > 4.5 and prob > 0.6:
        return "NO BET", edge

    if book_odds < 1.2:
        return "NO BET", edge

    if edge >= 0.15 and prob >= 0.55:
        return "VALUE++", edge

    if edge >= 0.08 and prob >= 0.52:
        return "VALUE+", edge

    if edge >= 0.04 and prob >= 0.50:
        return "VALUE", edge

    if prob >= 0.60 and edge >= 0:
        return "SAFE", edge

    if edge >= 0.02:
        return "RISK", edge

    return "NO BET", edge


def confidence_score(prob, edge):
    if prob is None:
        return 0

    score = (prob * 0.7) + (edge * 0.3)
    return round(min(max(score, 0), 1), 3)