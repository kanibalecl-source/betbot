from flask import jsonify

def register_gpt_analysis_api(app):

    @app.route('/api/gpt-analysis')
    def api_gpt_analysis():

        return jsonify({
            "matches": [
                {
                    "match": "Arsenal vs Chelsea",
                    "bet": "BTTS",
                    "confidence": 81,
                    "value": "HIGH",
                    "risk": "MEDIUM",
                    "status": "PLAY",
                    "analysis": "Arsenal prezentuje bardzo dobrą formę u siebie."
                }
            ],
            "ako": {
                "safe": [
                    "Arsenal vs Chelsea - BTTS"
                ]
            }
        })
