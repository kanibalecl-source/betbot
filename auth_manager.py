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
            max-width:none!important;
            min-height:100vh!important;
            padding:0!important;
        }}
        .stApp {{
            background:#050708 url("{background_uri}") center/cover no-repeat fixed!important;
        }}
        div[data-testid="stForm"] {{
            position:fixed!important;
            inset:0!important;
            padding:0!important;
            border:0!important;
            background:transparent!important;
            box-shadow:none!important;
            pointer-events:none!important;
        }}
        .login-user-icon,.login-title,.login-subtitle,.login-note {{
            display:none!important;
        }}
        div[data-testid="stForm"] div[data-testid="stTextInput"] {{
            position:fixed!important;
            left:64.65vw!important;
            width:27.4vw!important;
            height:5.75vh!important;
            margin:0!important;
            pointer-events:auto!important;
        }}
        div[data-testid="stForm"] div[data-testid="stTextInput"]:has(input[aria-label="Adres e-mail lub login"]) {{
            top:36.55vh!important;
        }}
        div[data-testid="stForm"] div[data-testid="stTextInput"]:has(input[type="password"]) {{
            top:47.8vh!important;
        }}
        div[data-testid="stTextInput"] label {{
            display:none!important;
        }}
        div[data-testid="stTextInput"] div[data-baseweb="input"] {{
            height:100%!important;
            border:0!important;
            background:transparent!important;
            box-shadow:none!important;
        }}
        div[data-testid="stTextInput"] input {{
            height:100%!important;
            padding-left:3.3vw!important;
            border:0!important;
            border-radius:7px!important;
            background:transparent!important;
            color:#fff!important;
            caret-color:#a8ef00!important;
            font-size:clamp(10px,.82vw,14px)!important;
        }}
        div[data-testid="stTextInput"] input::placeholder {{
            color:transparent!important;
        }}
        div[data-testid="stTextInput"] input:not(:placeholder-shown) {{
            background:rgba(8,11,12,.96)!important;
        }}
        div[data-testid="stTextInput"] input:focus {{
            border:1px solid rgba(168,239,0,.75)!important;
            box-shadow:0 0 0 3px rgba(168,239,0,.09)!important;
        }}
        div[data-testid="stTextInput"] button {{
            opacity:0!important;
        }}
        div[data-testid="stFormSubmitButton"] {{
            position:fixed!important;
            top:62.15vh!important;
            left:64.65vw!important;
            width:27.4vw!important;
            height:7.25vh!important;
            pointer-events:auto!important;
        }}
        div[data-testid="stFormSubmitButton"] button {{
            width:100%!important;
            height:100%!important;
            margin:0!important;
            border:0!important;
            background:transparent!important;
            box-shadow:none!important;
            color:transparent!important;
            opacity:0!important;
        }}
        div[data-testid="stAlert"] {{
            position:fixed!important;
            right:7vw!important;
            bottom:3vh!important;
            width:30vw!important;
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
    with st.form("kanibal_login_form", clear_on_submit=False):
        st.markdown(
            """
            <div class="login-user-icon"></div>
            <div class="login-title"></div>
            <div class="login-subtitle"></div>
            """,
            unsafe_allow_html=True,
        )
        username = st.text_input("Adres e-mail lub login", placeholder="Wprowadź login")
        password = st.text_input("Hasło", type="password", placeholder="Wprowadź hasło")
        submitted = st.form_submit_button("Zaloguj się", use_container_width=True)
        st.markdown('<div class="login-note"></div>', unsafe_allow_html=True)

    if submitted:
        if authenticate(username.strip(), password):
            st.session_state.auth_ok = True
            st.session_state.auth_user = username.strip()
            st.rerun()
        else:
            st.error("Nieprawidłowy login lub hasło.")

    st.stop()
