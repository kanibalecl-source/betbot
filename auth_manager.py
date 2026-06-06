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
    background_uri = _asset_data_uri(BASE_DIR / "kanibal_login_page.png")
    st.markdown(
        f"""
        <style>
        section[data-testid="stSidebar"] {{display:none!important;}}
        header[data-testid="stHeader"] {{background:transparent!important;}}
        .block-container {{
            max-width:1920px!important;
            min-height:100vh!important;
            padding:7.5vh 5vw 2vh!important;
        }}
        .stApp {{
            background:#050708 url("{background_uri}") center/cover no-repeat fixed!important;
        }}
        div[data-testid="stHorizontalBlock"] {{
            gap:3vw!important;
            align-items:center!important;
        }}
        .login-spacer {{min-height:76vh;}}
        div[data-testid="stForm"] {{
            padding:clamp(28px,3.4vw,54px)!important;
            border:1px solid rgba(205,255,170,.30)!important;
            border-radius:18px!important;
            background:linear-gradient(180deg,rgba(11,14,15,.985),rgba(5,8,9,.99))!important;
            box-shadow:0 28px 90px rgba(0,0,0,.70),0 0 45px rgba(143,231,0,.08)!important;
            backdrop-filter:blur(18px);
        }}
        .login-user-icon {{
            width:58px;height:58px;margin:0 auto 20px;border:1px solid #75b900;
            border-radius:50%;display:grid;place-items:center;color:#a8ef00;font-size:28px;
        }}
        .login-title {{font-size:34px;font-weight:500;color:#fff;text-align:center;line-height:1.1;}}
        .login-subtitle {{margin:12px 0 34px;color:#9a9d9f;text-align:center;font-size:14px;}}
        .login-note {{
            margin-top:24px;color:#858a87;font-size:12px;line-height:1.5;
            border-top:1px solid rgba(255,255,255,.08);padding-top:22px;text-align:center;
        }}
        div[data-testid="stTextInput"] label {{
            color:#e6e8e4!important;font-size:14px!important;font-weight:400!important;
        }}
        div[data-testid="stTextInput"] input {{
            height:56px!important;border-radius:8px!important;
            border:1px solid rgba(255,255,255,.25)!important;
            background:rgba(0,0,0,.34)!important;color:#fff!important;font-size:14px!important;
        }}
        div[data-testid="stTextInput"] input:focus {{
            border-color:rgba(168,239,0,.75)!important;
            box-shadow:0 0 0 3px rgba(168,239,0,.09)!important;
        }}
        div[data-testid="stFormSubmitButton"] button {{
            height:62px!important;margin-top:14px!important;border:0!important;border-radius:7px!important;
            background:linear-gradient(180deg,#b6fa13,#79c900)!important;color:#111700!important;
            font-weight:800!important;font-size:16px!important;letter-spacing:.17em!important;
            text-transform:uppercase!important;box-shadow:0 0 24px rgba(148,229,0,.30)!important;
        }}
        @media(max-width:1100px){{
            .block-container {{padding:4vh 4vw!important;}}
            .stApp {{background-position:35% center!important;}}
            .login-spacer {{min-height:35vh;}}
        }}
        @media(max-width:700px){{
            .stApp {{background-position:32% center!important;}}
            .login-spacer {{min-height:18vh;}}
            div[data-testid="stForm"] {{padding:28px 22px!important;}}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def require_login() -> None:
    if "auth_ok" not in st.session_state:
        st.session_state.auth_ok = False
    if "auth_user" not in st.session_state:
        st.session_state.auth_user = ""

    if st.session_state.auth_ok:
        with st.sidebar:
            st.markdown("---")
            st.caption(f"Zalogowany: **{st.session_state.auth_user}**")
            if st.button("Wyloguj", use_container_width=True):
                st.session_state.auth_ok = False
                st.session_state.auth_user = ""
                st.rerun()
        return

    _login_css()
    left_col, right_col = st.columns([1.58, 0.82], vertical_alignment="center")
    with left_col:
        st.markdown('<div class="login-spacer"></div>', unsafe_allow_html=True)
    with right_col:
        with st.form("kanibal_login_form", clear_on_submit=False):
            st.markdown(
                """
                <div class="login-user-icon">&#9675;</div>
                <div class="login-title">Witaj ponownie</div>
                <div class="login-subtitle">Zaloguj się, aby przejść do panelu analitycznego</div>
                """,
                unsafe_allow_html=True,
            )
            username = st.text_input("Adres e-mail lub login", placeholder="Wprowadź login")
            password = st.text_input("Hasło", type="password", placeholder="Wprowadź hasło")
            submitted = st.form_submit_button("Zaloguj się", use_container_width=True)
            st.markdown(
                '<div class="login-note">Twoje dane są bezpieczne<br>Dostęp tylko dla autoryzowanych użytkowników</div>',
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
