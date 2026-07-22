from database import get_conn, init_db
from api_results import get_match_result_by_id, get_closing_odds_safe


def evaluate_market(market, home_goals, away_goals):
    total = home_goals + away_goals

    if market == "HOME_WIN":
        return home_goals > away_goals
    if market == "DRAW":
        return home_goals == away_goals
    if market == "AWAY_WIN":
        return away_goals > home_goals
    if market == "BTTS_YES":
        return home_goals > 0 and away_goals > 0
    if market == "BTTS_NO":
        return home_goals == 0 or away_goals == 0
    if market == "OVER_2.5":
        return total > 2.5
    if market == "UNDER_2.5":
        return total < 2.5
    if market == "OVER_1.5":
        return total > 1.5
    if market == "UNDER_1.5":
        return total < 1.5

    return None


def settle_open_bets():
    init_db()
    conn = get_conn()
    open_bets = conn.execute("SELECT * FROM bets WHERE status = 'OPEN'").fetchall()

    updated = 0

    for bet in open_bets:
        fixture_id = bet["fixture_id"]

        result = get_match_result_by_id(fixture_id)
        if not result or not result.get("finished"):
            continue

        home_goals = int(result["home_goals"])
        away_goals = int(result["away_goals"])

        won = evaluate_market(bet["market"], home_goals, away_goals)
        if won is None:
            continue

        stake = float(bet["stake"])
        odds = float(bet["odds"])

        profit = (stake * (odds - 1)) if won else -stake
        result_text = "WIN" if won else "LOSS"

        closing_odds = get_closing_odds_safe(
            fixture_id=bet["fixture_id"],
            odds_event_id=bet["odds_event_id"],
            home_team=bet["home_team"],
            away_team=bet["away_team"],
            market_key=bet["odds_api_market"] or "h2h",
            outcome_name=bet["closing_outcome_name"]
        )

        clv = None
        if closing_odds:
            # Positive CLV means the taken price was better than the close.
            clv = (odds / float(closing_odds)) - 1

        conn.execute("""
            UPDATE bets
            SET status = 'CLOSED',
                result = ?,
                profit = ?,
                closing_odds = ?,
                clv = ?
            WHERE id = ?
        """, (result_text, profit, closing_odds, clv, bet["id"]))

        updated += 1

    conn.commit()
    conn.close()
    return updated


def main():
    updated = settle_open_bets()
    print(f"Rozliczono betów: {updated}")


if __name__ == "__main__":
    main()
