import math

MAX_GOALS = 10
# Fixed corrections and arbitrary clamps would change the bot's own price
# without evidence learned from settled records. Keep the model transparent.
DIXON_COLES_RHO = 0.0


def clamp(value, low, high):
    return max(low, min(high, value))


def poisson_prob(lmbda, goals):
    if lmbda < 0:
        return 0.0
    if lmbda == 0:
        return 1.0 if goals == 0 else 0.0
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
    home_xg = float(home_xg)
    away_xg = float(away_xg)
    if not math.isfinite(home_xg) or not math.isfinite(away_xg):
        raise ValueError("Goal rates must be finite")
    if home_xg < 0 or away_xg < 0:
        raise ValueError("Goal rates cannot be negative")

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
    checked = {}
    for market, probability in model.items():
        probability = float(probability)
        if not math.isfinite(probability) or probability < 0 or probability > 1:
            raise ValueError(f"Invalid probability for {market}: {probability}")
        checked[market] = probability
    return checked


def build_model(home_xg, away_xg):
    matrix = build_score_matrix(home_xg, away_xg)

    home_win, draw, away_win = calculate_1x2(matrix)

    btts_yes = calculate_btts(matrix)

    over_0_5 = calculate_over(matrix, 0.5)
    over_1_5 = calculate_over(matrix, 1.5)
    over_2_5 = calculate_over(matrix, 2.5)
    over_3_5 = calculate_over(matrix, 3.5)
    over_4_5 = calculate_over(matrix, 4.5)

    return sanity_check_model({
        # 1X2 base probabilities
        "HOME_WIN": home_win,
        "DRAW": draw,
        "AWAY_WIN": away_win,

        # Double chance
        "DOUBLE_1X": home_win + draw,
        "DOUBLE_X2": draw + away_win,
        "DOUBLE_12": home_win + away_win,

        # BTTS
        "BTTS_YES": btts_yes,
        "BTTS_NO": 1 - btts_yes,

        # Totals 0.5–4.5
        "OVER_0.5": over_0_5,
        "UNDER_0.5": 1 - over_0_5,

        "OVER_1.5": over_1_5,
        "UNDER_1.5": 1 - over_1_5,

        "OVER_2.5": over_2_5,
        "UNDER_2.5": 1 - over_2_5,

        "OVER_3.5": over_3_5,
        "UNDER_3.5": 1 - over_3_5,

        "OVER_4.5": over_4_5,
        "UNDER_4.5": 1 - over_4_5,
    })
