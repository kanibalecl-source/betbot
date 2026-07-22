"""Local-only country flag helpers used by the Streamlit presentation layer.

The module has no network access and no dependency on the prediction pipeline.
Flags are rendered as inline SVG, so Windows does not replace them with grey
two-letter emoji boxes. No external image host or network request is used.
"""

from __future__ import annotations

import html
import re
import unicodedata
from typing import Any, Mapping


_COUNTRIES = """
Afghanistan|AF
Albania|AL
Algeria|DZ
Andorra|AD
Angola|AO
Argentina|AR
Armenia|AM
Australia|AU
Austria|AT
Azerbaijan|AZ
Bahrain|BH
Bangladesh|BD
Belarus|BY
Belgium|BE
Benin|BJ
Bolivia|BO
Bosnia and Herzegovina|BA
Botswana|BW
Brazil|BR
Bulgaria|BG
Burkina Faso|BF
Burundi|BI
Cambodia|KH
Cameroon|CM
Canada|CA
Cape Verde|CV
Central African Republic|CF
Chad|TD
Chile|CL
China|CN
Colombia|CO
Comoros|KM
Congo|CG
Costa Rica|CR
Croatia|HR
Cuba|CU
Cyprus|CY
Czechia|CZ
Denmark|DK
Dominican Republic|DO
DR Congo|CD
Ecuador|EC
Egypt|EG
El Salvador|SV
England|GB-ENG
Equatorial Guinea|GQ
Estonia|EE
Eswatini|SZ
Ethiopia|ET
Faroe Islands|FO
Fiji|FJ
Finland|FI
France|FR
Gabon|GA
Gambia|GM
Georgia|GE
Germany|DE
Ghana|GH
Gibraltar|GI
Greece|GR
Guatemala|GT
Guinea|GN
Guinea-Bissau|GW
Haiti|HT
Honduras|HN
Hong Kong|HK
Hungary|HU
Iceland|IS
India|IN
Indonesia|ID
Iran|IR
Iraq|IQ
Ireland|IE
Israel|IL
Italy|IT
Ivory Coast|CI
Jamaica|JM
Japan|JP
Jordan|JO
Kazakhstan|KZ
Kenya|KE
Kosovo|XK
Kuwait|KW
Kyrgyzstan|KG
Latvia|LV
Lebanon|LB
Liberia|LR
Libya|LY
Liechtenstein|LI
Lithuania|LT
Luxembourg|LU
Madagascar|MG
Malawi|MW
Malaysia|MY
Mali|ML
Malta|MT
Mauritania|MR
Mauritius|MU
Mexico|MX
Moldova|MD
Monaco|MC
Mongolia|MN
Montenegro|ME
Morocco|MA
Mozambique|MZ
Myanmar|MM
Namibia|NA
Netherlands|NL
New Zealand|NZ
Nicaragua|NI
Niger|NE
Nigeria|NG
North Macedonia|MK
Northern Ireland|GB-NIR
Norway|NO
Oman|OM
Pakistan|PK
Palestine|PS
Panama|PA
Paraguay|PY
Peru|PE
Philippines|PH
Poland|PL
Portugal|PT
Puerto Rico|PR
Qatar|QA
Romania|RO
Russia|RU
Rwanda|RW
San Marino|SM
Saudi Arabia|SA
Scotland|GB-SCT
Senegal|SN
Serbia|RS
Sierra Leone|SL
Singapore|SG
Slovakia|SK
Slovenia|SI
South Africa|ZA
South Korea|KR
Spain|ES
Sudan|SD
Suriname|SR
Sweden|SE
Switzerland|CH
Syria|SY
Taiwan|TW
Tajikistan|TJ
Tanzania|TZ
Thailand|TH
Togo|TG
Trinidad and Tobago|TT
Tunisia|TN
Turkey|TR
Turkmenistan|TM
Uganda|UG
Ukraine|UA
United Arab Emirates|AE
United States|US
Uruguay|UY
Uzbekistan|UZ
Venezuela|VE
Vietnam|VN
Wales|GB-WLS
Zambia|ZM
Zimbabwe|ZW
"""


def _key(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


COUNTRY_CODES = {
    _key(name): code
    for name, code in (line.split("|", 1) for line in _COUNTRIES.strip().splitlines())
}

COUNTRY_CODES.update({
    "usa": "US",
    "u s a": "US",
    "united states of america": "US",
    "korea republic": "KR",
    "republic of korea": "KR",
    "czech republic": "CZ",
    "turkiye": "TR",
    "republic of ireland": "IE",
    "bosnia herzegovina": "BA",
    "bosnia herz": "BA",
    "north korea": "KP",
    "korea dpr": "KP",
    "congo dr": "CD",
    "congo democratic republic": "CD",
    "democratic republic of the congo": "CD",
    "cote d ivoire": "CI",
    "cape verde islands": "CV",
    "uae": "AE",
    "fyr macedonia": "MK",
    "macedonia": "MK",
    "hong kong china": "HK",
    "chinese taipei": "TW",
})

_WORLD_KEYS = {"world", "international", "europe", "asia", "africa", "south america", "north america"}


def country_code(value: Any) -> str:
    """Return a supported ISO/FIFA-style code or an empty string."""
    key = _key(value)
    if not key or key in _WORLD_KEYS:
        return ""
    if key in COUNTRY_CODES:
        return COUNTRY_CODES[key]
    raw = str(value).strip().upper()
    if re.fullmatch(r"[A-Z]{2}", raw):
        return raw
    return ""


def flag_emoji(code: str) -> str:
    """Build a flag emoji. Subdivision codes use the parent country flag."""
    parent = str(code or "").split("-", 1)[0].upper()
    if not re.fullmatch(r"[A-Z]{2}", parent):
        return ""
    return "".join(chr(0x1F1E6 + ord(char) - ord("A")) for char in parent)


_HORIZONTAL_FLAGS = {
    "PL": ("#ffffff", "#dc143c"), "DE": ("#151515", "#dd0000", "#ffce00"),
    "ES": ("#aa151b", "#f1bf00", "#aa151b"), "NL": ("#ae1c28", "#ffffff", "#21468b"),
    "AT": ("#ed2939", "#ffffff", "#ed2939"), "HU": ("#ce2939", "#ffffff", "#477050"),
    "BG": ("#ffffff", "#00966e", "#d62612"), "EE": ("#4891d9", "#111111", "#ffffff"),
    "LT": ("#fdb913", "#006a44", "#c1272d"), "LV": ("#9e3039", "#ffffff", "#9e3039"),
    "UA": ("#0057b7", "#ffd700"), "RU": ("#ffffff", "#0039a6", "#d52b1e"),
    "AR": ("#74acdf", "#ffffff", "#74acdf"), "HR": ("#ff0000", "#ffffff", "#171796"),
    "LU": ("#ed2939", "#ffffff", "#00a1de"), "SI": ("#ffffff", "#005da4", "#ed1c24"),
    "SK": ("#ffffff", "#0b4ea2", "#ee1c25"), "RS": ("#c6363c", "#0c4076", "#ffffff"),
}

_VERTICAL_FLAGS = {
    "FR": ("#0055a4", "#ffffff", "#ef4135"), "IT": ("#009246", "#ffffff", "#ce2b37"),
    "BE": ("#111111", "#fdda24", "#ef3340"), "IE": ("#169b62", "#ffffff", "#ff883e"),
    "CI": ("#f77f00", "#ffffff", "#009e60"), "RO": ("#002b7f", "#fcd116", "#ce1126"),
}


def _stripes(colors: tuple[str, ...], vertical: bool = False) -> str:
    size = 24 / len(colors) if vertical else 16 / len(colors)
    parts = []
    for index, color in enumerate(colors):
        if vertical:
            parts.append(f'<path fill="{color}" d="M{index * size:g} 0h{size:g}v16H{index * size:g}z"/>')
        else:
            parts.append(f'<path fill="{color}" d="M0 {index * size:g}h24v{size:g}H0z"/>')
    return "".join(parts)


def _flag_art(code: str) -> str:
    """Return compact flag artwork or an honest ISO badge fallback."""
    code = str(code or "").upper()
    parent = code.split("-", 1)[0]
    if code in _VERTICAL_FLAGS:
        return _stripes(_VERTICAL_FLAGS[code], True)
    if code in _HORIZONTAL_FLAGS:
        return _stripes(_HORIZONTAL_FLAGS[code])
    if code == "CZ":
        return '<path fill="#fff" d="M0 0h24v8H0z"/><path fill="#d7141a" d="M0 8h24v8H0z"/><path fill="#11457e" d="M0 0l10 8-10 8z"/>'
    if code in {"DK", "SE", "NO", "FI"}:
        base, cross = {"DK": ("#c8102e", "#fff"), "SE": ("#006aa7", "#fecc00"), "NO": ("#ba0c2f", "#fff"), "FI": ("#fff", "#003580")}[code]
        art = f'<path fill="{base}" d="M0 0h24v16H0z"/><path fill="{cross}" d="M7 0h3v16H7zM0 6h24v3H0z"/>'
        if code == "NO":
            art += '<path fill="#00205b" d="M8 0h1v16H8zM0 7h24v1H0z"/>'
        return art
    if code == "CH":
        return '<path fill="#d52b1e" d="M0 0h24v16H0z"/><path fill="#fff" d="M10 3h4v3h3v4h-3v3h-4v-3H7V6h3z"/>'
    if code == "JP":
        return '<path fill="#fff" d="M0 0h24v16H0z"/><circle fill="#bc002d" cx="12" cy="8" r="4"/>'
    if code == "BR":
        return '<path fill="#009b3a" d="M0 0h24v16H0z"/><path fill="#ffdf00" d="M12 2l9 6-9 6-9-6z"/><circle fill="#002776" cx="12" cy="8" r="3.4"/>'
    if code == "PT":
        return '<path fill="#046a38" d="M0 0h9v16H0z"/><path fill="#da291c" d="M9 0h15v16H9z"/><circle fill="#ffcd00" cx="9" cy="8" r="2.2"/>'
    if code == "GB-ENG":
        return '<path fill="#fff" d="M0 0h24v16H0z"/><path fill="#ce1124" d="M10 0h4v16h-4zM0 6h24v4H0z"/>'
    if code == "GB-SCT":
        return '<path fill="#005eb8" d="M0 0h24v16H0z"/><path stroke="#fff" stroke-width="3" d="M-1 0l26 16M25 0L-1 16"/>'
    if code == "GB-WLS":
        return '<path fill="#fff" d="M0 0h24v8H0z"/><path fill="#00ab39" d="M0 8h24v8H0z"/><path fill="#d30731" d="M5 10l4-6 2 4 4-3 4 7-7-2-3 3z"/>'
    if code == "GB-NIR":
        return '<path fill="#fff" d="M0 0h24v16H0z"/><path fill="#c8102e" d="M10 0h4v16h-4zM0 6h24v4H0z"/><circle fill="#fff" stroke="#c8102e" cx="12" cy="8" r="2"/>'
    if parent == "GB":
        return '<path fill="#012169" d="M0 0h24v16H0z"/><path stroke="#fff" stroke-width="4" d="M0 0l24 16M24 0L0 16"/><path stroke="#c8102e" stroke-width="2" d="M0 0l24 16M24 0L0 16"/><path fill="#fff" d="M9 0h6v16H9zM0 5h24v6H0z"/><path fill="#c8102e" d="M10.5 0h3v16h-3zM0 6.5h24v3H0z"/>'
    safe = html.escape(parent[:2])
    return f'<path fill="#18211d" d="M0 0h24v16H0z"/><text x="12" y="11" text-anchor="middle" fill="#cdd6d1" font-size="7" font-family="Arial,sans-serif" font-weight="700">{safe}</text>'


def _flag_svg(code: str) -> str:
    return f'<svg viewBox="0 0 24 16" aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg">{_flag_art(code)}</svg>'


def _world_svg() -> str:
    return '<svg viewBox="0 0 24 16" aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="8" r="6.4" fill="none" stroke="#9be900" stroke-width="1.5"/><path d="M5.6 8h12.8M12 1.6c2 1.9 3 4 3 6.4s-1 4.5-3 6.4c-2-1.9-3-4-3-6.4s1-4.5 3-6.4z" fill="none" stroke="#9be900" stroke-width="1.1"/></svg>'


def _value(row: Mapping[str, Any], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip() and str(value).strip().lower() != "nan":
            return str(value).strip()
    return ""


def split_teams(row: Mapping[str, Any]) -> tuple[str, str]:
    home = _value(row, "home_team", "home")
    away = _value(row, "away_team", "away")
    if home and away:
        return home, away
    match = _value(row, "match", "mecz", "match_name")
    for separator in (" vs ", " v ", " - ", " – ", " — "):
        if separator in match:
            left, right = match.split(separator, 1)
            return left.strip(), right.strip()
    return "", ""


def _flag_span(code: str, title: str) -> str:
    if not re.fullmatch(r"[A-Z]{2}(?:-[A-Z]{3})?", str(code or "").upper()):
        return ""
    return f'<span class="ka-country-flag" title="{html.escape(title, quote=True)}">{_flag_svg(code)}</span>'


def league_html(row: Mapping[str, Any]) -> str:
    """Format a league with its country flag, without changing stored data."""
    league = _value(row, "league", "liga") or "-"
    country = _value(row, "country", "league_country")
    if not country and " / " in league:
        league_name, possible_country = league.rsplit(" / ", 1)
        if country_code(possible_country) or _key(possible_country) in _WORLD_KEYS:
            league, country = league_name.strip(), possible_country.strip()
    code = country_code(country)
    if code:
        prefix = _flag_span(code, country)
    elif _key(country) in _WORLD_KEYS:
        prefix = f'<span class="ka-country-flag ka-world-flag" title="Rozgrywki międzynarodowe">{_world_svg()}</span>'
    else:
        prefix = ""
    return f'<span class="ka-country-label">{prefix}<span>{html.escape(league)}</span></span>'

    # Kept unreachable only for compatibility with older source patches.
    prefix = _flag_span(code, country) if code else ('<span class="ka-country-flag ka-world-flag" title="Rozgrywki międzynarodowe">🌐</span>' if _key(country) in _WORLD_KEYS else "")
    return f'<span class="ka-country-label">{prefix}<span>{html.escape(league)}</span></span>'


def match_html(row: Mapping[str, Any], bold: bool = True) -> str:
    """Put flags next to both teams only when both names are national teams."""
    match = _value(row, "match", "mecz", "match_name") or "-"
    home, away = split_teams(row)
    home_code, away_code = country_code(home), country_code(away)
    if home and away and home_code and away_code:
        value = (
            f'<span class="ka-team-name">{_flag_span(home_code, home)}{html.escape(home)}</span>'
            f'<span class="ka-match-separator"> – </span>'
            f'<span class="ka-team-name">{_flag_span(away_code, away)}{html.escape(away)}</span>'
        )
        return f"<b>{value}</b>" if bold else value
    if home and away and home_code and away_code:
        separator = " – "
        value = (
            f'<span class="ka-team-name">{_flag_span(home_code, home)}{html.escape(home)}</span>'
            f'<span class="ka-match-separator">{separator}</span>'
            f'<span class="ka-team-name">{_flag_span(away_code, away)}{html.escape(away)}</span>'
        )
    else:
        value = html.escape(match)
    return f"<b>{value}</b>" if bold else value
