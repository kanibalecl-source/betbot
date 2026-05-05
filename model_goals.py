import math

MAX_GOALS = 10
DIXON_COLES_RHO = -0.10
MIN_XG = 0.20
MAX_XG = 4.00


def clamp(value, low, high):
    return max(low, min(high, value))


def poisson_prob(lmbda, goals):
    if lmbda <= 0:
        return 0.0
    return (lmbda ** goals) * math.exp(-lmbda) / math.factorial(goals)


def dixon_coles_adjustment(home_goals, away_goals, home_xg, away_xg, rho=DIXON_COLES_RHO):
    if home_goals == 0 and away_goals == 0:
        return 1 - (home_xg * away_xg * rho)
    if home_goals == 0 and away_goals == 1:
        return 1 + (home_xg * rho)
    if home_goals == 1 and away_goals == 0:
        return 1 + (away_xg * rho)
    if home_goals == 1 and away_goals == 1:
        return 1 - rho
    return 1.0


def build_score_matrix(home_xg, away_xg):
    home_xg = clamp(float(home_xg), MIN_XG, MAX_XG)
    away_xg = clamp(float(away_xg), MIN_XG, MAX_XG)

    matrix = []
    for home_goals in range(MAX_GOALS + 1):
        row = []
        for away_goals in range(MAX_GOALS + 1):
            base_prob = poisson_prob(home_xg, home_goals) * poisson_prob(away_xg, away_goals)
            adj = dixon_coles_adjustment(home_goals, away_goals, home_xg, away_xg)
            row.append(max(base_prob * adj, 0.0))
        matrix.append(row)

    total = sum(sum(row) for row in matrix)
    if total > 0:
        matrix = [[p / total for p in row] for row in matrix]

    return matrix


def calculate_1x2(matrix):
    home_win = draw = away_win = 0.0

    for home_goals, row in enumerate(matrix):
        for away_goals, prob in enumerate(row):
            if home_goals > away_goals:
                home_win += prob
            elif home_goals == away_goals:
                draw += prob
            else:
                away_win += prob

    return home_win, draw, away_win


def calculate_btts(matrix):
    return sum(
        prob
        for home_goals, row in enumerate(matrix)
        for away_goals, prob in enumerate(row)
        if home_goals > 0 and away_goals > 0
    )


def calculate_over(matrix, line):
    return sum(
        prob
        for home_goals, row in enumerate(matrix)
        for away_goals, prob in enumerate(row)
        if home_goals + away_goals > line
    )


def sanity_check_model(model):
    return {market: clamp(float(prob), 0.01, 0.99) for market, prob in model.items()}


def build_model(home_xg, away_xg):
    matrix = build_score_matrix(home_xg, away_xg)

    home_win, draw, away_win = calculate_1x2(matrix)

    btts_yes = calculate_btts(matrix)
    over_2_5 = calculate_over(matrix, 2.5)
    over_1_5 = calculate_over(matrix, 1.5)

    return sanity_check_model({
        "HOME_WIN": home_win,
        "DRAW": draw,
        "AWAY_WIN": away_win,
        "BTTS_YES": btts_yes,
        "BTTS_NO": 1 - btts_yes,
        "OVER_2.5": over_2_5,
        "UNDER_2.5": 1 - over_2_5,
        "OVER_1.5": over_1_5,
        "UNDER_1.5": 1 - over_1_5,
    })
