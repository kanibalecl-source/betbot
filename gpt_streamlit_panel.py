from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import streamlit as st


def _load_report(base_dir: Path) -> Dict[str, Any]:
    try:
        from gpt_match_value_engine import load_latest_report
        return load_latest_report(base_dir)
    except Exception as exc:
        return {"analyses": [], "coupons": [], "message": f"Nie udało się wczytać GPT: {exc}"}


def _save_gpt_to_storage(report: Dict[str, Any]) -> None:
    try:
        from agi_storage import upsert_gpt_analysis
        for item in report.get("analyses", []) or []:
            upsert_gpt_analysis(item)
    except Exception:
        pass


def _analysis_text(item: Dict[str, Any]) -> str:
    analysis = item.get("analysis") or {}
    if not isinstance(analysis, dict):
        return str(analysis)
    parts = []
    labels = [
        ("Forma", "forma"),
        ("Kontuzje i kadra", "kontuzje_kadra"),
        ("Styl gry i matchup", "styl_matchup"),
        ("Motywacja i atmosfera", "motywacja_atmosfera"),
        ("Value kurs", "value_kurs"),
        ("Ryzyka", "ryzyka"),
        ("Rekomendacja", "rekomendacja"),
    ]
    for label, key in labels:
        value = analysis.get(key)
        if value:
            parts.append(f"**{label}:** {value}")
    return "\n\n".join(parts) if parts else str(item.get("summary", ""))


def render_gpt_tab(base_dir=None):
    base_dir = Path(base_dir or Path(__file__).resolve().parent)
    st.markdown("<div class='ka-title'><span class='ka-dot'></span>GPT ANALYSIS</div>", unsafe_allow_html=True)
    st.caption("Opisowa analiza GPT działa jako osobny moduł. Nie zmienia logiki typowania ani wyglądu pozostałych zakładek.")

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        limit = st.number_input("Limit meczów do analizy", min_value=1, max_value=50, value=10, step=1)
    with col2:
        run = st.button("Uruchom analizę GPT", use_container_width=True)
    with col3:
        st.info("Model używa OPENAI_API_KEY. Wyniki są cache’owane i zapisywane do storage.")

    if run:
        with st.spinner("GPT analizuje mecze i buduje AKO..."):
            try:
                from gpt_match_value_engine import run_full_gpt_analysis
                report = run_full_gpt_analysis(base_dir, limit=int(limit))
                _save_gpt_to_storage(report)
                st.success(f"Gotowe. Przeanalizowano: {report.get('count', 0)}")
            except Exception as exc:
                st.error(f"Błąd GPT: {exc}")

    report = _load_report(base_dir)
    if report.get("message"):
        st.warning(report.get("message"))

    analyses = report.get("analyses", []) or []
    coupons = report.get("coupons", []) or []

    m1, m2, m3, m4 = st.columns(4)
    playable = [a for a in analyses if str(a.get("decision", "")).upper() == "PLAY"]
    m1.metric("Analizy GPT", len(analyses))
    m2.metric("PLAY", len(playable))
    avg_conf = round(sum(float(a.get("confidence", 0) or 0) for a in analyses) / len(analyses), 1) if analyses else 0
    m3.metric("Śr. confidence", f"{avg_conf}%")
    m4.metric("Kupony AKO", len(coupons))

    if analyses:
        table_rows = []
        for a in analyses:
            table_rows.append({
                "Mecz": a.get("match"),
                "Typ": a.get("bet"),
                "Kurs": a.get("odds"),
                "Decyzja": a.get("decision"),
                "Confidence": a.get("confidence"),
                "Value": a.get("value_score"),
                "Ryzyko": a.get("risk"),
            })
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

        for a in analyses[:20]:
            decision = str(a.get("decision", "SKIP")).upper()
            with st.expander(f"{decision} | {a.get('match')} | {a.get('bet')} | {a.get('confidence', 0)}%"):
                st.write(a.get("summary", ""))
                st.markdown(_analysis_text(a))

    st.markdown("### 💎 Kupony AKO")
    if coupons:
        for c in coupons:
            with st.container(border=True):
                st.subheader(f"{c.get('name')} — {c.get('label', '')}")
                st.write(f"Kurs całkowity: **{c.get('total_odds')}** | Śr. confidence: **{c.get('avg_confidence')}%** | Ryzyko: **{c.get('risk')}**")
                picks = c.get("picks") or []
                if picks:
                    st.dataframe(pd.DataFrame([{"Mecz": p.get("match"), "Typ": p.get("bet"), "Kurs": p.get("odds"), "Confidence": p.get("confidence")} for p in picks]), use_container_width=True, hide_index=True)
                else:
                    st.caption("Brak typów spełniających kryteria.")
    else:
        st.caption("Brak kuponów — uruchom analizę GPT.")
