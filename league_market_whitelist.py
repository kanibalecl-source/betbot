ALLOWED_LEAGUES = [
    "Premier League",
    "Bundesliga",
    "Serie A",
    "La Liga",
    "Ligue 1",
    "Eredivisie",
    "Championship"
]

ALLOWED_MARKETS = [
    "Over 2.5",
    "BTTS",
    "Home Win",
    "Away Win",
    "Draw No Bet",
    "Double Chance"
]


def is_league_allowed(league):

    return str(league).strip() in ALLOWED_LEAGUES


def is_market_allowed(market):

    return str(market).strip() in ALLOWED_MARKETS
