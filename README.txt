1. Wgraj gpt_analysis_tab.py do glownego folderu bota.
2. Wgraj templates/gpt_analysis.html do folderu templates.
3. W app.py dodaj IMPORT:

from gpt_analysis_tab import register_gpt_analysis_routes

4. POD:
app = Flask(__name__)

dodaj:
register_gpt_analysis_routes(app)

5. Wejdz:
https://twoj-bot.up.railway.app/gpt-analysis
