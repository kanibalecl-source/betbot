"""
Simple closed login layer for Streamlit dashboard.
- No public registration.
- Users are managed manually in users.json.
- Supports plain text passwords for easy setup and sha256 hashes for safer use.
"""
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
    visual_uri = _asset_data_uri(BASE_DIR / "kanibal_login_visual_reference.png")
    st.markdown(
        f"""
        <style>
        :root {{ --login-lime:#72ff27; --login-bg:#050808; --login-panel:#0a0f10; --login-line:#263033; }}
        html,body,.stApp {{ min-height:100%; overflow:hidden!important; background:var(--login-bg)!important; }}
        [data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stSidebar"],
        [data-testid="stDecoration"],footer {{ display:none!important; }}
        .block-container {{ max-width:none!important; padding:0!important; min-height:100vh!important; }}
        .ka-login-visual {{
            position:fixed; inset:0 42.5vw 0 0; z-index:0;
            background-image:linear-gradient(90deg,rgba(2,5,5,.05) 0%,rgba(2,5,5,.08) 72%,#050808 100%),url('{visual_uri}');
            background-repeat:no-repeat; background-position:left center; background-size:auto 100%;
        }}
        .ka-login-visual::after {{ content:""; position:absolute; inset:0; background:linear-gradient(180deg,rgba(0,0,0,.06),transparent 38%,rgba(0,0,0,.32)); pointer-events:none; }}
        .ka-login-system {{
            position:fixed; z-index:3; top:28px; right:4.2vw; display:flex; align-items:center; gap:18px;
            color:#758083; font:700 10px/1 Inter,Arial,sans-serif; letter-spacing:.13em; text-transform:uppercase;
        }}
        .ka-login-system .online {{ color:#a9b4b5; display:flex; align-items:center; gap:8px; }}
        .ka-login-system .online::before {{ content:""; width:7px; height:7px; border-radius:50%; background:var(--login-lime); box-shadow:0 0 10px rgba(114,255,39,.75); }}
        .ka-login-system .lang {{ color:#d4d9d9; padding-left:18px; border-left:1px solid #252c2e; }}
        div[data-testid="stForm"] {{
            position:fixed!important; z-index:4!important; top:50%!important; right:4.2vw!important;
            transform:translateY(-50%)!important; width:min(36.2vw,520px)!important;
            margin:0!important; padding:34px 36px 31px!important;
            border:1px solid var(--login-line)!important; border-radius:14px!important;
            background:linear-gradient(145deg,rgba(15,21,22,.98),rgba(7,11,12,.99))!important;
            box-shadow:0 30px 90px rgba(0,0,0,.52),inset 0 1px 0 rgba(255,255,255,.025)!important;
        }}
        .ka-login-card-head {{ margin:0 0 28px; }}
        .ka-login-security {{ color:var(--login-lime); font:800 9px/1 Inter,Arial,sans-serif; letter-spacing:.19em; text-transform:uppercase; margin-bottom:14px; }}
        .ka-login-security::before {{ content:"◆"; font-size:8px; margin-right:8px; }}
        .ka-login-card-head h1 {{ margin:0 0 9px; color:#f4f7f6; font:750 28px/1.15 Inter,Arial,sans-serif; letter-spacing:-.025em; }}
        .ka-login-card-head p {{ margin:0; color:#737f82; font:500 12px/1.55 Inter,Arial,sans-serif; }}
        div[data-testid="stForm"] [data-testid="stTextInput"] {{ margin-bottom:17px!important; }}
        div[data-testid="stForm"] [data-testid="stTextInput"] label p {{ color:#aeb7b8!important; font-size:10px!important; font-weight:800!important; letter-spacing:.105em!important; text-transform:uppercase!important; }}
        div[data-testid="stForm"] [data-baseweb="input"] {{ height:54px!important; border:1px solid #293235!important; border-radius:8px!important; background:#080d0e!important; box-shadow:none!important; transition:border-color .16s,box-shadow .16s!important; }}
        div[data-testid="stForm"] [data-baseweb="input"] > div {{ background:transparent!important; }}
        div[data-testid="stForm"] [data-baseweb="input"]:focus-within {{ border-color:#5d9f3d!important; box-shadow:0 0 0 2px rgba(114,255,39,.09)!important; }}
        div[data-testid="stForm"] input {{ background:transparent!important; color:#e8eeee!important; -webkit-text-fill-color:#e8eeee!important; font:600 13px Inter,Arial,sans-serif!important; caret-color:var(--login-lime)!important; }}
        div[data-testid="stForm"] input::placeholder {{ color:#505a5d!important; -webkit-text-fill-color:#505a5d!important; opacity:1!important; }}
        div[data-testid="stForm"] [data-testid="stHorizontalBlock"] {{ margin:-2px 0 17px!important; align-items:center!important; }}
        div[data-testid="stForm"] [data-testid="stCheckbox"] label {{ gap:8px!important; }}
        div[data-testid="stForm"] [data-testid="stCheckbox"] p {{ color:#7f898b!important; font-size:10px!important; font-weight:650!important; }}
        div[data-testid="stForm"] [data-testid="stCheckbox"] span {{ border-color:#3a4547!important; background:#090e0f!important; border-radius:3px!important; }}
        .ka-login-forgot {{ color:#8f999b; font:700 10px/1.4 Inter,Arial,sans-serif; text-align:right; padding-top:7px; }}
        div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button {{
            height:56px!important; min-height:56px!important; border:1px solid #8aff4d!important; border-radius:8px!important;
            background:linear-gradient(180deg,#7dff36,#67e829)!important; color:#071006!important;
            font:900 11px/1 Inter,Arial,sans-serif!important; letter-spacing:.105em!important; text-transform:uppercase!important;
            box-shadow:0 10px 30px rgba(87,229,31,.13),inset 0 1px 0 rgba(255,255,255,.3)!important;
        }}
        div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button:hover {{ background:linear-gradient(180deg,#8bff4e,#70ef31)!important; transform:translateY(-1px); }}
        .ka-login-note {{ margin-top:18px; color:#596366; font:600 9px/1.45 Inter,Arial,sans-serif; letter-spacing:.035em; text-align:center; }}
        .ka-login-note::before {{ content:"▣"; color:#798486; margin-right:7px; }}
        .ka-login-footer {{ position:fixed; z-index:3; right:4.2vw; bottom:25px; width:min(36.2vw,520px); color:#4d5759; font:650 8px/1.4 Inter,Arial,sans-serif; letter-spacing:.09em; text-align:center; text-transform:uppercase; }}
        div[data-testid="stAlert"] {{ position:fixed!important; z-index:8!important; right:4.2vw!important; top:calc(50% + 295px)!important; width:min(36.2vw,520px)!important; }}

        /* Approved full-screen login — reference no. 2. */
        .ka-login-visual {{
            inset:0 42.6vw 0 0!important;
            background-image:url('{visual_uri}')!important;
            background-position:left top!important;
            background-size:auto 100%!important;
        }}
        .ka-login-visual::after {{
            display:block!important; content:""!important; position:absolute!important;
            top:0!important; right:0!important; bottom:0!important; left:102.35vh!important;
            background:#050808!important; pointer-events:none!important;
        }}
        .ka-login-system {{ top:30px!important; right:3.75vw!important; gap:26px!important; font-size:12px!important; letter-spacing:.02em!important; }}
        .ka-login-system .online {{ color:#aeb4b4!important; gap:12px!important; }}
        .ka-login-system .online::before {{ width:11px!important; height:11px!important; background:#a8db00!important; box-shadow:0 0 11px rgba(168,219,0,.55)!important; }}
        .ka-login-system .lang {{ padding-left:27px!important; color:#d8dddd!important; }}
        .ka-login-system .lang::after {{ content:"⌄"; margin-left:27px; color:#aeb5b5; font-size:18px; }}
        div[data-testid="stForm"] {{
            top:9.25vh!important; right:3.75vw!important; transform:none!important;
            width:38.8vw!important; height:78vh!important; min-height:0!important;
            box-sizing:border-box!important; overflow:hidden!important;
            padding:clamp(28px,5.2vh,50px) clamp(32px,2.75vw,44px) clamp(25px,4vh,38px)!important;
            border:1px solid #3a4345!important; border-radius:9px!important;
            background:linear-gradient(145deg,rgba(12,18,20,.985),rgba(7,12,14,.99))!important;
            box-shadow:0 28px 72px rgba(0,0,0,.42),inset 0 1px 0 rgba(255,255,255,.025)!important;
        }}
        .ka-login-card-head {{ margin:0 0 clamp(14px,2.4vh,24px)!important; text-align:center!important; }}
        div[data-testid="stForm"] [data-testid="stVerticalBlock"] {{ gap:0!important; }}
        .ka-login-security {{ margin:0 0 clamp(12px,1.8vh,18px)!important; color:#a9dd00!important; font-size:12px!important; letter-spacing:.13em!important; }}
        .ka-login-security::before {{
            content:""!important; display:inline-block; width:16px; height:16px; margin:0 11px -3px 0;
            background:#a9dd00; -webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M7 10V7a5 5 0 0110 0v3h1a2 2 0 012 2v8a2 2 0 01-2 2H6a2 2 0 01-2-2v-8a2 2 0 012-2h1zm2 0h6V7a3 3 0 00-6 0v3z'/%3E%3C/svg%3E") center/contain no-repeat;
        }}
        .ka-login-card-head h1 {{ margin:0 0 8px!important; color:#f3f5f4!important; font-size:clamp(32px,2.75vw,44px)!important; font-weight:760!important; line-height:1.08!important; letter-spacing:-.025em!important; }}
        .ka-login-card-head p {{ margin:0!important; color:#9aa1a2!important; font-size:clamp(13px,1.15vw,18px)!important; font-weight:450!important; line-height:1.5!important; }}
        div[data-testid="stForm"] [data-testid="stTextInput"] {{ margin-bottom:clamp(10px,1.7vh,16px)!important; }}
        div[data-testid="stForm"] [data-testid="stTextInput"] label p {{ color:#e4e7e6!important; font-size:clamp(13px,1.05vw,16px)!important; font-weight:600!important; letter-spacing:0!important; text-transform:none!important; }}
        div[data-testid="stForm"] [data-baseweb="input"] {{ position:relative!important; height:clamp(55px,7.2vh,66px)!important; border:1px solid #485153!important; border-radius:8px!important; background:#0b1113!important; }}
        div[data-testid="stForm"] div[data-testid="stTextInput"] [data-baseweb="input"] > div,
        div[data-testid="stForm"] div[data-testid="stTextInput"] [data-baseweb="input"] input {{ background:#0b1113!important; background-color:#0b1113!important; }}
        div[data-testid="stForm"] div[data-testid="stTextInput"] [data-baseweb="input"]:focus-within {{ border-color:#aee000!important; box-shadow:0 0 0 2px rgba(174,224,0,.10)!important; }}
        div[data-testid="stForm"] input:-webkit-autofill,
        div[data-testid="stForm"] input:-webkit-autofill:hover,
        div[data-testid="stForm"] input:-webkit-autofill:focus {{
            -webkit-box-shadow:0 0 0 1000px #0b1113 inset!important;
            -webkit-text-fill-color:#eef1f0!important;
            caret-color:#aee000!important;
        }}
        div[data-testid="stForm"] [data-testid="InputInstructions"] {{ display:none!important; }}
        div[data-testid="stForm"] [data-baseweb="input"]::before {{ content:""; position:absolute; z-index:2; left:21px; top:50%; width:24px; height:24px; transform:translateY(-50%); background-position:center; background-size:contain; background-repeat:no-repeat; opacity:.9; }}
        div[data-testid="stForm"] [data-baseweb="input"]:has(input[aria-label="Adres e-mail lub login"])::before {{ background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23b4b9ba' stroke-width='1.8'%3E%3Ccircle cx='12' cy='8' r='4'/%3E%3Cpath d='M4.5 21c0-4.2 3.4-7 7.5-7s7.5 2.8 7.5 7z'/%3E%3C/svg%3E"); }}
        div[data-testid="stForm"] [data-baseweb="input"]:has(input[type="password"])::before {{ background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23b4b9ba' stroke-width='1.8'%3E%3Crect x='5' y='10' width='14' height='11' rx='2'/%3E%3Cpath d='M8 10V7a4 4 0 018 0v3'/%3E%3C/svg%3E"); }}
        div[data-testid="stForm"] input {{ padding-left:66px!important; color:#eef1f0!important; -webkit-text-fill-color:#eef1f0!important; font-size:clamp(14px,1.12vw,18px)!important; font-weight:500!important; }}
        div[data-testid="stForm"] input::placeholder {{ color:#7d8486!important; -webkit-text-fill-color:#7d8486!important; }}
        div[data-testid="stForm"] [data-testid="stHorizontalBlock"] {{ margin:-1px 0 clamp(17px,2.6vh,24px)!important; }}
        div[data-testid="stForm"] [data-testid="stCheckbox"] p {{ color:#e5e8e7!important; font-size:clamp(13px,1.05vw,16px)!important; font-weight:550!important; letter-spacing:0!important; text-transform:none!important; }}
        div[data-testid="stForm"] [data-testid="stCheckbox"] label:has(input:checked) span {{ background:#aee000!important; border-color:#aee000!important; color:#071000!important; }}
        div[data-testid="stForm"] [data-testid="stCheckbox"] label:has(input:checked) span::after {{ content:"✓"; color:#071000; font-size:13px; font-weight:950; line-height:1; }}
        .ka-login-forgot {{ color:#aee000!important; font-size:clamp(13px,1.05vw,16px)!important; font-weight:600!important; padding-top:7px!important; }}
        div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button {{
            height:clamp(58px,8vh,72px)!important; min-height:clamp(58px,8vh,72px)!important;
            border-color:#b9eb08!important; border-radius:7px!important;
            background:linear-gradient(180deg,#bceb08 0%,#8fd500 100%)!important;
            color:#071006!important; font-size:clamp(17px,1.55vw,24px)!important; font-weight:850!important; letter-spacing:.065em!important;
        }}
        div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button p {{ font-size:clamp(17px,1.55vw,24px)!important; font-weight:850!important; letter-spacing:.065em!important; }}
        .ka-login-note {{ margin-top:clamp(18px,3.8vh,34px)!important; padding-top:clamp(16px,2.9vh,27px)!important; border-top:1px solid #424a4c!important; color:#909899!important; font-size:clamp(11px,.9vw,14px)!important; }}
        .ka-login-note::before {{ content:"◉"!important; color:#a6adae!important; font-size:17px!important; margin-right:12px!important; }}
        .ka-login-note b {{ color:#aee000; padding:0 9px; }}
        .ka-login-footer {{
            left:0!important; right:0!important; bottom:0!important; width:100vw!important; height:74px!important;
            box-sizing:border-box!important; padding:0 4.8vw!important; border-top:1px solid #22292b!important;
            display:flex!important; align-items:center!important; justify-content:space-between!important;
            color:#697173!important; font-size:13px!important; letter-spacing:.025em!important; text-align:left!important; text-transform:none!important;
        }}
        .ka-login-footer b {{ color:#a8d900; padding:0 12px; }}
        .ka-login-footer > span:first-child {{ visibility:hidden!important; }}
        div[data-testid="stAlert"] {{ right:3.75vw!important; top:auto!important; bottom:80px!important; width:38.8vw!important; }}
        @media (max-width:900px) {{
            .ka-login-visual {{ display:none; }}
            .ka-login-system {{ right:24px; }}
            div[data-testid="stForm"] {{ left:16px!important; right:16px!important; top:72px!important; width:auto!important; height:calc(100vh - 158px)!important; min-height:0!important; padding:28px 24px 25px!important; }}
            .ka-login-footer {{ padding:0 18px!important; font-size:10px!important; }}
            .ka-login-footer > span:first-child {{ visibility:visible!important; }}
        }}
        </style>
        <div class="ka-login-visual" aria-hidden="true"></div>
        <div class="ka-login-system"><span class="online">System online</span><span class="lang">PL</span></div>
        """,
        unsafe_allow_html=True,
    )


def require_login() -> None:
    if "auth_ok" not in st.session_state:
        st.session_state.auth_ok = False
    if "auth_user" not in st.session_state:
        st.session_state.auth_user = ""

    if st.session_state.auth_ok:
        # The authenticated account control is rendered by the dashboard's
        # navigation rail.  Keeping it out of the authentication layer avoids
        # duplicate controls and preserves a clean, predictable sidebar order.
        return

    _login_css()
    with st.form("kanibal_login_form", clear_on_submit=False):
        st.markdown(
            """
            <div class="ka-login-card-head">
              <div class="ka-login-security">Bezpieczny dostęp</div>
              <h1>Witaj ponownie</h1>
              <p>Zaloguj się, aby przejść do panelu analitycznego</p>
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
        submitted = st.form_submit_button("Zaloguj się", use_container_width=True)
        st.markdown('<div class="ka-login-note">Bezpieczne połączenie <b>•</b> Szyfrowanie 256-bit</div>', unsafe_allow_html=True)

    st.markdown('<div class="ka-login-footer"><span>© 2026 KANIBAL ANALYTICS</span><span>Polityka prywatności <b>•</b> Pomoc</span></div>', unsafe_allow_html=True)

    if submitted:
        if authenticate(username.strip(), password):
            st.session_state.auth_ok = True
            st.session_state.auth_user = username.strip()
            st.rerun()
        else:
            st.error("Nieprawidłowy login lub hasło.")

    st.stop()
