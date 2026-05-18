from __future__ import annotations

import json
from pathlib import Path
from flask import jsonify, render_template, request


def register_gpt_analysis_routes(app, base_dir):
    """Rejestruje osobną zakładkę ANALIZA GPT bez ruszania istniejących route'ów."""
    base_dir = Path(base_dir)

    @app.route("/gpt-analysis")
    def gpt_analysis_page():
        return render_template("gpt_analysis.html", page="gpt_analysis")

    @app.route("/api/gpt-analysis", methods=["GET"])
    def api_gpt_analysis():
        from gpt_match_value_engine import load_latest_report
        return jsonify(load_latest_report(base_dir))

    @app.route("/api/gpt-analysis/run", methods=["POST"])
    def api_gpt_analysis_run():
        from gpt_match_value_engine import run_full_gpt_analysis
        limit = request.json.get("limit") if request.is_json else None
        try:
            limit = int(limit) if limit else None
        except Exception:
            limit = None
        report = run_full_gpt_analysis(base_dir, limit=limit)
        return jsonify(report)
