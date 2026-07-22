"""Cross-process cache and pacing for API-Football pre-match odds."""
from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def _float_env(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return max(minimum, default)


def _runtime_dir() -> Path:
    configured = os.getenv("PERSISTENT_DATA_DIR", "").strip()
    root = Path(configured) if configured else Path(tempfile.gettempdir())
    path = root / "runtime_cache" / "api_football"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


@contextmanager
def _file_lock(path: Path, timeout_seconds: float = 60.0):
    started = time.monotonic()
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(descriptor, f"{os.getpid()} {time.time()}".encode("ascii"))
        except FileExistsError:
            try:
                if time.time() - path.stat().st_mtime > 90:
                    path.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            if time.monotonic() - started >= timeout_seconds:
                raise TimeoutError(f"Timeout waiting for API request lock: {path}")
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            if descriptor is not None:
                os.close(descriptor)
        finally:
            path.unlink(missing_ok=True)


def _rate_limited(payload: dict[str, Any]) -> bool:
    errors = payload.get("errors")
    if isinstance(errors, dict):
        text = " ".join(f"{key} {value}" for key, value in errors.items())
    else:
        text = str(errors or "")
    normalized = text.lower().replace("_", " ")
    return "ratelimit" in normalized.replace(" ", "") or "too many requests" in normalized


def _cached_result(fixture_id: str, now: float) -> dict[str, Any] | None:
    runtime = _runtime_dir()
    cache_path = runtime / "odds_cache.json"
    ttl = _float_env("API_FOOTBALL_ODDS_CACHE_SECONDS", 240.0, 0.0)
    with _file_lock(runtime / "cache.lock"):
        cache = _read_json(cache_path)
        entry = cache.get(str(fixture_id))
        if not isinstance(entry, dict):
            return None
        stored_at = float(entry.get("stored_at", 0.0) or 0.0)
        if ttl <= 0 or now - stored_at > ttl:
            return None
        payload = entry.get("payload")
        if not isinstance(payload, dict):
            return None
        return {
            "payload": payload,
            "observed_at": str(entry.get("observed_at") or ""),
            "cached": True,
            "status_code": int(entry.get("status_code", 200) or 200),
            "rate_limited": False,
        }


def _store_cache(fixture_id: str, result: dict[str, Any], now: float) -> None:
    runtime = _runtime_dir()
    cache_path = runtime / "odds_cache.json"
    ttl = _float_env("API_FOOTBALL_ODDS_CACHE_SECONDS", 240.0, 0.0)
    with _file_lock(runtime / "cache.lock"):
        cache = _read_json(cache_path)
        for key, entry in list(cache.items()):
            try:
                expired = now - float(entry.get("stored_at", 0.0)) > max(60.0, ttl * 2)
            except Exception:
                expired = True
            if expired:
                cache.pop(key, None)
        cache[str(fixture_id)] = {
            "stored_at": now,
            "observed_at": result["observed_at"],
            "status_code": result["status_code"],
            "payload": result["payload"],
        }
        _write_json_atomic(cache_path, cache)


def fetch_fixture_odds(
    fixture_id: str | int,
    url: str,
    headers: dict[str, str],
    requester: Callable[..., Any],
) -> dict[str, Any]:
    """Fetch odds once per cache window and pace all local processes together."""
    fixture_key = str(fixture_id)
    now = time.time()
    cached = _cached_result(fixture_key, now)
    if cached is not None:
        return cached

    runtime = _runtime_dir()
    with _file_lock(runtime / "request.lock"):
        now = time.time()
        cached = _cached_result(fixture_key, now)
        if cached is not None:
            return cached

        state_path = runtime / "request_state.json"
        state = _read_json(state_path)
        min_interval = _float_env(
            "API_FOOTBALL_ODDS_MIN_INTERVAL_SECONDS", 2.5, 0.0
        )
        allowed_at = max(
            float(state.get("last_request_at", 0.0) or 0.0) + min_interval,
            float(state.get("blocked_until", 0.0) or 0.0),
        )
        if allowed_at > now:
            time.sleep(allowed_at - now)

        response = requester(
            url,
            headers=headers,
            params={"fixture": fixture_key},
            timeout=25,
        )
        completed_at = time.time()
        try:
            payload = response.json()
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}

        limited = _rate_limited(payload) or int(getattr(response, "status_code", 0)) == 429
        state["last_request_at"] = completed_at
        if limited:
            cooldown = _float_env(
                "API_FOOTBALL_RATE_LIMIT_COOLDOWN_SECONDS", 65.0, 0.0
            )
            state["blocked_until"] = completed_at + cooldown
        else:
            state["blocked_until"] = 0.0
        _write_json_atomic(state_path, state)

        result = {
            "payload": payload,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "cached": False,
            "status_code": int(getattr(response, "status_code", 0) or 0),
            "rate_limited": limited,
        }
        if not limited and not payload.get("errors"):
            _store_cache(fixture_key, result, completed_at)
        return result

