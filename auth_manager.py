"""
Simple closed login layer for Streamlit dashboard.
- No public registration.
- Users are managed manually in users.json.
- Supports plain text passwords for easy setup and sha256 hashes for safer use.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, Any

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

    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] {display: none !important;}
        .block-container {max-width: 560px !important; padding-top: 6rem !important;}
        .login-card {
            background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.025));
            border: 1px solid rgba(88,255,47,0.22);
            border-radius: 24px;
            padding: 28px;
            box-shadow: 0 22px 70px rgba(0,0,0,0.5);
            text-align: center;
        }
        .login-title {font-size: 34px; font-weight: 900; color: #ffffff; letter-spacing: 1px;}
        .login-subtitle {font-size: 13px; color: #58ff2f; margin-top: 8px; letter-spacing: 3px;}
        </style>
        <div class="login-card">
            <div class="login-title">KANIBAL ANALYTICS</div>
            <div class="login-subtitle">ZAMKNIĘTY PANEL DOSTĘPU</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("kanibal_login_form", clear_on_submit=False):
        username = st.text_input("Nazwa użytkownika")
        password = st.text_input("Hasło", type="password")
        submitted = st.form_submit_button("Zaloguj", use_container_width=True)

    if submitted:
        if authenticate(username.strip(), password):
            st.session_state.auth_ok = True
            st.session_state.auth_user = username.strip()
            st.rerun()
        else:
            st.error("Nieprawidłowa nazwa użytkownika lub hasło.")

    st.stop()
