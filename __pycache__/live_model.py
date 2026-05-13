def clamp_prob(prob):
    return max(0.01, min(float(prob), 0.95))


def estimate_base_over25_prob(minute, home_goals, away_goals):
    total = (home_goals or 0) + (away_goals or 0)

    if total >= 3:
        return 0.92
    if total == 2:
        if minute <= 55:
            return 0.72
        if minute <= 70:
            return 0.58
        return 0.42
    if total == 1:
        if minute <= 30:
            return 0.66
        if minute <= 45:
            return 0.58
        if minute <= 60:
            return 0.44
        return 0.28
    if minute <= 15:
        return 0.56
    if minute <= 25:
        return 0.49
    if minute <= 35:
        return 0.42
    if minute <= 45:
        return 0.34
    if minute <= 60:
        return 0.24
    return 0.14


def live_model_over25(minute, home_goals, away_goals):
    return clamp_prob(estimate_base_over25_prob(minute, home_goals, away_goals))
