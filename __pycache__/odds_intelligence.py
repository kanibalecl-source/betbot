def value_gap(best_price, avg_price):
    if not best_price or not avg_price or avg_price <= 0:
        return 0.0
    return round((best_price - avg_price) / avg_price, 4)

def odds_quality_label(best_price, avg_price):
    gap = value_gap(best_price, avg_price)
    if gap >= 0.05:
        return "ELITE"
    if gap >= 0.025:
        return "GOOD"
    if gap > 0:
        return "OK"
    return "NONE"
