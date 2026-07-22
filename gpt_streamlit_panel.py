from __future__ import annotations

import html
import os
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st


def _load_report(base_dir: Path, profile: str = "prematch", source_files=None) -> Dict[str, Any]:
    try:
        from gpt_match_value_engine import load_latest_report
        return load_latest_report(base_dir, profile=profile, source_files=source_files)
    except Exception as exc:
        return {"analyses": [], "coupons": [], "message": f"Nie udało się wczytać GPT: {exc}"}


def _load_candidates(base_dir: Path, profile: str, source_files=None, limit: int = 50) -> List[Dict[str, Any]]:
    try:
        from gpt_match_value_engine import load_candidate_matches
        return load_candidate_matches(base_dir, limit=limit, profile=profile, source_files=source_files)
    except Exception:
        return []


def _save_gpt_to_storage(report: Dict[str, Any]) -> None:
    try:
        from agi_storage import upsert_gpt_analysis
        for item in report.get("analyses", []) or []:
            upsert_gpt_analysis(item)
    except Exception:
        pass


def _key(item: Dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("match", "")).lower(),
        str(item.get("bet", "")).lower(),
        str(item.get("odds", "")),
    )


def _decision_label(value: Any) -> str:
    raw = str(value or "").upper()
    if raw == "PLAY":
        return "GRAĆ"
    if raw == "WATCH":
        return "OBSERWUJ"
    if raw == "SKIP":
        return "POMIŃ"
    return raw or "OCZEKUJE"


def _risk_label(value: Any) -> str:
    raw = str(value or "").lower()
    return {
        "low": "NISKIE",
        "medium": "ŚREDNIE",
        "high": "WYSOKIE",
        "very_high": "BARDZO WYSOKIE",
    }.get(raw, str(value or "-").upper())


def _pill_class(label: str) -> str:
    up = str(label).upper()
    if "GRA" in up:
        return "pill-green"
    if "POM" in up:
        return "pill-red"
    return "pill-yellow"


def _first_text(item: Dict[str, Any], *keys: str, default: str = "-") -> str:
    for key in keys:
        value = item.get(key)
        if value not in (None, "", "nan"):
            return str(value)
    return default


def _analysis_value(item: Dict[str, Any], *keys: str, default: str = "-") -> str:
    analysis = item.get("analysis") or {}
    if isinstance(analysis, dict):
        for key in keys:
            value = analysis.get(key)
            if value not in (None, "", "nan"):
                return str(value)
    return default


def _progress(value: Any) -> str:
    try:
        width = max(0, min(100, float(value or 0)))
    except Exception:
        width = 0
    return f'<div class="progress"><span style="width:{width:.0f}%"></span></div>'


def _inject_gpt_css() -> None:
    st.markdown(
        """
        <style>
        .gpt-row-head,.gpt-row{
            display:grid;
            grid-template-columns:2.6fr .82fr .52fr .82fr .9fr .62fr .9fr .82fr;
            gap:0;
            align-items:center;
        }
        .gpt-row-head{
            background:#fff;
            border-bottom:1px solid #dfe6ef;
            color:#111;
            text-transform:uppercase;
            font-size:11px;
            font-weight:950;
        }
        .gpt-row-head div{padding:13px 12px;}
        .gpt-row{
            min-height:62px;
            background:#fff;
            border:1px solid #dfe6ef;
            color:#111;
            font-size:13px;
            font-weight:850;
        }
        .gpt-row.selected{background:#fff;}
        .gpt-row div{padding:11px 12px;}
        .gpt-row b,.gpt-row .green,.gpt-row .yellow,.gpt-row .red{color:#111!important;}
        .muted-small{color:#111;font-size:12px;font-weight:700;}
        .gpt-footnote{color:#8f9a96;font-size:12px;font-weight:850;margin:12px 0 0;}
        div[class*="_analyze_"] div[data-testid="stButton"] button{
            min-height:34px!important;
            border-radius:7px!important;
            border:1px solid #cfd7e1!important;
            background:#fff!important;
            color:#111!important;
            font-size:11px!important;
            font-weight:950!important;
            padding:5px 8px!important;
            width:100%!important;
        }
        div[class*="_analyze_"] div[data-testid="stButton"] button:hover{
            background:#fff!important;
            border-color:#929eac!important;
            color:#111!important;
        }
        .gpt-side-panel{height:100%;}
        .gpt-detail-head{border:1px solid #dfe6ef;border-radius:8px;padding:16px;background:#fff;display:grid;gap:8px;margin-bottom:14px;}
        .gpt-detail-head span{font-size:13px;font-weight:850;color:#111;}
        .green{color:var(--green)!important}.yellow{color:var(--yellow)!important}.red{color:var(--red)!important}
        .gpt-score-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:14px;}
        .gpt-score-grid div{border:1px solid #dfe6ef;border-radius:8px;background:#fff;color:#111;padding:13px;}
        .gpt-score-grid span{display:block;color:#111;text-transform:uppercase;font-size:10px;font-weight:950;margin-bottom:8px;}
        .gpt-score-grid b{font-size:24px;}
        .gpt-notes{display:grid;gap:10px;}
        .gpt-notes div{border:1px solid #dfe6ef;border-left:3px solid #1478e8;border-radius:7px;background:#fff;color:#111;padding:12px 13px;font-size:13px;line-height:1.45;font-weight:800;}
        .gpt-ako-wrap{margin-top:14px;}
        .gpt-ako-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;}
        .gpt-ako-card{border:1px solid #dfe6ef;border-radius:8px;background:#fff;color:#111;padding:14px;min-height:106px;}
        .gpt-ako-card h4{margin:0 0 10px;font-size:13px;text-transform:uppercase;}
        .gpt-ako-card p{margin:0;color:#111;font-size:12px;line-height:1.45;font-weight:800;}
        @media(max-width:1100px){.gpt-row-head,.gpt-row{grid-template-columns:1fr}.gpt-ako-grid,.gpt-score-grid{grid-template-columns:1fr;}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_row(candidate: Dict[str, Any], analysis: Dict[str, Any] | None, idx: int, selected: bool, base_dir: Path, key_prefix: str, source_files, limit: int) -> None:
    source = analysis or candidate
    decision = _decision_label(source.get("decision")) if analysis else "OCZEKUJE"
    row_class = "gpt-row selected" if selected else "gpt-row"
    match = html.escape(_first_text(source, "match"))
    league = html.escape(_first_text(source, "league", default=""))
    bet = html.escape(_first_text(source, "bet"))
    odds = html.escape(_first_text(source, "odds"))
    value = html.escape(_first_text(source, "value_score", default="-")) if analysis else "-"
    risk = html.escape(_risk_label(source.get("risk"))) if analysis else "-"
    confidence = _progress(source.get("confidence")) if analysis else "-"
    st.markdown(
        f"""
        <div class="{row_class}">
            <div><b>{match}</b><br><span class="muted-small">{league}</span></div>
            <div><b>{bet}</b></div>
            <div><b>{odds}</b></div>
            <div><span class="pill {_pill_class(decision)}">{html.escape(decision)}</span></div>
            <div>{confidence}</div>
            <div><b>{value}</b></div>
            <div><b>{risk}</b></div>
            <div class="gpt-action"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="gpt-action">', unsafe_allow_html=True)
    cols = st.columns([7, 1])
    with cols[1]:
        if st.button("Analizuj GPT", key=f"{key_prefix}_analyze_{idx}", use_container_width=True):
            with st.spinner(f"GPT analizuje: {candidate.get('match', '')}"):
                try:
                    from gpt_match_value_engine import run_single_gpt_analysis
                    report = run_single_gpt_analysis(base_dir, idx, limit=limit, profile=key_prefix, source_files=source_files)
                    _save_gpt_to_storage(report)
                    st.session_state[f"{key_prefix}_selected_gpt_key"] = _key(candidate)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Błąd analizy GPT: {exc}")
    st.markdown("</div>", unsafe_allow_html=True)


def _render_details(item: Dict[str, Any] | None) -> None:
    if not item:
        st.markdown(
            '<div class="ka-panel"><h3>Szczegóły analizy</h3><p class="ka-sub">Kliknij Analizuj GPT przy wybranym meczu. Prompt uruchomi się tylko dla tego jednego typu.</p></div>',
            unsafe_allow_html=True,
        )
        return

    decision = _decision_label(item.get("decision"))
    match = html.escape(_first_text(item, "match"))
    bet = html.escape(_first_text(item, "bet"))
    odds = html.escape(_first_text(item, "odds"))
    confidence = html.escape(_first_text(item, "confidence", default="0"))
    quality = html.escape(_first_text(item, "quality_score", default="0"))
    value = html.escape(_first_text(item, "value_score", default="0"))
    reason = html.escape(_first_text(item, "main_reason", "summary", default="-"))
    form = html.escape(_analysis_value(item, "forma", "najwazniejsze_dane", default="-"))
    risks = html.escape(_analysis_value(item, "ryzyka", "argumenty_przeciw", default="-"))
    alternative = html.escape(_analysis_value(item, "alternatywa", "rekomendacja", default="-"))
    color = _pill_class(decision).replace("pill-", "")

    st.markdown(
        f"""
        <div class="ka-panel gpt-side-panel">
            <h3>Szczegóły analizy</h3>
            <div class="gpt-detail-head">
                <b>{match}</b>
                <span>Typ bota: <b>{bet} @ {odds}</b></span>
                <span>Decyzja GPT: <b class="{color}">{html.escape(decision)}</b></span>
            </div>
            <div class="gpt-score-grid">
                <div><span>Pewność</span><b>{confidence}%</b></div>
                <div><span>Jakość</span><b>{quality}/10</b></div>
                <div><span>Value</span><b>{value}</b></div>
            </div>
            <div class="gpt-notes">
                <div><b>Powód główny:</b> {reason}</div>
                <div><b>Forma:</b> {form}</div>
                <div><b>Ryzyka:</b> {risks}</div>
                <div><b>Alternatywa:</b> {alternative}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_ako(coupons: list[Dict[str, Any]]) -> None:
    cards = []
    defaults = [
        ("Najbezpieczniejszy", "Kupon powstanie po ręcznej analizie wybranych meczów."),
        ("Ryzyko / kurs", "GPT użyje wyłącznie typów, które zostały wcześniej przeanalizowane."),
        ("Do obserwacji", "Typy z potencjałem, ale wymagające ręcznego sprawdzenia składów lub rynku przed grą."),
    ]
    source = coupons[:3] if coupons else []
    for idx in range(3):
        if idx < len(source):
            coupon = source[idx]
            title = str(coupon.get("name") or defaults[idx][0])
            text = f"Kurs całkowity: {coupon.get('total_odds', '-')} | Śr. pewność: {coupon.get('avg_confidence', '-')}% | Ryzyko: {coupon.get('risk', '-')}"
        else:
            title, text = defaults[idx]
        cards.append(f"<div class='gpt-ako-card'><h4>{html.escape(title)}</h4><p>{html.escape(text)}</p></div>")
    st.markdown(
        f"""
        <div class="ka-panel gpt-ako-wrap">
            <h3>Propozycje AKO GPT</h3>
            <div class="gpt-ako-grid">{''.join(cards)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_gpt_tab(base_dir=None, profile_name: str = "Prematch", key_prefix: str = "prematch", source_files=None):
    _inject_gpt_css()
    base_dir = Path(base_dir or Path(__file__).resolve().parent)
    limit = int(os.getenv("GPT_AUTO_ANALYSIS_LIMIT", "50") or "50")
    api_ready = bool(os.getenv("OPENAI_API_KEY", "").strip())

    if not api_ready:
        st.warning("Brakuje OPENAI_API_KEY. Prompt nie wykona pełnej analizy, dopóki nie ustawisz klucza.")

    candidates = _load_candidates(base_dir, key_prefix, source_files=source_files, limit=limit)
    report = _load_report(base_dir, profile=key_prefix, source_files=source_files)
    if report.get("message"):
        st.warning(report.get("message"))

    analyses = report.get("analyses", []) or []
    coupons = report.get("coupons", []) or []
    lookup = {_key(item): item for item in analyses}
    playable = [a for a in analyses if str(a.get("decision", "")).upper() == "PLAY"]
    watch = [a for a in analyses if str(a.get("decision", "")).upper() == "WATCH"]
    skipped = [a for a in analyses if str(a.get("decision", "")).upper() == "SKIP"]
    avg_conf = round(sum(float(a.get("confidence", 0) or 0) for a in analyses) / len(analyses), 1) if analyses else 0
    selected_key = st.session_state.get(f"{key_prefix}_selected_gpt_key")
    selected = lookup.get(selected_key) if selected_key else (analyses[0] if analyses else None)

    left, right = st.columns([2.45, 1], gap="medium")
    with left:
        st.markdown(
            f"""
            <div class="ka-panel">
                <h3>Analiza GPT - {html.escape(profile_name.upper())}</h3>
                <div class="ka-grid" style="grid-template-columns:repeat(4,minmax(0,1fr));">
                    <div class="ka-card"><div class="ka-label">Analizy</div><div class="ka-value">{len(analyses)}</div><div class="ka-sub">wykonane kliknięciem</div></div>
                    <div class="ka-card"><div class="ka-label">Śr. pewność</div><div class="ka-value">{avg_conf}%</div><div class="ka-sub">GPT</div></div>
                    <div class="ka-card"><div class="ka-label">Obserwuj</div><div class="ka-value">{len(watch)}</div><div class="ka-sub">do ręcznej decyzji</div></div>
                    <div class="ka-card"><div class="ka-label">Pominięte</div><div class="ka-value">{len(skipped)}</div><div class="ka-sub">ryzyko / brak value</div></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="ka-panel">
                <div class="gpt-row-head">
                    <div>Mecz</div><div>Typ</div><div>Kurs</div><div>Decyzja</div><div>Pewność</div><div>Value</div><div>Ryzyko</div><div>Akcja</div>
                </div>
            """,
            unsafe_allow_html=True,
        )
        if not candidates:
            st.info("Brak typów wygenerowanych przez bota w tym profilu.")
        for idx, candidate in enumerate(candidates[:limit]):
            analysis = lookup.get(_key(candidate))
            _render_row(candidate, analysis, idx, selected_key == _key(candidate), base_dir, key_prefix, source_files, limit)
        st.markdown('</div>', unsafe_allow_html=True)
    with right:
        _render_details(selected)

    _render_ako(coupons)
