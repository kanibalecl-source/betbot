from __future__ import annotations

import os
from pathlib import Path


def load_local_env(path: str | Path = ".env.local") -> dict[str, str]:
    """Load simple KEY=VALUE pairs for local-only runs.

    This intentionally does not touch Railway or any remote environment. Values
    are applied only to the current local process and inherited by child
    processes started from the local launcher.
    """
    env_path = Path(path)
    loaded: dict[str, str] = {}
    if not env_path.exists():
        return loaded

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ[key] = value
            loaded[key] = value
    return loaded

