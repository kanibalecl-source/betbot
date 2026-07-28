from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UnifiedModelAiUiTests(unittest.TestCase):
    def test_navigation_has_one_model_ai_entry(self) -> None:
        text = (ROOT / "executive_dashboard_theme.py").read_text(encoding="utf-8")
        nav_block = text.split("NAV_ITEMS =", 1)[1].split("NAV_LABELS =", 1)[0]
        self.assertIn('"Model AI"', nav_block)
        self.assertNotIn('"Czat GPT"', nav_block)
        self.assertNotIn('"AI"', nav_block)

    def test_dashboard_routes_unified_page(self) -> None:
        text = (ROOT / "dashboard_streamlit.py").read_text(encoding="utf-8")
        self.assertIn('selected_page == "Model AI"', text)
        self.assertIn("render_model_ai(ai_picks, results)", text)
        self.assertNotIn('selected_page == "Czat GPT"', text)
        self.assertNotIn('selected_page == "AI"', text)

    def test_gpt_is_on_demand_and_does_not_write_model_state(self) -> None:
        dashboard = (ROOT / "dashboard_streamlit.py").read_text(encoding="utf-8")
        engine = (ROOT / "gpt_match_value_engine.py").read_text(encoding="utf-8")
        self.assertIn('"Pełna analiza GPT"', dashboard)
        self.assertIn("run_gpt_analysis_for_item", dashboard)
        helper = engine.split("def run_gpt_analysis_for_item", 1)[1].split(
            "def run_single_gpt_analysis", 1
        )[0]
        self.assertNotIn("ai_picks.csv", helper)
        self.assertNotIn("quality_training.csv", helper)
        self.assertNotIn("active_model", helper)

    def test_model_ai_report_has_readable_progressive_disclosure(self) -> None:
        dashboard = (ROOT / "dashboard_streamlit.py").read_text(encoding="utf-8")
        theme = (ROOT / "executive_dashboard_theme.py").read_text(encoding="utf-8")

        self.assertIn("model-ai-readability-guide", dashboard)
        self.assertIn("model-ai-verdict-metrics", dashboard)
        self.assertIn("model-ai-report-section", dashboard)
        self.assertIn("Źródła i jakość danych", dashboard)
        self.assertIn("model-ai-report-section[open]", theme)
        self.assertIn("grid-template-columns:repeat(2,minmax(0,1fr))", theme)

    def test_model_ai_uses_the_same_table_component_as_prematch(self) -> None:
        dashboard = (ROOT / "dashboard_streamlit.py").read_text(encoding="utf-8")
        ai_renderer = dashboard.split(
            "def render_ai_picks_interactive", 1
        )[1].split("def title", 1)[0]

        self.assertIn("table = html_table(headers", ai_renderer)
        self.assertIn("rows = pick_rows(shown)", ai_renderer)
        self.assertIn('"Buk PL"', ai_renderer)
        self.assertIn("model-ai-types-panel", ai_renderer)
        self.assertNotIn("ai-table-final-head", ai_renderer)
        self.assertNotIn("ai-table-final-row", ai_renderer)

    def test_full_approved_prompt_is_packaged(self) -> None:
        prompt = (ROOT / "model_ai_analysis_prompt_v2.txt").read_text(encoding="utf-8")
        self.assertIn("ostatnie 10 spotkań", prompt)
        self.assertIn("Każdą istotną aktualną informację opatrz linkiem", prompt)
        self.assertIn("W każdej parze wartości muszą sumować się do 100%", prompt)
        self.assertIn("60–75 minut", prompt)
        builder = (ROOT / "gpt_prompts.py").read_text(encoding="utf-8")
        self.assertIn("model_ai_analysis_prompt_v2.txt", builder)

    def test_ui_exposes_provider_failures_instead_of_rendering_fallback(self) -> None:
        dashboard = (ROOT / "dashboard_streamlit.py").read_text(encoding="utf-8")
        self.assertIn("_model_ai_analysis_failed", dashboard)
        self.assertIn("Poprzednia próba analizy nie powiodła się", dashboard)
        self.assertIn("Analiza nie została wykonana:", dashboard)


    def test_shared_controls_use_the_light_blue_action_palette(self) -> None:
        theme = (ROOT / "executive_dashboard_theme.py").read_text(encoding="utf-8")

        self.assertIn("--ui-action:#25a9ef", theme)
        self.assertIn('[data-baseweb="select"]>div>div:last-child', theme)
        self.assertIn("background:var(--ui-action-soft)!important;border-color:#8fd2f3", theme)
        self.assertIn('[data-baseweb="popover"] [role="option"]', theme)
        self.assertIn('[role="listbox"] [role="option"][aria-selected="true"]', theme)
        self.assertIn("background:#cfeefe!important;color:#0b4f7a!important", theme)
        self.assertIn('[data-testid="stSelectbox"] [data-rac][role="group"]', theme)
        self.assertIn('input[role="combobox"][data-rac]', theme)
        self.assertIn('button[data-rac][aria-haspopup="listbox"]', theme)
        self.assertIn('[data-testid="stExpander"] summary', theme)
        self.assertIn("linear-gradient(180deg,#43bcf5 0%,var(--ui-action) 100%)", theme)
        self.assertNotIn("linear-gradient(180deg,#0b2b51,#071e3b)", theme)

    def test_every_page_uses_the_v16_card_navigation_system(self) -> None:
        theme = (ROOT / "executive_dashboard_theme.py").read_text(encoding="utf-8")
        dashboard = (ROOT / "dashboard_streamlit.py").read_text(encoding="utf-8")

        self.assertIn("NAV_PRESENTATION", theme)
        for slug in (
            "live", "prematch", "model_ai", "analytics", "history",
            "bets", "ranking", "volleyball", "handball",
        ):
            self.assertIn(f'"{slug}"', theme)
        self.assertIn('key=f"nav_card_{slug}"', theme)
        self.assertIn("ui-nav-visual", theme)
        self.assertIn("ui-nav-badge", theme)
        self.assertIn("ui-menu-emblem", theme)
        self.assertIn("flex:0 0 76px!important", theme)
        self.assertIn(".stElementContainer:has(.stButton){position:absolute!important;inset:0!important;width:100%!important;height:100%!important", theme)
        self.assertIn(".stElementContainer:has(.ui-nav-visual){position:absolute!important;inset:0!important;z-index:5!important;pointer-events:none!important}", theme)
        self.assertIn('button:not([kind="primary"]):hover{background:transparent!important', theme)
        self.assertIn(':not(:has(button[kind="primary"])):hover .ui-nav-copy strong{color:#168ff5!important}', theme)
        self.assertIn("overflow-y:auto!important", theme)
        self.assertIn("ka-page-metal-title", theme)
        self.assertIn("ka-page-metal-title", dashboard)
        self.assertNotIn(
            "st.markdown('<div class=\"model-ai-metal-title\">MODEL AI</div>'",
            dashboard,
        )


if __name__ == "__main__":
    unittest.main()
