# === AI WATCH TOGGLE FIX ===

# PODMIEŃ:
# --------------------------------
# f'<div><div class="ai-status">{status_label}</div></div></div>'

# NA:
# --------------------------------

f"""
<div>
<div class="ai-status"
onclick="
var el=document.getElementById('details_{key}');
if(el.style.display==='block'){
el.style.display='none';
}else{
el.style.display='block';
}
">
{status_label}
</div>
</div>
</div>
"""

# ORAZ DODAJ POD:
# st.markdown(row_html, unsafe_allow_html=True)

# TEN BLOK:
# --------------------------------

st.markdown(f'''
<div id="details_{{key}}" class="ai-details-box" style="display:none;">
    <div class="ai-details-grid">

        <div class="ai-kpi">
            <div class="ai-kpi-label">xG HOME</div>
            <div class="ai-kpi-value">{{xg_home}}</div>
        </div>

        <div class="ai-kpi">
            <div class="ai-kpi-label">xG AWAY</div>
            <div class="ai-kpi-value">{{xg_away}}</div>
        </div>

        <div class="ai-kpi">
            <div class="ai-kpi-label">BOT ODDS</div>
            <div class="ai-kpi-value">{{bot_odds}}</div>
        </div>

        <div class="ai-kpi">
            <div class="ai-kpi-label">BOOK ODDS</div>
            <div class="ai-kpi-value">{{market_odds}}</div>
        </div>

        <div class="ai-kpi">
            <div class="ai-kpi-label">BOOKMAKER MARGIN</div>
            <div class="ai-kpi-value">{{bookmaker_margin}}</div>
        </div>

    </div>
</div>
''', unsafe_allow_html=True)
