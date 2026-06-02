from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

from persistent_storage import fetch_recent_picks, save_gpt_analysis, summary as storage_summary


def _df_records(df: pd.DataFrame, limit: int = 12) -> List[Dict[str, Any]]:
    try:
        if df is None or df.empty:
            return []
        return df.head(limit).fillna("").to_dict(orient="records")
    except Exception:
        return []


def build_context(picks: pd.DataFrame, live: pd.DataFrame, results: pd.DataFrame, profile_name: str = "Prematch") -> Dict[str, Any]:
    return {
        "profile": profile_name,
        "storage": storage_summary(),
        "recent_memory_picks": fetch_recent_picks(30),
        "current_picks": _df_records(picks, 20),
        "live_matches": _df_records(live, 20),
        "results_history": _df_records(results, 20),
    }


def call_gpt(question: str, context: Dict[str, Any], risk_profile: str, max_legs: int) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"

    if not api_key:
        return "Brakuje OPENAI_API_KEY w Railway Variables. Dodaj klucz i zrestartuj deploy."

    if OpenAI is None:
        return "Biblioteka openai nie jest zainstalowana. Sprawdź requirements.txt."

    client = OpenAI(api_key=api_key)

    system_prompt = """
Jesteś analitykiem bettingowym w bocie KANIBAL ANALYTICS.
Nie udawaj pewności. Nie obiecuj zysku. Analizuj ryzyko.
Używaj danych bota jako bazowego filtra, ale jeśli masz dostęp do wyszukiwania w internecie,
sprawdź aktualny kontekst: forma, kontuzje, składy, atmosfera, motywacja, terminarz.
Przed budową kuponu uwzględnij preferencje użytkownika: profil ryzyka i maksymalną liczbę zdarzeń.
Odpowiadaj po polsku, opisowo, z jasnym podziałem:
1) Najważniejsze obserwacje
2) Pytania/założenia, jeśli brakuje danych
3) Propozycja kuponu
4) Czego unikać
5) Poziom ryzyka
"""

    user_input = {
        "question": question,
        "risk_profile": risk_profile,
        "max_legs": max_legs,
        "bot_context": context,
    }

    # Najpierw próbujemy Responses API z web_search_preview. Jeśli konto/model tego nie obsługuje,
    # schodzimy do zwykłej odpowiedzi bez wyszukiwania w internecie.
    try:
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_input, ensure_ascii=False, default=str)},
            ],
            tools=[{"type": "web_search_preview"}],
        )
        answer = getattr(response, "output_text", "") or str(response)
    except Exception as first_error:
        try:
            response = client.responses.create(
                model=model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_input, ensure_ascii=False, default=str)},
                ],
            )
            answer = getattr(response, "output_text", "") or str(response)
            answer += f"\n\n_Uwaga techniczna: wyszukiwanie w internecie nie zostało użyte: {first_error}_"
        except Exception as second_error:
            answer = f"Błąd połączenia z OpenAI: {second_error}"

    try:
        save_gpt_analysis(question, answer, model, context)
    except Exception:
        pass

    return answer


def render_gpt_chat_tab(picks: pd.DataFrame, live: pd.DataFrame, results: pd.DataFrame, profile_name: str = "Prematch", key_prefix: str = "prematch") -> None:
    st.markdown(f"## CZAT GPT - {profile_name.upper()}")
    st.caption("Rozmawiasz z GPT o typach aktywnego profilu. GPT widzi aktualne typy, historię i pamięć danych.")

    context = build_context(picks, live, results, profile_name=profile_name)
    s = context.get("storage", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Typy profilu", len(picks) if picks is not None else 0)
    c2.metric("Mecze live", len(live) if live is not None else 0)
    c3.metric("Analizy GPT", s.get("gpt_analyses", 0))
    c4.metric("Magazyn danych", "TRWAŁY" if s.get("persistent") else "LOKALNY")

    if not s.get("persistent"):
        st.warning("Dane zapisują się lokalnie. Na Railway dodaj Volume i ustaw PERSISTENT_DATA_DIR, aby nie znikały po ponownym wdrożeniu.")

    risk_profile = st.selectbox("Profil kuponu", ["bezpieczny", "średni", "agresywny"], index=1, key=f"{key_prefix}_gpt_risk_profile")
    max_legs = st.slider("Maksymalna liczba zdarzeń na AKO", 2, 8, 4, key=f"{key_prefix}_gpt_max_legs")

    quick_cols = st.columns(4)
    quick_questions = [
        ("Najlepszy singiel", f"Wskaż najlepszy singiel z profilu {profile_name} i uzasadnij ryzyko."),
        ("Kupon 2-3 mecze", f"Zbuduj ostrożny kupon 2-3 mecze z profilu {profile_name}."),
        ("Czego unikać", f"Wskaż, czego unikać w profilu {profile_name} i dlaczego."),
        ("Porównaj ligi", f"Porównaj ligi z profilu {profile_name} pod kątem trafności i ryzyka."),
    ]
    area_key = f"{key_prefix}_gpt_question_area"
    default_q = st.session_state.get(area_key, f"Przeanalizuj dzisiejsze typy z profilu {profile_name}, zadaj najważniejsze pytania i zaproponuj kupon AKO.")
    for col, (label, prompt) in zip(quick_cols, quick_questions):
        if col.button(label, key=f"{key_prefix}_quick_{label}"):
            st.session_state[area_key] = prompt
            default_q = prompt
    question = st.text_area("Twoje pytanie do GPT", value=default_q, height=120, key=area_key)

    if st.button("Zapytaj GPT", type="primary", key=f"{key_prefix}_ask_gpt"):
        with st.spinner("GPT analizuje dane bota i kontekst zewnętrzny..."):
            answer = call_gpt(question, context, risk_profile, max_legs)
            st.session_state[f"{key_prefix}_last_gpt_answer"] = answer

    if f"{key_prefix}_last_gpt_answer" in st.session_state:
        st.markdown("### Odpowiedź GPT")
        st.markdown(st.session_state[f"{key_prefix}_last_gpt_answer"])

