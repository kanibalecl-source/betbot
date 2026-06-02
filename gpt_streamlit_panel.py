from __future__ import annotations

import json
import html
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import streamlit as st


def _load_report(base_dir: Path, profile: str = "prematch", source_files=None) -> Dict[str, Any]:
    try:
        from gpt_match_value_engine import load_latest_report
        return load_latest_report(base_dir, profile=profile, source_files=source_files)
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
        ("Wartość kursu", "value_kurs"),
        ("Ryzyka", "ryzyka"),
        ("Rekomendacja", "rekomendacja"),
    ]
    for label, key in labels:
        value = analysis.get(key)
        if value:
            parts.append(f"**{label}:** {value}")
    return "\n\n".join(parts) if parts else str(item.get("summary", ""))


def _decision_label(value: Any) -> str:
    raw = str(value or "").upper()
    if raw == "PLAY":
        return "GRAĆ"
    if raw == "SKIP":
        return "POMIŃ"
    return raw or "-"


def _dark_table(rows: list[dict[str, Any]], columns: list[str], empty_text: str = "Brak danych.") -> None:
    if not rows:
        st.markdown(
            f'<div class="ka-table-scroll"><table class="ka-table"><thead><tr><th>Informacja</th></tr></thead><tbody><tr><td>{html.escape(empty_text)}</td></tr></tbody></table></div>',
            unsafe_allow_html=True,
        )
        return
    header = "".join(f"<th>{html.escape(str(col))}</th>" for col in columns)
    body_rows = []
    for row in rows:
        cells = []
        for col in columns:
            value = row.get(col, "")
            if col == "Decyzja":
                label = html.escape(str(value or "-"))
                pill_class = "pill-green" if "GRA" in label.upper() else "pill-yellow"
                cells.append(f'<td><span class="pill {pill_class}">{label}</span></td>')
            else:
                cells.append(f"<td>{html.escape(str(value if value not in (None, '') else '-'))}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    table = f'<div class="ka-table-scroll"><table class="ka-table"><thead><tr>{header}</tr></thead><tbody>{"".join(body_rows)}</tbody></table></div>'
    st.markdown(table, unsafe_allow_html=True)


def render_gpt_tab(base_dir=None, profile_name: str = "Prematch", key_prefix: str = "prematch", source_files=None):
    base_dir = Path(base_dir or Path(__file__).resolve().parent)
    st.markdown(f"<div class='ka-title'><span class='ka-dot'></span>ANALIZA GPT - {profile_name.upper()}</div>", unsafe_allow_html=True)
    st.caption("Opisowa analiza GPT działa jako osobny moduł. Nie zmienia logiki typowania ani wyglądu pozostałych zakładek.")

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        limit = st.number_input("Limit meczów do analizy", min_value=1, max_value=50, value=10, step=1, key=f"{key_prefix}_gpt_analysis_limit")
    with col2:
        run = st.button("Uruchom analizę GPT", use_container_width=True, key=f"{key_prefix}_run_gpt_analysis")
    with col3:
        st.info(f"Analiza działa na profilu {profile_name}. Wyniki są zapisywane osobno dla tego profilu.")

    if run:
        with st.spinner("GPT analizuje mecze i buduje AKO..."):
            try:
                from gpt_match_value_engine import run_full_gpt_analysis
                report = run_full_gpt_analysis(base_dir, limit=int(limit), profile=key_prefix, source_files=source_files)
                _save_gpt_to_storage(report)
                st.success(f"Gotowe. Przeanalizowano: {report.get('count', 0)}")
            except Exception as exc:
                st.error(f"Błąd GPT: {exc}")

    report = _load_report(base_dir, profile=key_prefix, source_files=source_files)
    if report.get("message"):
        st.warning(report.get("message"))

    analyses = report.get("analyses", []) or []
    coupons = report.get("coupons", []) or []

    m1, m2, m3, m4 = st.columns(4)
    playable = [a for a in analyses if str(a.get("decision", "")).upper() == "PLAY"]
    m1.metric("Analizy GPT", len(analyses))
    m2.metric("Do gry", len(playable))
    avg_conf = round(sum(float(a.get("confidence", 0) or 0) for a in analyses) / len(analyses), 1) if analyses else 0
    m3.metric("Śr. pewność", f"{avg_conf}%")
    m4.metric("Kupony AKO", len(coupons))

    if analyses:
        table_rows = []
        for a in analyses:
            table_rows.append({
                "Mecz": a.get("match"),
                "Typ": a.get("bet"),
                "Kurs": a.get("odds"),
                "Decyzja": _decision_label(a.get("decision")),
                "Pewność": a.get("confidence"),
                "Wartość": a.get("value_score"),
                "Ryzyko": a.get("risk"),
            })
        _dark_table(table_rows, ["Mecz", "Typ", "Kurs", "Decyzja", "Pewność", "Wartość", "Ryzyko"])

        for a in analyses[:20]:
            decision = _decision_label(a.get("decision", "SKIP"))
            with st.expander(f"{decision} | {a.get('match')} | {a.get('bet')} | {a.get('confidence', 0)}%"):
                st.write(a.get("summary", ""))
                st.markdown(_analysis_text(a))

    st.markdown("### Kupony AKO")
    if coupons:
        for c in coupons:
            with st.container(border=True):
                st.subheader(f"{c.get('name')} — {c.get('label', '')}")
                st.write(f"Kurs całkowity: **{c.get('total_odds')}** | Śr. pewność: **{c.get('avg_confidence')}%** | Ryzyko: **{c.get('risk')}**")
                picks = c.get("picks") or []
                if picks:
                    _dark_table(
                        [{"Mecz": p.get("match"), "Typ": p.get("bet"), "Kurs": p.get("odds"), "Pewność": p.get("confidence")} for p in picks],
                        ["Mecz", "Typ", "Kurs", "Pewność"],
                    )
                else:
                    st.caption("Brak typów spełniających kryteria.")
    else:
        st.caption("Brak kuponów - uruchom analizę GPT.")

