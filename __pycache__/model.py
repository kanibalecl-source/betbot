from statistics import median


def _median_or_none(values):
    values = [v for v in values if v is not None and v > 1.0]
    if not values:
        return None
    return median(values)


def _de_vig_two_way(odds_a, odds_b):
    if odds_a is None or odds_b is None:
        return None, None

    p_a = 1 / odds_a
    p_b = 1 / odds_b
    s = p_a + p_b
    if s <= 0:
        return None, None

    return p_a / s, p_b / s


def _de_vig_three_way(odds_h, odds_d, odds_a):
    if odds_h is None or odds_d is None or odds_a is None:
        return None, None, None

    p_h = 1 / odds_h
    p_d = 1 / odds_d
    p_a = 1 / odds_a
    s = p_h + p_d + p_a
    if s <= 0:
        return None, None, None

    return p_h / s, p_d / s, p_a / s


def _ou_pair_key(market_code):
    if market_code.startswith("OVER_"):
        line = market_code.split("_", 1)[1]
        return market_code, f"UNDER_{line}"
    if market_code.startswith("UNDER_"):
        line = market_code.split("_", 1)[1]
        return f"OVER_{line}", market_code
    return None, None


def calculate_market_metrics(market_code, all_market_data):
    """
    Czysta matematyka z kursów API:
    - fair probability z konsensusu rynku po zdjęciu marży
    - fair odds = 1 / fair probability
    - edge = best_odds / fair_odds - 1
    """
    if market_code not in all_market_data:
        return None

    market_data = all_market_data[market_code]
    best_odds = market_data.get("best_odds")
    all_odds = market_data.get("all_odds", [])

    if best_odds is None or best_odds <= 1.0:
        return None

    fair_prob = None
    books_count = len([x for x in all_odds if x and x > 1.0])

    # 1X2
    if market_code in ["HOME_WIN", "DRAW", "AWAY_WIN"]:
        mh = _median_or_none(all_market_data.get("HOME_WIN", {}).get("all_odds", []))
        md = _median_or_none(all_market_data.get("DRAW", {}).get("all_odds", []))
        ma = _median_or_none(all_market_data.get("AWAY_WIN", {}).get("all_odds", []))

        ph, pd, pa = _de_vig_three_way(mh, md, ma)

        mapping = {
            "HOME_WIN": ph,
            "DRAW": pd,
            "AWAY_WIN": pa,
        }
        fair_prob = mapping.get(market_code)

    # BTTS
    elif market_code in ["BTTS_YES", "BTTS_NO"]:
        yes = _median_or_none(all_market_data.get("BTTS_YES", {}).get("all_odds", []))
        no = _median_or_none(all_market_data.get("BTTS_NO", {}).get("all_odds", []))
        py, pn = _de_vig_two_way(yes, no)
        fair_prob = py if market_code == "BTTS_YES" else pn

    # Over/Under
    elif market_code.startswith("OVER_") or market_code.startswith("UNDER_"):
        over_key, under_key = _ou_pair_key(market_code)
        mo = _median_or_none(all_market_data.get(over_key, {}).get("all_odds", []))
        mu = _median_or_none(all_market_data.get(under_key, {}).get("all_odds", []))
        po, pu = _de_vig_two_way(mo, mu)
        fair_prob = po if market_code.startswith("OVER_") else pu

    # Double chance z 1X2 fair probs
    elif market_code in ["HOME_OR_DRAW", "AWAY_OR_DRAW", "HOME_OR_AWAY"]:
        mh = _median_or_none(all_market_data.get("HOME_WIN", {}).get("all_odds", []))
        md = _median_or_none(all_market_data.get("DRAW", {}).get("all_odds", []))
        ma = _median_or_none(all_market_data.get("AWAY_WIN", {}).get("all_odds", []))

        ph, pd, pa = _de_vig_three_way(mh, md, ma)
        if ph is not None:
            mapping = {
                "HOME_OR_DRAW": ph + pd,
                "AWAY_OR_DRAW": pd + pa,
                "HOME_OR_AWAY": ph + pa,
            }
            fair_prob = mapping.get(market_code)

    if fair_prob is None or fair_prob <= 0:
        return None

    fair_odds = round(1 / fair_prob, 2)
    edge = round((best_odds / fair_odds) - 1, 4)

    return {
        "best_odds": round(best_odds, 2),
        "fair_prob": round(fair_prob, 4),
        "fair_odds": fair_odds,
        "edge": edge,
        "books_count": books_count,
    }