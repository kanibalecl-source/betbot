from flask import Blueprint, jsonify, render_template

def register_gpt_analysis_routes(app, base_dir=None):

    gpt_bp = Blueprint(
        'gpt_analysis',
        __name__,
        template_folder='templates'
    )

    @gpt_bp.route('/gpt-analysis')
    def gpt_analysis_page():
        return render_template('gpt_analysis.html')

    @gpt_bp.route('/api/gpt-analysis')
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
                    "analysis": "Arsenal prezentuje bardzo dobrą formę u siebie. Chelsea ma problemy defensywne na wyjazdach. Zakład BTTS wygląda korzystnie względem kursu."
                },
                {
                    "match": "Milan vs Roma",
                    "bet": "Over 1.5",
                    "confidence": 77,
                    "value": "MEDIUM",
                    "risk": "LOW",
                    "status": "PLAY",
                    "analysis": "Obie drużyny regularnie kreują sytuacje bramkowe. Tempo meczu powinno sprzyjać overowi."
                }
            ],
            "ako": {
                "safe": [
                    "Arsenal vs Chelsea - BTTS",
                    "Milan vs Roma - Over 1.5"
                ]
            }
        })

    app.register_blueprint(gpt_bp)
