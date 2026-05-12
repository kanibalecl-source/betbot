
SOURCES = [
    "API_FOOTBALL",
    "UNDERSTAT",
    "SOFASCORE",
    "FOTMOB",
    "ODDS_API"
]

class MultiSourceIngestion:
    def fetch(self):
        return {"sources": SOURCES, "status": "ok"}
