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


def _login_css() -> str:
    banner_uri = _asset_data_uri(BASE_DIR / "kanibal_banner_pro.jpg")
    banner_html = (
        f"<img src='{banner_uri}' alt='KANIBAL ANALYTICS'>"
        if banner_uri
        else "<div class='login-fallback'>KANIBAL<br><span>ANALYTICS</span></div>"
    )
    st.markdown(
        f"""
        <style>
        section[data-testid="stSidebar"] {{display:none!important;}}
        .block-container {{max-width:1920px!important;padding:2.4rem 3.4rem 1rem!important;}}
        .stApp {{
            background:
                radial-gradient(circle at 15% 20%,rgba(124,255,43,.12),transparent 28%),
                radial-gradient(circle at 82% 72%,rgba(255,196,0,.08),transparent 24%),
                linear-gradient(135deg,#020404 0%,#07100b 46%,#030506 100%)!important;
        }}
        .stApp::before {{
            content:"";
            position:fixed;
            inset:0;
            opacity:.18;
            pointer-events:none;
            background-image:
                linear-gradient(rgba(124,255,43,.14) 1px,transparent 1px),
                linear-gradient(90deg,rgba(124,255,43,.14) 1px,transparent 1px);
            background-size:64px 64px;
            -webkit-mask-image:linear-gradient(90deg,rgba(0,0,0,.82),transparent 72%);
            mask-image:linear-gradient(90deg,rgba(0,0,0,.82),transparent 72%);
        }}
        .login-orb-wrap {{min-height:720px;display:flex;align-items:center;justify-content:center;position:relative;}}
        .login-orb-wrap::before {{
            content:"";
            position:absolute;
            width:760px;
            height:760px;
            border-radius:50%;
            background:radial-gradient(circle,rgba(124,255,43,.16),rgba(124,255,43,.05) 38%,transparent 70%);
            filter:blur(10px);
        }}
        .login-orb {{
            position:relative;
            width:min(720px,70vw);
            aspect-ratio:1;
            border-radius:50%;
            padding:18px;
            border:1px solid rgba(124,255,43,.34);
            background:
                radial-gradient(circle at 34% 28%,rgba(255,255,255,.16),transparent 18%),
                linear-gradient(145deg,rgba(124,255,43,.22),rgba(255,196,0,.10) 48%,rgba(0,0,0,.72));
            box-shadow:0 42px 120px rgba(0,0,0,.62),0 0 70px rgba(124,255,43,.20),inset 0 0 40px rgba(124,255,43,.08);
        }}
        .login-orb::before,.login-orb::after {{
            content:"";
            position:absolute;
            inset:-18px;
            border-radius:50%;
            border:1px solid rgba(124,255,43,.14);
            pointer-events:none;
        }}
        .login-orb::after {{inset:34px;border-color:rgba(255,255,255,.08);box-shadow:inset 0 0 60px rgba(0,0,0,.48);}}
        .login-orb img {{
            width:100%;
            height:100%;
            display:block;
            object-fit:contain;
            object-position:center;
            border-radius:50%;
            border:1px solid rgba(255,255,255,.10);
            padding:48px;
            background:radial-gradient(circle at 50% 50%,#071014 0%,#020505 72%);
            filter:saturate(1.08) contrast(1.08);
        }}
        .login-fallback {{
            width:100%;
            height:100%;
            border-radius:50%;
            display:flex;
            align-items:center;
            justify-content:center;
            flex-direction:column;
            color:#fff;
            font-size:58px;
            font-weight:950;
            background:#071014;
        }}
        .login-fallback span {{color:#7CFF2B;font-size:22px;letter-spacing:.26em;}}
        div[data-testid="stForm"] {{
            padding:32px;
            border:1px solid rgba(124,255,43,.20);
            border-radius:20px;
            background:linear-gradient(180deg,rgba(12,19,24,.94),rgba(5,9,11,.96));
            box-shadow:0 26px 90px rgba(0,0,0,.56),0 0 48px rgba(124,255,43,.08);
        }}
        div[data-testid="stForm"]::before {{content:"";display:block;width:50px;height:2px;margin-bottom:26px;background:#7CFF2B;}}
        .login-head {{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:20px;}}
        .login-title {{font-size:26px;font-weight:950;color:#fff;}}
        .login-badge {{
            color:#7CFF2B;
            border:1px solid rgba(124,255,43,.28);
            background:rgba(124,255,43,.08);
            border-radius:999px;
            padding:8px 12px;
            font-size:11px;
            font-weight:950;
            text-transform:uppercase;
            letter-spacing:.08em;
        }}
        .login-note {{
            margin-top:18px;
            color:#98a49d;
            font-size:12px;
            line-height:1.45;
            border-top:1px solid rgba(255,255,255,.08);
            padding-top:18px;
        }}
        div[data-testid="stTextInput"] label {{
            color:#a6b0b9!important;
            font-size:12px!important;
            font-weight:950!important;
            text-transform:uppercase!important;
            letter-spacing:.10em!important;
        }}
        div[data-testid="stTextInput"] input {{
            height:54px!important;
            border-radius:12px!important;
            border:1px solid rgba(255,255,255,.12)!important;
            background:#071014!important;
            color:#fff!important;
            font-size:15px!important;
        }}
        div[data-testid="stTextInput"] input:focus {{
            border-color:rgba(124,255,43,.65)!important;
            box-shadow:0 0 0 3px rgba(124,255,43,.10)!important;
        }}
        div[data-testid="stFormSubmitButton"] button {{
            height:56px!important;
            border:1px solid rgba(124,255,43,.46)!important;
            border-radius:12px!important;
            background:linear-gradient(180deg,rgba(124,255,43,.30),rgba(23,100,30,.32))!important;
            color:#fff!important;
            font-weight:950!important;
            font-size:14px!important;
            letter-spacing:.12em!important;
            text-transform:uppercase!important;
            box-shadow:0 0 28px rgba(124,255,43,.12)!important;
        }}
        @media(max-width:1100px){{
            .block-container {{padding:1.2rem!important;}}
            .login-orb-wrap {{min-height:420px;}}
            .login-orb {{width:min(430px,88vw);}}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    return banner_html


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

    banner_html = _login_css()
    left_col, right_col = st.columns([1.15, 0.85], vertical_alignment="center")
    with left_col:
        st.markdown(
            f'<div class="login-orb-wrap"><div class="login-orb">{banner_html}</div></div>',
            unsafe_allow_html=True,
        )
    with right_col:
        with st.form("kanibal_login_form", clear_on_submit=False):
            st.markdown(
                """
                <div class="login-head">
                    <div class="login-title">Logowanie</div>
                    <div class="login-badge">Panel prywatny</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            username = st.text_input("Login")
            password = st.text_input("Hasło", type="password")
            submitted = st.form_submit_button("Zaloguj", use_container_width=True)
            st.markdown(
                '<div class="login-note">Dostęp tylko dla autoryzowanego użytkownika. Sesja po zalogowaniu prowadzi bezpośrednio do panelu KANIBAL ANALYTICS.</div>',
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
