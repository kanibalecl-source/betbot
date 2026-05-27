from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    root = project_root()
    out = root / "data" / "safe_modular_upgrade"
    out.mkdir(parents=True, exist_ok=True)
    return out


def read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def write_json(name: str, payload: Dict[str, Any]) -> Path:
    out = data_dir() / name
    payload = dict(payload)
    payload["generated_at"] = datetime.utcnow().isoformat()
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def write_csv(name: str, rows: List[Dict[str, Any]]) -> Path:
    out = data_dir() / name
    pd.DataFrame(rows).to_csv(out, index=False)
    return out


def numeric_series(df: pd.DataFrame, candidates: List[str]):
    for c in candidates:
        if c in df.columns:
            return pd.to_numeric(df[c], errors="coerce")
    return pd.Series(dtype=float)


def first_existing_file(candidates: List[str]) -> Path | None:
    root = project_root()
    for rel in candidates:
        p = root / rel
        if p.exists():
            return p
    return None
