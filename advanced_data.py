import requests
from config import API_FOOTBALL_KEY

def get_fixture_team_stats(fixture_id: int):
    url = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={fixture_id}"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    data = response.json().get("response", [])
    if len(data) < 2:
        return None

    def stat_value(stats_list, label):
        for item in stats_list:
            if item.get("type") == label:
                value = item.get("value")
                if value is None:
                    return 0
                if isinstance(value, str):
                    value = value.replace("%", "")
                try:
                    return float(value)
                except Exception:
                    return 0
        return 0

    home_stats = data[0].get("statistics", [])
    away_stats = data[1].get("statistics", [])
    shots_home = stat_value(home_stats, "Total Shots")
    shots_away = stat_value(away_stats, "Total Shots")
    sot_home = stat_value(home_stats, "Shots on Goal")
    sot_away = stat_value(away_stats, "Shots on Goal")
    corners_home = stat_value(home_stats, "Corner Kicks")
    corners_away = stat_value(away_stats, "Corner Kicks")

    xg_proxy_home = round((sot_home * 0.28) + (shots_home * 0.05) + (corners_home * 0.03), 2)
    xg_proxy_away = round((sot_away * 0.28) + (shots_away * 0.05) + (corners_away * 0.03), 2)

    return {
        "xg_proxy_home": xg_proxy_home,
        "xg_proxy_away": xg_proxy_away,
    }
