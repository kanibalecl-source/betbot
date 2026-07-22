"""Presentation-only executive UI for the authenticated KANIBAL dashboard."""
from __future__ import annotations

import base64
import html
from pathlib import Path

import streamlit as st


NAV_ITEMS = (
    "Na żywo", "Przedmeczowe", "AI", "Analityka",
    "Historia", "Moje zakłady", "Ranking", "Czat GPT",
)

NAV_LABELS = {
    "Na żywo": "◉   Na żywo",
    "Przedmeczowe": "▣   Przedmeczowe",
    "AI": "✦   AI",
    "Analityka": "▥   Analityka",
    "Historia": "◷   Historia",
    "Moje zakłady": "▤   Moje zakłady",
    "Ranking": "♜   Ranking",
    "Czat GPT": "◌   Czat GPT",
}

PAGE_META = {
    "Na żywo": ("Centrum wydarzeń na żywo", "Aktualne mecze, kursy i sygnały modelu"),
    "Przedmeczowe": ("Centrum przedmeczowe", "Dzisiejsze rekomendacje i sygnały modelu"),
    "AI": ("Centrum modeli AI", "Oceny, uzasadnienia i szczegóły predykcji"),
    "Analityka": ("Analityka jakości", "Wyniki, ryzyko i nadzór Champion–Challenger"),
    "Historia": ("Historia wyników", "Rozliczone typy i pełna ścieżka audytowa"),
    "Moje zakłady": ("Moje zakłady", "Zarządzanie singlami, kuponami i stawkami"),
    "Ranking": ("Ranking skuteczności", "Najlepsze ligi, rynki i strategie"),
    "Czat GPT": ("Asystent analityczny", "Rozmowa z modelem na podstawie aktualnych danych"),
}


def _image_uri(path: Path) -> str:
    try:
        suffix = path.suffix.lower().lstrip(".") or "png"
        mime = "jpeg" if suffix in {"jpg", "jpeg"} else suffix
        return f"data:image/{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")
    except Exception:
        return ""


THEME_CSS = r"""
<style>
:root{
  --ui-navy:#071a35;--ui-navy-2:#0b2448;--ui-blue:#1478e8;--ui-blue-2:#28a8f5;
  --ui-bg:#f4f7fb;--ui-surface:#ffffff;--ui-surface-2:#f8fafc;--ui-line:#dfe6ef;
  --ui-text:#132238;--ui-muted:#69788c;--ui-green:#20a36a;--ui-amber:#d98b18;--ui-red:#d95151;
  --ui-shadow:0 8px 24px rgba(15,35,65,.075);--ui-radius:12px;
}
html,body,.stApp,[data-testid="stAppViewContainer"]{
  background:var(--ui-bg)!important;color:var(--ui-text)!important;
  font-family:Inter,"Segoe UI",Arial,sans-serif!important;
}
header[data-testid="stHeader"]{height:0!important;background:transparent!important}
[data-testid="stToolbar"],#MainMenu,footer,[data-testid="stStatusWidget"]{display:none!important}
.block-container{width:100%!important;max-width:1720px!important;padding:0 28px 28px!important}

/* Permanent navigation rail */
[data-testid="stSidebar"]{width:264px!important;min-width:264px!important;background:linear-gradient(180deg,#06172f 0%,#082342 100%)!important;border-right:1px solid rgba(255,255,255,.08)!important}
[data-testid="stSidebar"]>div:first-child{width:264px!important;padding:0!important}
[data-testid="stSidebar"] [data-testid="stSidebarContent"]{padding:0!important}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{gap:0!important}
.ui-side-brand{height:128px;padding:2px 24px 18px;border-bottom:1px solid rgba(255,255,255,.08);box-sizing:border-box}
.ui-side-logo{display:flex;align-items:center;gap:12px}.ui-side-logo img{width:54px;height:54px;object-fit:contain}
.ui-side-word strong{display:block;color:#fff;font-size:20px;letter-spacing:.045em;line-height:1}.ui-side-word span{display:block;color:#b8c7da;font-size:8px;font-weight:800;letter-spacing:.28em;margin-top:7px}
[data-testid="stSidebar"] .ui-nav-start+div{margin-top:40px!important}
[data-testid="stSidebar"] .stButton{padding:0 10px 4px!important}
[data-testid="stSidebar"] .stButton button{height:47px!important;min-height:47px!important;margin:0!important;padding:0 17px!important;border:0!important;border-radius:8px!important;background:transparent!important;color:#c8d4e2!important;box-shadow:none!important;justify-content:flex-start!important;font-size:14px!important;font-weight:650!important;letter-spacing:0!important;text-align:left!important}
[data-testid="stSidebar"] .stButton button:hover{background:rgba(255,255,255,.07)!important;color:#fff!important}
[data-testid="stSidebar"] .stButton button[kind="primary"]{background:linear-gradient(90deg,#1189ee,#24a9f5)!important;color:#fff!important;box-shadow:0 8px 22px rgba(0,122,230,.28)!important}
.ui-side-footer{position:fixed;left:0;bottom:65px;width:264px;border-top:1px solid rgba(255,255,255,.09);background:#071b35}
.ui-online{display:flex;align-items:center;gap:10px;padding:18px 25px;color:#b7c5d5;font-size:12px;border-bottom:1px solid rgba(255,255,255,.07)}
.ui-online:before{content:"";width:9px;height:9px;border-radius:50%;background:#59cf78;box-shadow:0 0 0 4px rgba(89,207,120,.12)}
[data-testid="stSidebar"] .st-key-executive_logout{position:fixed!important;left:10px!important;bottom:10px!important;width:244px!important;z-index:20!important}
[data-testid="stSidebar"] .st-key-executive_logout .stButton{padding:0!important}
[data-testid="stSidebar"] .st-key-executive_logout button{height:40px!important;min-height:40px!important;background:rgba(255,255,255,.055)!important;border:1px solid rgba(255,255,255,.12)!important;color:#eaf1f8!important;box-shadow:none!important;justify-content:center!important}
[data-testid="stSidebar"] .st-key-executive_logout button:hover{background:rgba(255,255,255,.10)!important;border-color:rgba(255,255,255,.22)!important}

/* Top workspace bar */
.ui-topbar{height:88px;margin:0 -28px 22px;padding:0 31px;display:flex;align-items:center;justify-content:space-between;gap:24px;background:linear-gradient(100deg,#071a35,#06162d);color:#fff;box-shadow:0 3px 16px rgba(7,26,53,.16)}
.ui-heading h1{font-size:25px;line-height:1.1;margin:0 0 6px;color:#fff!important;font-weight:800;letter-spacing:-.02em}.ui-heading p{margin:0;color:#9fb0c5;font-size:12px}
.ui-top-tools{display:flex;align-items:center;gap:12px}.ui-search,.ui-date,.ui-tool{height:42px;border:1px solid rgba(255,255,255,.17);border-radius:9px;display:flex;align-items:center;color:#bdc9d7;background:rgba(255,255,255,.025);box-sizing:border-box}
.ui-search{width:310px;padding:0 15px;gap:10px;font-size:12px}.ui-date{padding:0 16px;color:#eef4fa;font-size:12px}.ui-tool{width:42px;justify-content:center;font-size:17px}.ui-user-dot{width:38px;height:38px;border:1px solid rgba(255,255,255,.22);border-radius:50%;display:grid;place-items:center;font-weight:800}

/* Brand banner */
.ka-page-banner,.ka-page-banner.ka-image-banner,.kanibal-hero{height:136px!important;width:100%!important;margin:0 0 18px!important;border:0!important;border-radius:var(--ui-radius)!important;overflow:hidden!important;background:#071a35!important;box-shadow:var(--ui-shadow)!important}
.ka-page-banner img,.ka-page-banner.ka-image-banner img,.kanibal-hero img{width:100%!important;height:100%!important;display:block!important;object-fit:cover!important;object-position:center!important;filter:saturate(.86) contrast(1.03)!important}
.ka-page-banner:after,.ka-page-banner-content{display:none!important}

/* Headings and KPI cards */
.ka-title,.ka-section-heading{display:flex!important;align-items:center!important;justify-content:space-between!important;min-height:34px!important;margin:0 2px 12px!important;color:var(--ui-text)!important;font-size:18px!important;font-weight:800!important;text-transform:none!important;letter-spacing:-.01em!important;text-shadow:none!important}
.ka-title-meta{color:#8694a6!important;font-size:9px!important;font-weight:750!important;letter-spacing:.06em!important}.status-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--ui-green);margin:0 4px}.ka-dot{display:none!important}
.ka-grid{display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:18px!important;margin:0 0 18px!important}
.ka-card{min-height:108px!important;padding:19px 20px!important;display:grid!important;grid-template-columns:58px 1fr!important;grid-template-rows:auto auto auto!important;column-gap:15px!important;align-content:center!important;background:var(--ui-surface)!important;border:1px solid var(--ui-line)!important;border-radius:var(--ui-radius)!important;box-shadow:var(--ui-shadow)!important}
.ka-metric-icon{grid-row:1/4;width:52px;height:52px;display:grid;place-items:center;align-self:center;border-radius:50%;background:#eaf3ff;color:#126ede;font-size:27px}.ka-label{grid-column:2;margin:0 0 3px!important;color:var(--ui-muted)!important;font-size:11px!important;font-weight:650!important;text-transform:none!important;letter-spacing:0!important}.ka-value{grid-column:2;color:var(--ui-text)!important;font-size:29px!important;line-height:1!important;font-weight:850!important;font-variant-numeric:tabular-nums}.ka-value.positive{color:#126ede!important}.ka-sub{grid-column:2;margin:7px 0 0!important;color:#94a1b1!important;font-size:9px!important;font-weight:650!important;text-transform:uppercase!important;letter-spacing:.05em!important}.sparkline{display:none!important}

/* Panels, layouts and data */
[data-testid="stHorizontalBlock"]{gap:18px!important;align-items:stretch!important}[data-testid="column"]>div{height:100%}
.ka-panel,.ka-viz,.pro-chart-card,.ai-detail-final,div[data-testid="stDataFrame"],div[data-testid="stMetric"]{background:var(--ui-surface)!important;border:1px solid var(--ui-line)!important;border-radius:var(--ui-radius)!important;box-shadow:var(--ui-shadow)!important;color:var(--ui-text)!important}
.ka-panel{padding:16px 17px!important;margin:0 0 18px!important}.ka-panel h3,.ka-viz-title,.pro-chart-title{margin:0 0 13px!important;color:var(--ui-text)!important;font-size:14px!important;font-weight:800!important;text-transform:none!important;letter-spacing:0!important}.ka-panel .ka-sub,.ka-viz-sub{color:var(--ui-muted)!important;text-transform:none!important;letter-spacing:0!important;font-size:11px!important;line-height:1.55!important}
.ka-table-scroll{width:100%!important;overflow:auto!important;border:1px solid #e5eaf1!important;border-radius:9px!important;background:#fff!important}.ka-table{width:100%!important;min-width:760px!important;border-collapse:collapse!important;color:var(--ui-text)!important;font-size:11px!important}.ka-table th{padding:11px 12px!important;background:#f7f9fc!important;border-bottom:1px solid #dfe6ee!important;color:#728196!important;font-size:9px!important;font-weight:750!important;letter-spacing:.04em!important;text-align:left!important;text-transform:none!important;white-space:nowrap!important}.ka-table td{padding:11px 12px!important;background:#fff!important;border-bottom:1px solid #edf1f5!important;color:#26364a!important;vertical-align:middle!important}.ka-table tr:nth-child(even) td{background:#fbfcfe!important}.ka-table tr:hover td{background:#f2f7fd!important}.ka-table b{color:#15243a!important}.green{color:#0875df!important;font-weight:800!important}.yellow{color:var(--ui-amber)!important;font-weight:800!important}.red{color:var(--ui-red)!important;font-weight:800!important}
.pill{display:inline-flex!important;align-items:center!important;justify-content:center!important;min-width:62px!important;padding:5px 8px!important;border-radius:6px!important;font-size:9px!important;font-weight:800!important;text-transform:uppercase!important}.pill-green{background:#e8f8f1!important;color:#16865b!important}.pill-yellow{background:#fff4df!important;color:#bd7715!important}.pill-red{background:#feecec!important;color:#c94545!important}.progress,.ai-conf-track{height:7px!important;min-width:76px!important;background:#e3e8ee!important;border-radius:99px!important;overflow:hidden!important}.progress span,.ai-conf-fill{height:100%!important;display:block!important;background:linear-gradient(90deg,#197ce5,#28a8f5)!important;border-radius:99px!important}
.ka-bar-row{color:#506076!important}.ka-bar-track{background:#e5eaf0!important}.ka-bar-fill{background:linear-gradient(90deg,#1675df,#29a8f5)!important}.ka-bar-value{color:#126fdc!important}.ka-viz{padding:16px 17px!important}.ka-insight{background:#f8fafc!important;border:1px solid #e7ecf2!important;border-radius:9px!important}.ka-insight b{color:#1d2d43!important}.ka-insight span{color:#718095!important}.ka-insight-icon{color:#1679df!important}

/* Inner tabs become calm segmented controls */
.stTabs [data-baseweb="tab-list"],[role="tablist"]{display:flex!important;gap:3px!important;min-height:46px!important;width:100%!important;margin:0 0 16px!important;padding:4px!important;overflow-x:auto!important;background:#fff!important;border:1px solid var(--ui-line)!important;border-radius:10px!important;box-shadow:none!important}
.stTabs [data-baseweb="tab"],[role="tab"]{position:relative!important;min-width:130px!important;height:38px!important;min-height:38px!important;padding:0 16px!important;border:0!important;border-radius:7px!important;clip-path:none!important;background:transparent!important;color:#66768a!important;font-size:11px!important;font-weight:700!important;letter-spacing:0!important;text-transform:none!important;box-shadow:none!important}.stTabs [data-baseweb="tab"]:before,.stTabs [data-baseweb="tab"]:after,[role="tab"]:before,[role="tab"]:after{display:none!important}.stTabs [aria-selected="true"],[role="tab"][aria-selected="true"],[role="tab"][data-selected="true"]{background:#1478e8!important;color:#fff!important;box-shadow:0 5px 14px rgba(20,120,232,.18)!important}

/* AI details */
.ai-table-final{background:#fff!important;border:1px solid var(--ui-line)!important;border-radius:10px!important;box-shadow:none!important}.ai-table-final-head{min-height:42px!important;background:#f6f8fb!important;color:#728196!important;font-size:9px!important}.ai-table-final-row{min-height:56px!important;background:#fff!important;color:#26364a!important;font-size:11px!important;border-bottom:1px solid #edf1f5!important}.ai-cell-main,.ai-cell-num{color:#17283f!important}.ai-cell-sub{color:#8b98a8!important}.ai-edge-plus{color:#0d78df!important}.ai-status-inline,.ai-status-text{height:28px!important;min-width:78px!important;border-radius:6px!important;background:#eaf4ff!important;border:0!important;color:#1474d9!important;font-size:9px!important}.ai-detail-final{padding:14px!important}.ai-detail-final-box{background:#f8fafc!important;border:1px solid #e5eaf0!important;border-radius:9px!important}.ai-detail-final-title{color:#17283f!important}.ai-engine-line{color:#5f6f83!important}

/* Native controls */
.stButton>button,button[kind="primary"],[data-testid="stFormSubmitButton"] button{min-height:40px!important;border-radius:8px!important;border:1px solid #0d315b!important;background:linear-gradient(180deg,#0b2b51,#071e3b)!important;color:#fff!important;font-size:11px!important;font-weight:800!important;letter-spacing:.01em!important;text-transform:none!important;box-shadow:0 5px 14px rgba(7,30,59,.14)!important}.stButton>button:hover{background:#124779!important;border-color:#124779!important}
[data-baseweb="input"],[data-baseweb="select"]>div,[data-baseweb="textarea"],[data-testid="stNumberInput"]>div>div{min-height:40px!important;border-radius:8px!important;background:#fff!important;border-color:#dce4ed!important;color:#1f3046!important}input,textarea{color:#1f3046!important}label,[data-testid="stWidgetLabel"]{color:#607086!important;font-size:10px!important;font-weight:700!important;text-transform:none!important;letter-spacing:0!important}[data-testid="stExpander"]{border:1px solid var(--ui-line)!important;border-radius:9px!important;background:#fff!important}[data-testid="stAlert"]{border-radius:9px!important;border:1px solid var(--ui-line)!important;color:#33445a!important}.footer-ka{display:flex!important;justify-content:space-between!important;margin-top:18px!important;padding:16px 4px!important;border-top:1px solid var(--ui-line)!important;color:#8290a1!important;font-size:9px!important}

/* Country flags */
.ka-country-label,.ka-team-name{display:inline-flex;align-items:center;gap:7px}.ka-country-flag{display:inline-flex;width:22px;height:16px;border:1px solid #d5dde7;border-radius:3px;overflow:hidden;background:#fff;font-size:15px}.ka-country-flag svg{width:100%;height:100%}.ka-match-separator{margin:0 6px;color:#9aa6b5}

@media(max-width:1200px){[data-testid="stSidebar"]{width:220px!important;min-width:220px!important}[data-testid="stSidebar"]>div:first-child{width:220px!important}.ui-side-footer{width:220px}[data-testid="stSidebar"] .st-key-executive_logout{width:200px!important}.ka-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}.ui-search{display:none}.block-container{padding-left:18px!important;padding-right:18px!important}.ui-topbar{margin-left:-18px;margin-right:-18px}}
@media(max-width:760px){[data-testid="stSidebar"]{display:none!important}.block-container{padding:0 10px 18px!important}.ui-topbar{margin:0 -10px 14px;padding:0 14px;height:72px}.ui-heading h1{font-size:19px}.ui-heading p,.ui-date{display:none}.ka-grid{grid-template-columns:1fr!important}.ka-page-banner,.ka-page-banner.ka-image-banner{height:92px!important}}
</style>
"""


def inject_executive_theme() -> None:
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def render_navigation(base_dir: Path) -> str:
    logo = _image_uri(base_dir / "kanibal_logo.png")
    image = f'<img src="{logo}" alt="KANIBAL">' if logo else ""
    with st.sidebar:
        st.markdown(
            '<div class="ui-side-brand"><div class="ui-side-logo">'
            f'{image}<div class="ui-side-word"><strong>KANIBAL</strong><span>ANALYTICS</span></div>'
            '</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="ui-nav-start"></div>', unsafe_allow_html=True)
        if st.session_state.get("executive_navigation") not in NAV_ITEMS:
            st.session_state.executive_navigation = "Przedmeczowe"
        for item in NAV_ITEMS:
            active = st.session_state.executive_navigation == item
            if st.button(
                NAV_LABELS[item],
                key=f"executive_nav_{item}",
                use_container_width=True,
                type="primary" if active else "secondary",
            ):
                st.session_state.executive_navigation = item
        selected = st.session_state.executive_navigation
        st.markdown(
            '<div class="ui-side-footer"><div class="ui-online">System online</div></div>',
            unsafe_allow_html=True,
        )
        if st.button("Wyloguj", key="executive_logout", use_container_width=True):
            st.session_state.auth_ok = False
            st.session_state.auth_user = ""
            st.rerun()
    return selected


def render_workspace_bar(page: str) -> None:
    title, subtitle = PAGE_META.get(page, (page, "KANIBAL Analytics"))
    st.markdown(
        '<div class="ui-topbar">'
        f'<div class="ui-heading"><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div>'
        '<div class="ui-top-tools"><div class="ui-search">⌕ &nbsp; Szukaj meczu lub ligi</div>'
        '<div class="ui-date">▣ &nbsp; 22 lip 2026 &nbsp;⌄</div><div class="ui-tool">♢</div>'
        '<div class="ui-user-dot">A</div></div></div>',
        unsafe_allow_html=True,
    )
