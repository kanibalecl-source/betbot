# app.py
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="KANIBAL ANALYTICS", layout="wide")

st.markdown("""
<style>
html, body, .stApp{
    background:#050807;
    color:white;
    font-family:Inter,sans-serif;
}
.block-container{
    padding-top:1.5rem;
    max-width:98%;
}
.chart-card{
    background:linear-gradient(180deg,#0b1118,#05080d);
    border:1px solid rgba(124,255,43,.16);
    border-radius:22px;
    padding:14px 14px 2px 14px;
    margin-bottom:18px;
    box-shadow:0 0 28px rgba(124,255,43,.05);
}
.chart-title{
    color:#7CFF2B;
    font-size:20px;
    font-weight:900;
    letter-spacing:.04em;
    margin-bottom:4px;
    text-transform:uppercase;
}
.chart-sub{
    color:#9cab9f;
    font-size:13px;
    margin-bottom:12px;
    font-weight:600;
}
.chart-footer{
    color:#7f9186;
    font-size:12px;
    padding:4px 10px 14px 10px;
    line-height:1.5;
    font-weight:600;
}
.main-title{
    color:white;
    font-size:42px;
    font-weight:1000;
    margin-bottom:24px;
    letter-spacing:.03em;
}
.green-dot{
    width:18px;
    height:18px;
    border-radius:50%;
    background:#6fff2b;
    display:inline-block;
    margin-right:10px;
    box-shadow:0 0 22px rgba(111,255,43,.8);
}
</style>
""", unsafe_allow_html=True)

def premium_chart(title, subtitle, labels, values, y_title, benchmark=None, footer=None, height=340):

    colors = ["#74ff2b" if v >= 0 else "#ff5252" for v in values]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=labels,
        y=values,
        text=[f"{v}%" if y_title != "Liczba typów" else str(v) for v in values],
        textposition="outside",
        marker=dict(
            color=colors,
            line=dict(color="rgba(255,255,255,.12)", width=1.2)
        )
    ))

    if benchmark is not None:
        fig.add_hline(
            y=benchmark,
            line_dash="dash",
            line_color="rgba(255,255,255,.45)",
            annotation_text=f"AVG {benchmark}",
            annotation_position="top left"
        )

    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(8,18,13,.92)",
        margin=dict(l=35,r=20,t=20,b=50),
        font=dict(color="white", size=12),
        showlegend=False,
        xaxis=dict(
            gridcolor="rgba(255,255,255,.04)",
            tickfont=dict(size=11,color="#d8e2dc")
        ),
        yaxis=dict(
            title=y_title,
            gridcolor="rgba(255,255,255,.09)",
            titlefont=dict(color="#9cab9f")
        )
    )

    st.markdown(f'<div class="chart-card"><div class="chart-title">{title}</div><div class="chart-sub">{subtitle}</div>', unsafe_allow_html=True)

    st.plotly_chart(fig, use_container_width=True)

    if footer:
        st.markdown(f'<div class="chart-footer">{footer}</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

confidence = ["50-55","55-60","60-65","65-70","70-75","75-80","80-85","85-90","90-95","95-100"]
win_rate = [38,45,53,60,64,68,72,74,71,62]
confidence_count = [124,178,192,210,186,164,134,93,62,28]

leagues = ["Premier League","La Liga","Serie A","Bundesliga","Ligue 1","Ekstraklasa"]
league_roi = [18.2,12.7,8.4,6.1,3.2,-4.3]
league_win = [63,60,57,56,54,46]

markets = ["Moneyline","Over/Under","BTTS","Handicap","Corner O/U","Exact Score","Cards O/U","1st Half"]
market_win = [65,63,59,57,54,49,42,35]

hours = ["06:00","08:00","10:00","12:00","14:00","16:00","18:00","20:00","22:00","00:00"]
hour_win = [53,54,56,58,61,62,63,60,57,52]

features = ["Team Form","Game Tempo","Odds Value","H2H","Injuries","Motivation","Squad Quality","Weather","Rotation","Public Bets"]
feature_impact = [78,65,58,47,42,36,31,22,18,12]

st.markdown('<div class="main-title"><span class="green-dot"></span>KANIBAL AI ANALYTICS</div>', unsafe_allow_html=True)

c1,c2,c3 = st.columns(3)

with c1:
    premium_chart("Win Rate vs Confidence","Skuteczność AI względem poziomu confidence modelu.",confidence,win_rate,"Win Rate (%)",benchmark=58,footer="Im wyższa pewność modelu, tym większa skuteczność predykcji.")

with c2:
    premium_chart("ROI by League","Zwrot z inwestycji według ligi.",leagues,league_roi,"ROI (%)",benchmark=0,footer="Premier League i La Liga generują najwyższy ROI.")

with c3:
    premium_chart("League Win Rate","Skuteczność AI według ligi.",leagues,league_win,"Win Rate (%)",benchmark=58,footer="Najstabilniejsze ligi osiągają najwyższy win rate.")

c4,c5,c6 = st.columns(3)

with c4:
    premium_chart("Market Efficiency","Skuteczność AI względem rynku.",markets,market_win,"Win Rate (%)",footer="Moneyline i Over/Under pozostają najbardziej stabilne.")

with c5:
    premium_chart("Confidence Distribution","Rozkład ilości typów według confidence.",confidence,confidence_count,"Liczba typów",footer="Najwięcej sygnałów AI pojawia się w strefie 65-75%.")

with c6:
    premium_chart("Hourly Performance","Efektywność AI według godziny meczu.",hours,hour_win,"Win Rate (%)",benchmark=58,footer="Najlepsze wyniki generowane są wieczorem.")

premium_chart("AI Decision Factors","Wpływ poszczególnych czynników na końcową decyzję AI.",features,feature_impact,"Impact (%)",height=420,footer="Dane bazujące na ostatnich 30 dniach działania modelu.")
