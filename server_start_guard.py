"""Production pre-start guard. Does not alter source history files."""
from __future__ import annotations

import os
from typing import Any

from server_data_guard import prepare_server_data_backup
from storage_paths import require_persistent_storage_on_server


def run_server_start_guard_once() -> dict[str, Any]:
    if os.getenv("KANIBAL_SERVER_GUARD_DONE", "").strip() == "1":
        return {"status": "ALREADY_VERIFIED_IN_PROCESS"}
    require_persistent_storage_on_server()
    result = prepare_server_data_backup()
    os.environ["KANIBAL_SERVER_GUARD_DONE"] = "1"
    print(f"SERVER DATA GUARD: {result}", flush=True)
    return result


if __name__ == "__main__":
    run_server_start_guard_once()
