"""KANIBAL ANALYTICS — approved 1:1 trading-desk visual system.

This module is deliberately presentation-only.  It does not read or mutate bot
data, which keeps the visual upgrade isolated from prediction and settlement
logic.
"""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st


THEME_CSS = r"""
<style>
:root {
  --ka-bg: #050708;
  --ka-bg-2: #07100b;
  --ka-panel: #0a1012;
  --ka-panel-2: #0d1517;
  --ka-panel-3: #111a1c;
  --ka-line: rgba(218, 231, 223, .12);
  --ka-line-soft: rgba(218, 231, 223, .075);
  --ka-lime: #7cff2b;
  --ka-lime-2: #9cff32;
  --ka-lime-soft: rgba(124, 255, 43, .10);
  --ka-amber: #ffca45;
  --ka-red: #ff4d43;
  --ka-text: #f4f8f2;
  --ka-muted: #98a59e;
  --ka-shadow: 0 14px 34px rgba(0, 0, 0, .34);
  --ka-radius: 8px;
}

html, body, [data-testid="stAppViewContainer"], .stApp {
  background:
    radial-gradient(circle at 85% 0%, rgba(124,255,43,.055), transparent 25%),
    linear-gradient(180deg, var(--ka-bg) 0%, var(--ka-bg-2) 46%, var(--ka-bg) 100%) !important;
  color: var(--ka-text) !important;
  font-family: Inter, "Segoe UI", Arial, sans-serif !important;
}

header[data-testid="stHeader"] { height: 0 !important; background: transparent !important; }
[data-testid="stToolbar"], #MainMenu, footer, [data-testid="stStatusWidget"] { display:none !important; }
.block-container {
  width: 100% !important;
  max-width: 1920px !important;
  padding: 12px 22px 22px !important;
}

/* App utility bar */
.ka-appbar {
  height: 44px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:18px;
  margin:0 0 8px;
  color:#dce5df;
}
.ka-appbar-brand { display:flex; align-items:center; gap:9px; min-width:220px; }
.ka-appbar-brand img { display:block; width:38px; height:38px; object-fit:contain; object-position:left center; }
.ka-brand-word { display:flex; flex-direction:column; line-height:.9; }
.ka-brand-word strong { color:#f7faf8; font-size:18px; font-weight:950; letter-spacing:.045em; }
.ka-brand-word span { color:#aab5af; font-size:7px; font-weight:850; letter-spacing:.31em; margin-top:6px; }
.ka-appbar-tools { display:flex; align-items:center; gap:18px; font-size:12px; color:#aab5af; }
.ka-live { display:inline-flex; align-items:center; gap:8px; color:#dbe5df; font-weight:800; letter-spacing:.05em; }
.ka-live:before, .status-dot { content:""; width:9px; height:9px; border-radius:50%; background:var(--ka-lime); box-shadow:0 0 12px rgba(124,255,43,.7); display:inline-block; }
.ka-time { font-variant-numeric:tabular-nums; color:#87948d; padding-right:18px; border-right:1px solid var(--ka-line); }
.ka-user { display:flex; align-items:center; gap:10px; color:#e9efeb; }
.ka-avatar { width:28px; height:28px; border:1px solid rgba(124,255,43,.35); border-radius:50%; display:grid; place-items:center; color:var(--ka-lime); font-weight:950; background:#11191b; }

/* Main and nested navigation */
.stTabs [data-baseweb="tab-list"] {
  display:grid !important;
  grid-auto-flow:column !important;
  grid-auto-columns:minmax(118px, 1fr) !important;
  gap:0 !important;
  width:100% !important;
  margin:0 0 8px !important;
  padding:0 10px !important;
  overflow-x:auto !important;
  background:linear-gradient(180deg,#0a1012,#080d0f) !important;
  border:1px solid var(--ka-line) !important;
  border-radius:var(--ka-radius) !important;
  box-shadow:var(--ka-shadow) !important;
}
.stTabs [data-baseweb="tab"] {
  min-width:118px !important;
  height:50px !important;
  padding:0 12px !important;
  border:0 !important;
  border-right:1px solid var(--ka-line-soft) !important;
  background:transparent !important;
  color:#b8c3bd !important;
  font-size:11px !important;
  font-weight:850 !important;
  letter-spacing:.055em !important;
  text-transform:uppercase !important;
}
.stTabs [data-baseweb="tab"]:hover { color:#fff !important; background:rgba(255,255,255,.018) !important; }
.stTabs [aria-selected="true"] {
  color:var(--ka-lime) !important;
  background:linear-gradient(180deg,rgba(124,255,43,.04),transparent) !important;
  box-shadow:inset 0 -2px 0 var(--ka-lime) !important;
}
.stTabs [data-baseweb="tab-highlight"] { display:none !important; }
.stTabs [data-baseweb="tab-panel"] { padding-top:0 !important; }

/* Primary eight-section menu: exact segmented terminal navigation. */
.stTabs [data-baseweb="tab-list"]:has(> [data-baseweb="tab"]:nth-child(8)) {
  grid-template-columns:repeat(8,minmax(0,1fr)) !important;
  grid-auto-columns:unset !important;
  height:52px !important;
  margin:0 0 12px !important;
  padding:0 !important;
  overflow:hidden !important;
  background:#090e10 !important;
  border:1px solid #20282a !important;
  border-radius:8px !important;
  box-shadow:0 7px 24px rgba(0,0,0,.24) !important;
}
.stTabs [data-baseweb="tab-list"]:has(> [data-baseweb="tab"]:nth-child(8)) > [data-baseweb="tab"] {
  min-width:0 !important;
  width:100% !important;
  height:50px !important;
  padding:0 8px !important;
  justify-content:center !important;
  border-right:1px solid #1b2325 !important;
  color:#a7b0ae !important;
  font-size:11px !important;
  font-weight:850 !important;
  letter-spacing:.025em !important;
  white-space:nowrap !important;
}
.stTabs [data-baseweb="tab-list"]:has(> [data-baseweb="tab"]:nth-child(8)) > [data-baseweb="tab"]:last-of-type { border-right:0 !important; }
.stTabs [data-baseweb="tab-list"]:has(> [data-baseweb="tab"]:nth-child(8)) > [data-baseweb="tab"][aria-selected="true"] {
  color:#83ff3e !important;
  background:linear-gradient(180deg,#102313 0%,#0c1710 100%) !important;
  box-shadow:inset 0 -2px 0 #83ff3e !important;
}
.stTabs [data-baseweb="tab-list"]:has(> [data-baseweb="tab"]:nth-child(8)) > [data-baseweb="tab"]:hover {
  color:#eef4f0 !important;
  background:#0d1416 !important;
}

/* Exact approved hero treatment */
.ka-page-banner, .ka-page-banner.ka-image-banner, .kanibal-hero {
  width:100% !important;
  min-height:0 !important;
  height:198px !important;
  margin:0 0 12px !important;
  overflow:hidden !important;
  position:relative !important;
  border:1px solid rgba(218,231,223,.14) !important;
  border-radius:var(--ka-radius) !important;
  background:#030506 !important;
  box-shadow:0 16px 42px rgba(0,0,0,.38) !important;
}
.ka-page-banner img, .ka-page-banner.ka-image-banner img, .kanibal-hero img {
  display:block !important;
  width:100% !important;
  height:100% !important;
  object-fit:contain !important;
  object-position:center center !important;
  opacity:1 !important;
  filter:none !important;
}
.ka-page-banner:after, .ka-page-banner-content { display:none !important; }

/* Section headings */
.ka-title, .ka-section-heading {
  min-height:34px;
  display:flex !important;
  align-items:center !important;
  justify-content:space-between !important;
  gap:14px !important;
  margin:4px 6px 8px !important;
  color:#f8fbf9 !important;
  font-size:20px !important;
  line-height:1.1 !important;
  font-weight:900 !important;
  letter-spacing:.03em !important;
  text-transform:uppercase !important;
  text-shadow:none !important;
}
.ka-title-left { display:flex; align-items:center; gap:12px; }
.ka-title-meta { display:flex; align-items:center; gap:9px; color:#89968f; font-size:10px; font-weight:750; letter-spacing:.055em; }
.ka-title-meta .status-dot { width:7px; height:7px; }
.ka-dot { display:none !important; }

/* KPI system */
.ka-grid {
  display:grid !important;
  grid-template-columns:repeat(4,minmax(0,1fr)) !important;
  gap:12px !important;
  margin:0 0 10px !important;
}
.ka-card {
  min-height:96px !important;
  display:grid !important;
  grid-template-columns:46px 1fr !important;
  grid-template-rows:auto auto auto !important;
  column-gap:14px !important;
  align-content:center !important;
  padding:13px 17px !important;
  border:1px solid var(--ka-line) !important;
  border-radius:var(--ka-radius) !important;
  background:linear-gradient(135deg,rgba(15,23,25,.98),rgba(8,13,15,.99)) !important;
  box-shadow:var(--ka-shadow) !important;
}
.ka-card:before { display:none !important; }
.ka-metric-icon {
  grid-row:1 / 4;
  width:42px; height:42px;
  display:grid; place-items:center;
  align-self:center;
  color:var(--ka-lime);
  font-size:32px;
  font-weight:300;
  line-height:1;
}
.ka-label { grid-column:2; color:#9aa69f !important; font-size:10px !important; font-weight:800 !important; letter-spacing:.10em !important; text-transform:uppercase !important; margin:0 0 4px !important; }
.ka-value { grid-column:2; color:#f7faf8 !important; font-size:27px !important; font-weight:900 !important; line-height:1 !important; font-variant-numeric:tabular-nums; }
.ka-value.positive { color:var(--ka-lime) !important; }
.ka-sub { grid-column:2; min-height:12px !important; margin:6px 0 0 !important; color:#8a9690 !important; font-size:9px !important; font-weight:750 !important; letter-spacing:.06em !important; text-transform:uppercase !important; }
.sparkline { display:none !important; }

/* Panels and layout */
.ka-panel, .pro-chart-card, .ai-detail-final, div[data-testid="stDataFrame"], div[data-testid="stMetric"] {
  border:1px solid var(--ka-line) !important;
  border-radius:var(--ka-radius) !important;
  background:linear-gradient(180deg,rgba(13,21,23,.98),rgba(7,12,14,.99)) !important;
  box-shadow:var(--ka-shadow) !important;
}
.ka-panel { padding:12px 14px !important; margin:0 0 10px !important; }
.ka-panel h3, .pro-chart-title {
  margin:0 0 9px !important;
  color:#f1f5f2 !important;
  font-size:13px !important;
  line-height:1.2 !important;
  font-weight:900 !important;
  letter-spacing:.065em !important;
  text-transform:uppercase !important;
}
.ka-panel .ka-sub { display:block; color:#9aa69f !important; text-transform:none !important; letter-spacing:0 !important; font-size:11px !important; line-height:1.5 !important; }
[data-testid="stHorizontalBlock"] { gap:10px !important; align-items:stretch !important; }
[data-testid="column"] > div { height:100%; }

/* Tables */
.ka-table-scroll { width:100% !important; overflow:auto !important; border:1px solid var(--ka-line-soft) !important; border-radius:6px !important; background:#071012 !important; }
.ka-table { width:100% !important; min-width:760px; table-layout:auto !important; border-collapse:separate !important; border-spacing:0 !important; color:#eef4f0 !important; font-size:11px !important; }
.ka-table th {
  position:sticky !important; top:0 !important; z-index:2 !important;
  padding:9px 10px !important;
  background:#10181a !important;
  border-bottom:1px solid rgba(124,255,43,.16) !important;
  color:#a7b2ac !important;
  font-size:9px !important;
  font-weight:850 !important;
  letter-spacing:.075em !important;
  text-align:left !important;
  text-transform:uppercase !important;
  white-space:nowrap !important;
}
.ka-table td { padding:9px 10px !important; background:#091113 !important; border-bottom:1px solid var(--ka-line-soft) !important; color:#e9efeb !important; vertical-align:middle !important; }
.ka-table tr:nth-child(even) td { background:#0b1416 !important; }
.ka-table tr:hover td { background:rgba(124,255,43,.055) !important; }
.ka-table b { color:#fff; }
.green { color:var(--ka-lime) !important; font-weight:900 !important; }
.yellow { color:var(--ka-amber) !important; font-weight:900 !important; }
.red { color:var(--ka-red) !important; font-weight:900 !important; }
.pill { display:inline-flex !important; align-items:center !important; justify-content:center !important; min-width:66px !important; padding:4px 8px !important; border-radius:5px !important; font-size:9px !important; font-weight:900 !important; letter-spacing:.05em !important; text-transform:uppercase !important; }
.pill-green { color:var(--ka-lime) !important; background:rgba(124,255,43,.11) !important; border:1px solid rgba(124,255,43,.22); }
.pill-yellow { color:var(--ka-amber) !important; background:rgba(255,202,69,.10) !important; border:1px solid rgba(255,202,69,.22); }
.pill-red { color:var(--ka-red) !important; background:rgba(255,77,67,.10) !important; border:1px solid rgba(255,77,67,.25); }
.progress, .ai-conf-track { height:6px !important; min-width:76px !important; border-radius:99px !important; overflow:hidden !important; background:#283032 !important; border:0 !important; }
.progress span, .ai-conf-fill { display:block !important; height:100% !important; border-radius:99px !important; background:linear-gradient(90deg,#64cf26,var(--ka-lime)) !important; box-shadow:none !important; }

/* AI table/details */
.ai-table-final { border:1px solid var(--ka-line) !important; border-radius:var(--ka-radius) !important; background:#091113 !important; box-shadow:none !important; margin:0 0 8px !important; overflow:hidden !important; }
.ai-table-final-head { min-height:38px !important; background:#10181a !important; color:#aab6af !important; font-size:9px !important; }
.ai-table-final-row { min-height:50px !important; background:#091113 !important; font-size:11px !important; }
.ai-cell-main { font-size:12px !important; }
.ai-cell-sub { font-size:9px !important; color:#87948d !important; }
.ai-status-inline, .ai-status-text { height:27px !important; min-width:72px !important; border-radius:5px !important; background:rgba(124,255,43,.10) !important; border:1px solid rgba(124,255,43,.22) !important; color:var(--ka-lime) !important; font-size:9px !important; }
.ai-detail-final { padding:12px !important; }
.ai-detail-final-grid { grid-template-columns:repeat(3,minmax(0,1fr)) !important; gap:8px !important; }
.ai-detail-final-box { min-height:0 !important; padding:12px !important; border-radius:6px !important; background:#0b1416 !important; border:1px solid var(--ka-line-soft) !important; }
.ai-detail-final-title { font-size:12px !important; margin:0 0 8px !important; }
.ai-engine-line { font-size:10px !important; line-height:1.55 !important; }

/* Native Streamlit controls */
.stButton > button, button[kind="primary"], button[kind="secondary"], [data-testid="stFormSubmitButton"] button {
  min-height:38px !important;
  border-radius:6px !important;
  border:1px solid rgba(124,255,43,.38) !important;
  background:linear-gradient(180deg,#95ea2c,#67b617) !important;
  color:#071006 !important;
  font-size:11px !important;
  font-weight:950 !important;
  letter-spacing:.05em !important;
  text-transform:uppercase !important;
  box-shadow:0 8px 18px rgba(75,150,15,.18) !important;
}
.stButton > button:hover { filter:brightness(1.08); border-color:var(--ka-lime) !important; }
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"], [data-testid="stNumberInput"] > div > div {
  min-height:39px !important;
  border-radius:6px !important;
  background:#0b1315 !important;
  border-color:var(--ka-line) !important;
  color:#eaf0ec !important;
}
label, [data-testid="stWidgetLabel"] { color:#9eaaa3 !important; font-size:10px !important; font-weight:800 !important; letter-spacing:.045em !important; text-transform:uppercase !important; }
[data-testid="stExpander"] { border:1px solid var(--ka-line) !important; border-radius:6px !important; background:#0a1214 !important; }
[data-testid="stAlert"] { border-radius:6px !important; background:#0c1517 !important; border:1px solid var(--ka-line) !important; color:#dfe7e2 !important; }

/* Render-grade data visual components */
.ka-viz { border:1px solid var(--ka-line); border-radius:var(--ka-radius); background:linear-gradient(180deg,#0d1517,#081012); padding:13px 15px; box-shadow:var(--ka-shadow); min-height:100%; }
.ka-viz-title { color:#edf3ef; font-size:12px; font-weight:900; letter-spacing:.065em; text-transform:uppercase; margin-bottom:9px; }
.ka-viz-sub { color:#86928c; font-size:9px; margin-top:-5px; margin-bottom:8px; }
.ka-viz svg { display:block; width:100%; height:auto; overflow:visible; }
.ka-bars { display:grid; gap:9px; }
.ka-bar-row { display:grid; grid-template-columns:110px 1fr 62px; align-items:center; gap:10px; color:#cbd4cf; font-size:10px; }
.ka-bar-track { height:6px; border-radius:99px; background:#283032; overflow:hidden; }
.ka-bar-fill { height:100%; background:linear-gradient(90deg,#63bd25,var(--ka-lime)); }
.ka-bar-value { color:var(--ka-lime); font-weight:900; text-align:right; }
.ka-insight { display:flex; gap:11px; padding:10px; border:1px solid var(--ka-line-soft); border-radius:6px; background:#0a1214; margin-top:7px; }
.ka-insight-icon { color:var(--ka-lime); font-size:20px; }
.ka-insight b { display:block; color:#f4f8f5; font-size:11px; margin-bottom:3px; }
.ka-insight span { color:#93a099; font-size:9px; line-height:1.4; }

.footer-ka { display:flex !important; justify-content:space-between !important; margin-top:12px !important; padding:12px 4px 2px !important; border-top:1px solid var(--ka-line) !important; color:#78847e !important; font-size:9px !important; letter-spacing:.055em !important; }

/* Technical button skin — navigation only; page content remains unchanged. */
.stTabs [data-baseweb="tab-list"] {
  gap:6px !important;
  min-height:56px !important;
  padding:5px !important;
  border:1px solid #1b2b22 !important;
  border-radius:3px !important;
  background:linear-gradient(180deg,rgba(5,15,9,.96),rgba(2,9,6,.98)) !important;
  box-shadow:inset 0 1px 0 rgba(124,255,0,.025) !important;
}
.stTabs [data-baseweb="tab"] {
  position:relative !important;
  isolation:isolate !important;
  overflow:hidden !important;
  height:46px !important;
  min-height:46px !important;
  padding:0 14px !important;
  border:0 !important;
  border-right:0 !important;
  border-radius:0 !important;
  clip-path:polygon(8px 0,calc(100% - 8px) 0,100% 8px,100% calc(100% - 8px),calc(100% - 8px) 100%,8px 100%,0 calc(100% - 8px),0 8px) !important;
  background:#1a2a21 !important;
  color:#d7ded9 !important;
  box-shadow:none !important;
}
.stTabs [data-baseweb="tab"]::before {
  content:"";
  position:absolute;
  z-index:-1;
  inset:1px;
  clip-path:polygon(7px 0,calc(100% - 7px) 0,100% 7px,100% calc(100% - 7px),calc(100% - 7px) 100%,7px 100%,0 calc(100% - 7px),0 7px);
  background:linear-gradient(180deg,#07100b,#040a07);
}
.stTabs [data-baseweb="tab"]::after {
  content:"";
  position:absolute;
  z-index:3;
  right:8px;
  bottom:3px;
  width:13px;
  height:7px;
  color:#29442d;
  background:repeating-linear-gradient(135deg,transparent 0 2px,currentColor 2px 3px,transparent 3px 5px);
}
.stTabs [data-baseweb="tab"] p {
  position:relative !important;
  z-index:4 !important;
  margin:0 !important;
  color:inherit !important;
  font-size:inherit !important;
  font-weight:inherit !important;
  letter-spacing:inherit !important;
  white-space:nowrap !important;
}
.stTabs [data-baseweb="tab"]:hover {
  color:#f2f7f3 !important;
  background:#35513d !important;
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
  color:#f2f7f3 !important;
  background:#78ff00 !important;
  box-shadow:none !important;
}
.stTabs [data-baseweb="tab"][aria-selected="true"]::before {
  inset:2px;
  background:linear-gradient(180deg,#08140c,#061009);
}
.stTabs [data-baseweb="tab"][aria-selected="true"]::after { color:#78ff00 !important; }
.stTabs [data-baseweb="tab"][aria-selected="true"] p::before {
  content:"";
  position:absolute;
  left:-18px;
  top:50%;
  width:6px;
  height:6px;
  transform:translateY(-50%) rotate(45deg);
  background:#78ff00;
}

/* Keep the existing eight-column menu footprint. */
.stTabs [data-baseweb="tab-list"]:has(> [data-baseweb="tab"]:nth-child(8)) {
  grid-template-columns:repeat(8,minmax(0,1fr)) !important;
  height:56px !important;
  min-height:56px !important;
  padding:5px !important;
  gap:5px !important;
  overflow:hidden !important;
  background:linear-gradient(180deg,rgba(5,15,9,.96),rgba(2,9,6,.98)) !important;
  border:1px solid #1b2b22 !important;
  border-radius:3px !important;
  box-shadow:none !important;
}
.stTabs [data-baseweb="tab-list"]:has(> [data-baseweb="tab"]:nth-child(8)) > [data-baseweb="tab"] {
  min-width:0 !important;
  width:100% !important;
  height:46px !important;
  min-height:46px !important;
  padding:0 10px !important;
  border:0 !important;
  color:#cbd4ce !important;
  background:#1a2a21 !important;
  font-size:10px !important;
}
.stTabs [data-baseweb="tab-list"]:has(> [data-baseweb="tab"]:nth-child(8)) > [data-baseweb="tab"][aria-selected="true"] {
  color:#f2f7f3 !important;
  background:#78ff00 !important;
  box-shadow:none !important;
}
.stTabs [data-baseweb="tab-list"]:has(> [data-baseweb="tab"]:nth-child(8)) > [data-baseweb="tab"][aria-selected="true"]::before {
  inset:2px;
  background:linear-gradient(180deg,#08140c,#061009);
}

@media (max-width: 1200px) {
  .ka-grid { grid-template-columns:repeat(2,minmax(0,1fr)) !important; }
  .ka-page-banner, .ka-page-banner.ka-image-banner { height:170px !important; }
  .stTabs [data-baseweb="tab-list"] { grid-auto-columns:minmax(108px,1fr) !important; }
}
@media (max-width: 760px) {
  .block-container { padding:8px 10px 16px !important; }
  .ka-appbar { height:38px; }
  .ka-appbar-brand img { width:34px; height:34px; }
  .ka-brand-word strong { font-size:15px; }
  .ka-appbar-tools .ka-time, .ka-user span { display:none; }
  .ka-grid { grid-template-columns:1fr !important; }
  .ka-page-banner, .ka-page-banner.ka-image-banner { height:118px !important; }
  .ka-title, .ka-section-heading { font-size:17px !important; }
  .stTabs [data-baseweb="tab"] { min-width:104px !important; height:44px !important; }
  .ai-detail-final-grid { grid-template-columns:1fr !important; }
  .footer-ka { display:block !important; line-height:1.8; }
}
</style>
"""


def _image_data_uri(path: Path) -> str:
    try:
        suffix = path.suffix.lower().lstrip(".") or "png"
        mime = "jpeg" if suffix in {"jpg", "jpeg"} else suffix
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:image/{mime};base64,{encoded}"
    except Exception:
        return ""


def inject_trading_desk_theme() -> None:
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def render_appbar(base_dir: Path) -> None:
    logo = _image_data_uri(base_dir / "kanibal_logo.png")
    icon = f'<img src="{logo}" alt="">' if logo else ""
    brand = f'{icon}<span class="ka-brand-word"><strong>KANIBAL</strong><span>ANALYTICS</span></span>'
    st.markdown(
        f"""
        <div class="ka-appbar">
          <div class="ka-appbar-brand">{brand}</div>
          <div class="ka-appbar-tools">
            <span class="ka-live">NA ŻYWO</span>
            <span class="ka-time">DANE AKTUALIZOWANE AUTOMATYCZNIE</span>
            <span aria-label="Powiadomienia">◯</span>
            <span class="ka-user"><span class="ka-avatar">K</span><span>KANIBAL</span></span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

