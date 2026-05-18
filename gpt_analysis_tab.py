
from flask import Blueprint, jsonify, render_template

def register_gpt_analysis_routes(app, base_dir=None):
    gpt_bp = Blueprint('gpt_analysis', __name__, template_folder='templates')

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
                    "analysis": "Arsenal prezentuje bardzo dobrą formę u siebie, a Chelsea ma problemy defensywne na wyjazdach."
                }
            ],
            "ako": {
                "safe": [
                    "Arsenal vs Chelsea - BTTS"
                ]
            }
        })

    app.register_blueprint(gpt_bp)
