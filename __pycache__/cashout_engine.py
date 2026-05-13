def cashout_signal(bet, live_odds, minute, pressure_home=0, pressure_away=0):
    entry_odds = bet.get("odds_taken")

    if not entry_odds or not live_odds:
        return "HOLD ❓"

    drop = (entry_odds - live_odds) / entry_odds

    # 🔥 DUŻY PROFIT
    if drop >= 0.25:
        return "CASHOUT 🔥 (value captured)"

    # ⚠️ ŚREDNI PROFIT + CZAS
    if drop >= 0.15 and minute > 60:
        return "CASHOUT ⚠️ (secure profit)"

    # ❌ NEGATYWNE MOMENTUM
    if pressure_away > pressure_home * 1.5:
        return "CASHOUT ❌ (momentum lost)"

    # ⏳ KOŃCÓWKA
    if minute > 75 and drop >= 0.10:
        return "CASHOUT ⏳ (late game)"

    return "HOLD ✅"