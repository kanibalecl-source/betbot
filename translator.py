from config import SPORT_KEY_TO_PL
from lang_pl import BET_TRANSLATIONS, LEAGUE_TRANSLATIONS, RATING_TRANSLATIONS


def translate_bet(code):
    return BET_TRANSLATIONS.get(str(code), str(code))


def translate_league(name):
    txt = str(name)
    if txt in SPORT_KEY_TO_PL:
        return SPORT_KEY_TO_PL[txt]
    return LEAGUE_TRANSLATIONS.get(txt, txt)


def translate_rating(rating):
    return RATING_TRANSLATIONS.get(str(rating), str(rating))
