"""Audited QUALITY model registry with guarded manual and v7 promotion."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from quality_live_shadow import live_shadow_report
from storage_paths import get_data_dir


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return dict(value) if isinstance(value, Mapping) else {}
    except Exception:
        return {}


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def registry_status(data_dir: str | Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or get_data_dir()).resolve()
    active_path = Path(os.getenv("BETBOT_QUALITY_STATE", root / "quality_shadow_state.json")).resolve()
    candidate_path = Path(os.getenv(
        "BETBOT_QUALITY_CANDIDATE",
        root / "quality_retraining" / "quality_shadow_state.candidate.latest.json",
    )).resolve()
    candidate = _read(candidate_path)
    return {
        "active_path": str(active_path),
        "active_exists": active_path.is_file(),
        "active_sha256": _hash(active_path) if active_path.is_file() else "",
        "candidate_path": str(candidate_path),
        "candidate_exists": candidate_path.is_file(),
        "candidate_token": Path(str(candidate.get("candidate_path") or candidate_path)).name,
        "candidate_validation": candidate.get("validation", {}),
        "live_shadow": live_shadow_report(root),
        "automatic_promotion": False,
    }


def promote_candidate_manually(
    confirmation_token: str,
    data_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Promote only after two positive gates and an exact human-entered token."""
    root = Path(data_dir or get_data_dir()).resolve()
    status = registry_status(root)
    token = str(status["candidate_token"])
    if not token or confirmation_token.strip() != token:
        return {"status": "REFUSED_CONFIRMATION_TOKEN"}
    validation = status["candidate_validation"]
    if validation.get("status") != "POSITIVE_VALIDATION_MANUAL_APPROVAL":
        return {"status": "REFUSED_WALK_FORWARD_NOT_POSITIVE"}
    if status["live_shadow"].get("status") != "POSITIVE_LIVE_SHADOW_MANUAL_APPROVAL":
        return {"status": "REFUSED_LIVE_SHADOW_NOT_POSITIVE"}
    candidate_path = Path(status["candidate_path"]).resolve()
    active_path = Path(status["active_path"]).resolve()
    if root not in candidate_path.parents or root not in active_path.parents:
        raise RuntimeError("Model paths must stay inside persistent data storage.")
    candidate = _read(candidate_path)
    if not candidate or candidate.get("automatic_promotion") is True:
        raise RuntimeError("Invalid candidate document.")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    registry = root / "quality_retraining" / "registry"
    registry.mkdir(parents=True, exist_ok=True)
    backup = registry / f"champion_before_{stamp}.json"
    if active_path.is_file():
        shutil.copy2(active_path, backup)
    promoted = {
        **candidate,
        "registry_status": "ACTIVE_CHAMPION",
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "promotion_mode": "MANUAL_TWO_GATE",
        "automatic_promotion": False,
        "previous_champion_backup": str(backup) if backup.is_file() else "",
    }
    temporary = active_path.with_suffix(active_path.suffix + ".promotion.tmp")
    active_path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(json.dumps(promoted, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, active_path)
    event = {
        "event": "MANUAL_MODEL_PROMOTION",
        "at": promoted["promoted_at"],
        "candidate": str(candidate_path),
        "active": str(active_path),
        "active_sha256": _hash(active_path),
        "previous_backup": str(backup) if backup.is_file() else "",
    }
    with (registry / "promotion_audit.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return {"status": "PROMOTED_MANUALLY", **event}


def promote_candidate_automatically(
    expected_candidate_sha256: str,
    data_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Atomically promote an immutable candidate after every v7 safety gate.

    This entry point is intentionally separate from manual promotion.  It can
    only be called by the Autonomous Learning Governor and repeats the two
    statistical gates at the final write boundary to prevent TOCTOU errors.
    """
    enabled = os.getenv("BETBOT_AUTONOMOUS_PROMOTION_ENABLED", "0").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return {"status": "REFUSED_AUTONOMOUS_PROMOTION_DISABLED"}
    root = Path(data_dir or get_data_dir()).resolve()
    status = registry_status(root)
    candidate_path = Path(status["candidate_path"]).resolve()
    active_path = Path(status["active_path"]).resolve()
    if root not in candidate_path.parents or root not in active_path.parents:
        raise RuntimeError("Model paths must stay inside persistent data storage.")
    if not candidate_path.is_file() or _hash(candidate_path) != expected_candidate_sha256:
        return {"status": "REFUSED_CANDIDATE_CHANGED"}
    validation = status.get("candidate_validation", {})
    if validation.get("status") != "POSITIVE_VALIDATION_MANUAL_APPROVAL":
        return {"status": "REFUSED_WALK_FORWARD_NOT_POSITIVE"}
    if status.get("live_shadow", {}).get("status") != "POSITIVE_LIVE_SHADOW_MANUAL_APPROVAL":
        return {"status": "REFUSED_LIVE_SHADOW_NOT_POSITIVE"}

    candidate = _read(candidate_path)
    if not candidate or candidate.get("active_model_was_not_modified") is not True:
        return {"status": "REFUSED_INVALID_CANDIDATE"}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    registry = root / "quality_retraining" / "registry"
    registry.mkdir(parents=True, exist_ok=True)
    backup = registry / f"champion_before_auto_{stamp}.json"
    if active_path.is_file():
        shutil.copy2(active_path, backup)
    promoted_at = datetime.now(timezone.utc).isoformat()
    promoted = {
        **candidate,
        "registry_status": "ACTIVE_CHAMPION",
        "promoted_at": promoted_at,
        "promotion_mode": "AUTONOMOUS_V7_ALL_GATES",
        "automatic_promotion": True,
        "previous_champion_backup": str(backup) if backup.is_file() else "",
    }
    temporary = active_path.with_suffix(active_path.suffix + ".promotion.tmp")
    active_path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(json.dumps(promoted, ensure_ascii=False, indent=2), encoding="utf-8")
    with temporary.open("r+", encoding="utf-8") as handle:
        os.fsync(handle.fileno())
    os.replace(temporary, active_path)
    event = {
        "event": "AUTONOMOUS_MODEL_PROMOTION_V7",
        "at": promoted_at,
        "candidate": str(candidate_path),
        "candidate_sha256": expected_candidate_sha256,
        "active": str(active_path),
        "active_sha256": _hash(active_path),
        "previous_backup": str(backup) if backup.is_file() else "",
    }
    with (registry / "promotion_audit.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return {"status": "PROMOTED_AUTONOMOUSLY", **event}


def rollback_automatic_promotion(
    expected_active_sha256: str,
    backup_path: str | Path,
    reason: str,
    data_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Restore the previous champion only when both model identities match."""
    root = Path(data_dir or get_data_dir()).resolve()
    active_path = Path(os.getenv("BETBOT_QUALITY_STATE", root / "quality_shadow_state.json")).resolve()
    backup = Path(backup_path).resolve()
    registry = (root / "quality_retraining" / "registry").resolve()
    if root not in active_path.parents or registry not in backup.parents:
        raise RuntimeError("Rollback paths must stay inside the model registry.")
    if not active_path.is_file() or _hash(active_path) != expected_active_sha256:
        return {"status": "REFUSED_ACTIVE_MODEL_CHANGED"}
    if not backup.is_file():
        return {"status": "REFUSED_BACKUP_MISSING"}
    temporary = active_path.with_suffix(active_path.suffix + ".rollback.tmp")
    shutil.copy2(backup, temporary)
    os.replace(temporary, active_path)
    event = {
        "event": "AUTONOMOUS_MODEL_ROLLBACK_V7",
        "at": datetime.now(timezone.utc).isoformat(),
        "reason": str(reason)[:500],
        "restored_from": str(backup),
        "active": str(active_path),
        "active_sha256": _hash(active_path),
    }
    registry.mkdir(parents=True, exist_ok=True)
    with (registry / "promotion_audit.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return {"status": "ROLLED_BACK_AUTOMATICALLY", **event}
