"""Closed authentication layer and presentation for the Streamlit dashboard."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any, Dict

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
USERS_FILE = BASE_DIR / "users.json"

DEFAULT_USERS = {
    "admin": {
        "password": "admin123",
        "role": "admin",
        "active": True,
    }
}


def ensure_users_file() -> None:
    if not USERS_FILE.exists():
        USERS_FILE.write_text(json.dumps(DEFAULT_USERS, indent=2, ensure_ascii=False), encoding="utf-8")


def load_users() -> Dict[str, Any]:
    ensure_users_file()
    try:
        data = json.loads(USERS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def sha256_password(password: str) -> str:
    return "sha256$" + hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(saved: Any, password: str) -> bool:
    saved_str = str(saved or "")
    if saved_str.startswith("sha256$"):
        return saved_str == sha256_password(password)
    return saved_str == password


def authenticate(username: str, password: str) -> bool:
    users = load_users()
    user = users.get(username)
    if not user:
        return False
    if isinstance(user, str):
        return verify_password(user, password)
    if isinstance(user, dict):
        if user.get("active", True) is False:
            return False
        return verify_password(user.get("password"), password)
    return False


def _asset_data_uri(path: Path) -> str:
    try:
        if not path.exists():
            return ""
        mime = "image/png"
        if path.suffix.lower() in {".jpg", ".jpeg"}:
            mime = "image/jpeg"
        elif path.suffix.lower() == ".webp":
            mime = "image/webp"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"
    except Exception:
        return ""


def _login_css() -> None:
    logo_uri = _asset_data_uri(BASE_DIR / "kanibal_icon_512.png")
    st.markdown(
        f"""
        <style>
        :root {{
          --login-navy:#061d3b;
          --login-blue:#087af5;
          --login-blue-dark:#0569db;
          --login-muted:#64748b;
          --login-line:#cfdae9;
          --login-soft:#eef5ff;
          --login-green:#42c95a;
        }}
        html,body,.stApp {{
          min-height:100%; overflow:hidden!important; background:#fff!important;
          color:var(--login-navy)!important;
        }}
        [data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stSidebar"],
        [data-testid="stDecoration"],footer {{ display:none!important; }}
        .block-container {{ max-width:none!important; padding:0!important; min-height:100vh!important; }}

        .ka-login-brand {{
          position:fixed; z-index:2; left:3.7vw; top:4.1vh;
          display:flex; align-items:center; gap:18px;
        }}
        .ka-login-brand img {{
          width:94px; height:94px; object-fit:cover; border-radius:2px;
          box-shadow:0 6px 20px rgba(6,29,59,.08);
        }}
        .ka-login-wordmark strong {{
          display:block; color:var(--login-navy); font:850 34px/1 Inter,Arial,sans-serif;
          letter-spacing:.035em;
        }}
        .ka-login-wordmark span {{
          display:block; margin-top:16px; color:#0a70e6;
          font:800 15px/1 Inter,Arial,sans-serif; letter-spacing:.31em;
        }}
        .ka-login-wordmark small {{
          display:block; margin-top:17px; color:#73839a;
          font:750 9px/1 Inter,Arial,sans-serif; letter-spacing:.24em;
        }}
        .ka-login-system {{
          position:fixed; z-index:5; top:5.2vh; right:4vw;
          display:flex; align-items:center; gap:22px; color:#334155;
          font:800 12px/1 Inter,Arial,sans-serif; letter-spacing:.06em; text-transform:uppercase;
        }}
        .ka-login-system .online {{ display:flex; align-items:center; gap:12px; }}
        .ka-login-system .online::before {{
          content:""; width:11px; height:11px; border-radius:50%; background:var(--login-green);
          box-shadow:0 0 0 4px rgba(66,201,90,.08);
        }}
        .ka-login-system .lang {{ padding-left:24px; border-left:1px solid #d6dfeb; }}
        .ka-login-system .lang::after {{ content:"⌄"; margin-left:20px; font-size:18px; }}

        .ka-login-story {{
          position:fixed; z-index:1; left:3.7vw; top:19.3vh; width:47vw; height:61vh;
          color:var(--login-navy);
        }}
        .ka-login-story h2 {{
          margin:0; max-width:600px; color:var(--login-navy);
          font:850 clamp(44px,3.55vw,68px)/.99 Inter,Arial,sans-serif; letter-spacing:-.045em;
        }}
        .ka-login-story p {{
          margin:22px 0 0; max-width:560px; color:#536780;
          font:500 clamp(16px,1.3vw,23px)/1.55 Inter,Arial,sans-serif;
        }}
        .ka-login-chart {{ position:absolute; left:-1vw; right:0; bottom:0; height:46vh; }}
        .ka-login-chart svg {{ width:100%; height:100%; overflow:visible; }}
        .ka-metric {{
          position:absolute; z-index:2; min-width:112px; padding:13px 16px;
          border:1px solid #d3deec; border-radius:13px; background:rgba(255,255,255,.96);
          box-shadow:0 9px 24px rgba(32,77,130,.10); color:var(--login-navy);
        }}
        .ka-metric span {{ display:block; color:#718198; font:800 9px/1 Inter,Arial,sans-serif; text-transform:uppercase; }}
        .ka-metric strong {{ display:block; margin-top:7px; font:850 20px/1 Inter,Arial,sans-serif; }}
        .ka-metric.one {{ left:1.5vw; top:38%; }}
        .ka-metric.two {{ left:34%; top:8%; }}
        .ka-metric.three {{ right:3%; bottom:7%; }}

        div[data-testid="stForm"] {{
          position:fixed!important; z-index:4!important; top:50%!important; right:6.2vw!important;
          transform:translateY(-48%)!important; width:min(37vw,660px)!important;
          box-sizing:border-box!important; margin:0!important;
          padding:clamp(34px,4.2vh,50px) clamp(34px,3.2vw,54px) clamp(30px,3.7vh,44px)!important;
          border:1px solid var(--login-line)!important; border-radius:20px!important;
          background:#fff!important; box-shadow:0 24px 70px rgba(27,72,124,.10)!important;
        }}
        div[data-testid="stForm"] [data-testid="stVerticalBlock"] {{ gap:0!important; }}
        .ka-login-card-head {{ margin:0 0 clamp(22px,2.7vh,31px)!important; }}
        .ka-login-security {{
          display:flex; align-items:center; gap:12px; margin-bottom:clamp(20px,2.6vh,29px);
          color:var(--login-blue); font:850 13px/1 Inter,Arial,sans-serif;
          letter-spacing:.025em; text-transform:uppercase;
        }}
        .ka-login-security::before {{
          content:""; width:21px; height:21px; background:var(--login-blue);
          -webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M12 2l8 4v6c0 5-3.4 9.5-8 10-4.6-.5-8-5-8-10V6l8-4zm0 2.2L6 7.1V12c0 3.9 2.5 7.3 6 7.9 3.5-.6 6-4 6-7.9V7.1l-6-2.9zm-1.1 10.9l-2.8-2.8 1.4-1.4 1.4 1.4 3.7-3.7L16 10l-5.1 5.1z'/%3E%3C/svg%3E") center/contain no-repeat;
        }}
        .ka-login-card-head h1 {{
          margin:0 0 12px!important; color:var(--login-navy)!important;
          font:850 clamp(34px,2.5vw,46px)/1.08 Inter,Arial,sans-serif!important; letter-spacing:-.035em!important;
        }}
        .ka-login-card-head p {{
          margin:0!important; color:#63748b!important;
          font:500 clamp(14px,1.03vw,18px)/1.5 Inter,Arial,sans-serif!important;
        }}
        div[data-testid="stForm"] [data-testid="stTextInput"] {{ margin-bottom:clamp(13px,1.75vh,19px)!important; }}
        div[data-testid="stForm"] [data-testid="stTextInput"] label p {{
          color:var(--login-navy)!important; font-size:14px!important; font-weight:750!important;
          letter-spacing:0!important; text-transform:none!important;
        }}
        div[data-testid="stForm"] [data-baseweb="input"] {{
          position:relative!important; height:clamp(52px,6.1vh,62px)!important;
          border:1px solid #b9c8da!important; border-radius:10px!important;
          background:#fff!important; box-shadow:none!important; transition:.16s ease!important;
        }}
        div[data-testid="stForm"] [data-baseweb="input"] > div,
        div[data-testid="stForm"] [data-baseweb="input"] input {{ background:#fff!important; background-color:#fff!important; }}
        div[data-testid="stForm"] [data-baseweb="input"]:focus-within {{
          border-color:var(--login-blue)!important; box-shadow:0 0 0 3px rgba(8,122,245,.10)!important;
        }}
        div[data-testid="stForm"] [data-testid="InputInstructions"] {{ display:none!important; }}
        div[data-testid="stForm"] [data-baseweb="input"]::before {{
          content:""; position:absolute; z-index:3; left:17px; top:50%; width:23px; height:23px;
          transform:translateY(-50%); background:#6a7b92; opacity:.92;
          -webkit-mask-position:center; -webkit-mask-size:contain; -webkit-mask-repeat:no-repeat;
        }}
        div[data-testid="stForm"] [data-baseweb="input"]:has(input[aria-label="Adres e-mail lub login"])::before {{
          -webkit-mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M12 12a5 5 0 100-10 5 5 0 000 10zm0-2a3 3 0 110-6 3 3 0 010 6zm0 4c-5 0-9 2.5-9 6v2h18v-2c0-3.5-4-6-9-6zm-6.8 6c.5-2.2 3.4-4 6.8-4s6.3 1.8 6.8 4H5.2z'/%3E%3C/svg%3E");
        }}
        div[data-testid="stForm"] [data-baseweb="input"]:has(input[type="password"])::before {{
          -webkit-mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M17 8h-1V6a4 4 0 00-8 0v2H7a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2V10a2 2 0 00-2-2zm-7-2a2 2 0 014 0v2h-4V6zm7 14H7V10h10v10z'/%3E%3C/svg%3E");
        }}
        div[data-testid="stForm"] input {{
          padding-left:52px!important; color:var(--login-navy)!important; -webkit-text-fill-color:var(--login-navy)!important;
          font:550 clamp(14px,1vw,17px) Inter,Arial,sans-serif!important; caret-color:var(--login-blue)!important;
        }}
        div[data-testid="stForm"] input::placeholder {{ color:#8998ab!important; -webkit-text-fill-color:#8998ab!important; opacity:1!important; }}
        div[data-testid="stForm"] input:-webkit-autofill {{
          -webkit-box-shadow:0 0 0 1000px #fff inset!important; -webkit-text-fill-color:var(--login-navy)!important;
        }}
        div[data-testid="stForm"] [data-testid="stHorizontalBlock"] {{ margin:0 0 clamp(19px,2.6vh,28px)!important; align-items:center!important; }}
        div[data-testid="stForm"] [data-testid="stCheckbox"] label {{ gap:9px!important; }}
        div[data-testid="stForm"] [data-testid="stCheckbox"] p {{ color:var(--login-navy)!important; font-size:14px!important; font-weight:600!important; }}
        div[data-testid="stForm"] [data-testid="stCheckbox"] span {{ border-color:#aebfd2!important; border-radius:4px!important; background:#fff!important; }}
        div[data-testid="stForm"] [data-testid="stCheckbox"] label:has(input:checked) span {{ background:var(--login-blue)!important; border-color:var(--login-blue)!important; color:#fff!important; }}
        .ka-login-forgot {{ color:var(--login-blue); font:700 14px/1.45 Inter,Arial,sans-serif; text-align:right; padding-top:7px; }}
        div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button {{
          height:clamp(54px,6.4vh,64px)!important; min-height:clamp(54px,6.4vh,64px)!important;
          border:1px solid #0875e9!important; border-radius:11px!important;
          background:linear-gradient(180deg,#1187ff 0%,#0874ed 100%)!important; color:#fff!important;
          font:850 clamp(15px,1.12vw,19px)/1 Inter,Arial,sans-serif!important;
          letter-spacing:.035em!important; text-transform:uppercase!important;
          box-shadow:0 11px 25px rgba(8,116,237,.20)!important; transition:.16s ease!important;
        }}
        div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button:hover {{
          background:linear-gradient(180deg,#087df4,#0669db)!important; transform:translateY(-1px);
          box-shadow:0 14px 28px rgba(8,116,237,.26)!important;
        }}
        div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button p {{ color:#fff!important; font-weight:850!important; }}
        .ka-login-note {{
          margin-top:clamp(21px,3vh,32px); padding-top:clamp(18px,2.4vh,25px);
          border-top:1px solid #dbe4ef; color:#687a90;
          font:550 13px/1.4 Inter,Arial,sans-serif; text-align:center;
        }}
        .ka-login-note::before {{ content:"✓"; display:inline-grid; place-items:center; width:18px; height:18px; margin-right:9px; border:2px solid var(--login-green); border-radius:50%; color:var(--login-green); font-size:10px; font-weight:900; }}
        .ka-login-note b {{ color:#91a0b2; padding:0 8px; }}
        .ka-login-footer {{
          position:fixed; z-index:5; left:2.5vw; right:2.5vw; bottom:0; height:8vh; min-height:62px;
          display:flex; align-items:center; justify-content:space-between; box-sizing:border-box;
          border-top:1px solid #d6e0ec; color:#62738a; font:600 13px/1.4 Inter,Arial,sans-serif;
        }}
        .ka-login-footer b {{ color:#8fa0b5; padding:0 14px; }}
        div[data-testid="stAlert"] {{
          position:fixed!important; z-index:8!important; right:6.2vw!important; bottom:8.4vh!important;
          width:min(37vw,660px)!important; box-sizing:border-box!important;
        }}

        @media (max-height:850px) and (min-width:901px) {{
          .ka-login-brand {{ top:2.6vh; transform:scale(.82); transform-origin:left top; }}
          .ka-login-system {{ top:3.7vh; }}
          .ka-login-story {{ top:17vh; transform:scale(.88); transform-origin:left top; }}
          div[data-testid="stForm"] {{ transform:translateY(-49%) scale(.88)!important; transform-origin:right center!important; }}
        }}
        @media (max-width:1100px) {{
          .ka-login-story {{ width:43vw; }}
          .ka-login-wordmark strong {{ font-size:27px; }}
          .ka-login-wordmark span {{ font-size:12px; }}
          div[data-testid="stForm"] {{ right:3.2vw!important; width:48vw!important; }}
        }}
        @media (max-width:760px) {{
          html,body,.stApp {{ overflow:auto!important; }}
          .ka-login-story {{ display:none!important; }}
          .ka-login-brand {{ left:22px; top:20px; transform:scale(.72); transform-origin:left top; }}
          .ka-login-system {{ top:29px; right:20px; font-size:9px; gap:10px; }}
          .ka-login-system .lang {{ padding-left:10px; }}
          .ka-login-system .lang::after {{ margin-left:8px; }}
          div[data-testid="stForm"] {{
            position:absolute!important; left:16px!important; right:16px!important; top:138px!important;
            width:auto!important; transform:none!important; padding:28px 22px!important; border-radius:16px!important;
          }}
          .ka-login-card-head h1 {{ font-size:32px!important; }}
          .ka-login-footer {{ left:18px; right:18px; height:58px; font-size:9px; }}
          div[data-testid="stAlert"] {{ left:16px!important; right:16px!important; bottom:62px!important; width:auto!important; }}
        }}
        </style>

        <div class="ka-login-brand">
          <img src="{logo_uri}" alt="KANIBAL Analytics">
          <div class="ka-login-wordmark">
            <strong>KANIBAL</strong><span>ANALYTICS</span><small>ANALIZA · PRZEWAGA · ZYSK</small>
          </div>
        </div>
        <div class="ka-login-system"><span class="online">System online</span><span class="lang">PL</span></div>
        <section class="ka-login-story" aria-label="Analityka KANIBAL">
          <h2>Dane, które<br>dają przewagę.</h2>
          <p>Precyzyjne analizy. Sprawdzone strategie.<br>Lepsze decyzje.</p>
          <div class="ka-login-chart" aria-hidden="true">
            <svg viewBox="0 0 850 480" role="img">
              <defs><linearGradient id="barFade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#d7e8ff"/><stop offset="1" stop-color="#eef5ff"/></linearGradient></defs>
              <g stroke="#e5eef9" stroke-width="1"><path d="M120 40V430M210 40V430M300 40V430M390 40V430M480 40V430M570 40V430M660 40V430M750 40V430"/><path d="M70 90H810M70 170H810M70 250H810M70 330H810M70 410H810"/></g>
              <g fill="url(#barFade)"><rect x="160" y="360" width="24" height="62"/><rect x="225" y="332" width="24" height="90"/><rect x="290" y="302" width="24" height="120"/><rect x="355" y="318" width="24" height="104"/><rect x="420" y="266" width="24" height="156"/><rect x="485" y="235" width="24" height="187"/><rect x="550" y="249" width="24" height="173"/><rect x="615" y="190" width="24" height="232"/><rect x="680" y="140" width="24" height="282"/><rect x="745" y="88" width="24" height="334"/></g>
              <path d="M45 425C115 368 155 389 220 342S335 312 395 272 505 305 560 230 640 242 690 170 738 138 790 66" fill="none" stroke="#087af5" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M45 425C115 368 155 389 220 342S335 312 395 272 505 305 560 230 640 242 690 170 738 138 790 66" fill="none" stroke="#fff" stroke-width="2" stroke-dasharray="1 20"/>
              <g fill="#fff" stroke="#087af5" stroke-width="4"><circle cx="220" cy="342" r="7"/><circle cx="395" cy="272" r="7"/><circle cx="560" cy="230" r="7"/><circle cx="690" cy="170" r="7"/></g>
              <path d="M790 66l-26 8 20 13z" fill="#087af5"/>
              <path d="M36 435H810" stroke="#cbdcf1" stroke-width="2"/>
            </svg>
            <div class="ka-metric one"><span>Kurs śr.</span><strong>2.07</strong></div>
            <div class="ka-metric two"><span>Value</span><strong>48.0</strong></div>
            <div class="ka-metric three"><span>Pewność</span><strong>72%</strong></div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def require_login() -> None:
    if "auth_ok" not in st.session_state:
        st.session_state.auth_ok = False
    if "auth_user" not in st.session_state:
        st.session_state.auth_user = ""

    if st.session_state.auth_ok:
        return

    _login_css()
    with st.form("kanibal_login_form", clear_on_submit=False):
        st.markdown(
            """
            <div class="ka-login-card-head">
              <div class="ka-login-security">Bezpieczne logowanie</div>
              <h1>Witaj ponownie</h1>
              <p>Zaloguj się, aby przejść do panelu analitycznego.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        username = st.text_input("Adres e-mail lub login", placeholder="Wprowadź login")
        password = st.text_input("Hasło", type="password", placeholder="Wprowadź hasło")
        remember_col, forgot_col = st.columns([1, 1])
        with remember_col:
            st.checkbox("Zapamiętaj mnie", value=True)
        with forgot_col:
            st.markdown('<div class="ka-login-forgot">Nie pamiętasz hasła?</div>', unsafe_allow_html=True)
        submitted = st.form_submit_button("ZALOGUJ SIĘ", use_container_width=True)
        st.markdown(
            '<div class="ka-login-note">Bezpieczne połączenie <b>•</b> Szyfrowanie 256-bit</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="ka-login-footer"><span>© 2026 KANIBAL ANALYTICS</span>'
        '<span>Polityka prywatności <b>•</b> Pomoc</span></div>',
        unsafe_allow_html=True,
    )

    if submitted:
        if authenticate(username.strip(), password):
            st.session_state.auth_ok = True
            st.session_state.auth_user = username.strip()
            st.rerun()
        else:
            st.error("Nieprawidłowy login lub hasło.")

    st.stop()
