
# =========================
# SAFE BADGE RENDER
# =========================

pick_label = str(row.get("best_pick_label", "STANDARD")).upper()

badge_colors = {
    "ULTRA ELITE": "#b026ff",
    "TOP PICK": "#58ff2f",
    "BEST PICK": "#2ecc71",
    "VALUE PICK": "#f1c40f",
    "STANDARD": "#5f5f5f"
}

badge_color = badge_colors.get(pick_label, "#5f5f5f")

st.markdown(
    f'''
    <div style="
        background: linear-gradient(
            90deg,
            {badge_color}22,
            rgba(255,255,255,0.02)
        );
        border: 2px solid {badge_color};
        border-radius: 14px;
        padding: 14px;
        margin-bottom: 18px;
    ">
        <div style="
            color:{badge_color};
            font-size:22px;
            font-weight:900;
        ">
            {pick_label}
        </div>

        <div style="
            color:white;
            margin-top:8px;
            font-size:16px;
        ">
            AI SCORE: {row.get("ai_pick_score", "-")}
        </div>
    </div>
    ''',
    unsafe_allow_html=True
)
