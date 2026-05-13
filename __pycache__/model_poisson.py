import math


def poisson(lmbda, k):
    return (lmbda ** k) * math.exp(-lmbda) / math.factorial(k)


def compute_markets(home_xg, away_xg, max_goals=8):
    """
    Zachowuje zgodność z obecną wersją:
    zwraca słownik z:
    - HOME_WIN
    - DRAW
    - AWAY_WIN
    """

    p_home = 0.0
    p_draw = 0.0
    p_away = 0.0

    total_prob = 0.0

    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            p = poisson(home_xg, i) * poisson(away_xg, j)
            total_prob += p

            if i > j:
                p_home += p
            elif i == j:
                p_draw += p
            else:
                p_away += p

    # normalizacja bezpieczeństwa
    if total_prob > 0:
        p_home /= total_prob
        p_draw /= total_prob
        p_away /= total_prob

    return {
        "HOME_WIN": p_home,
        "DRAW": p_draw,
        "AWAY_WIN": p_away,
    }