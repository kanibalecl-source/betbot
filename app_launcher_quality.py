"""Add controlled QUALITY retraining without modifying the production launcher."""
from __future__ import annotations

import os
import runpy
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def _enabled() -> bool:
    return os.getenv("BETBOT_QUALITY_RETRAIN_ENABLED", "0").strip().lower() in {
        "1", "true", "yes", "on"
    }


def main() -> None:
    quality_process: subprocess.Popen[str] | None = None
    if _enabled():
        quality_process = subprocess.Popen(
            [sys.executable, "-u", str(BASE_DIR / "quality_auto_retraining_loop.py")],
            cwd=str(BASE_DIR),
        )
        print(
            f"QUALITY RETRAINING PROCESS STARTED pid={quality_process.pid} "
            "auto_promotion=false",
            flush=True,
        )
    else:
        print("QUALITY RETRAINING DISABLED", flush=True)
    try:
        runpy.run_path(str(BASE_DIR / "app_launcher.py"), run_name="__main__")
    finally:
        if quality_process is not None and quality_process.poll() is None:
            quality_process.terminate()
            try:
                quality_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                quality_process.kill()


if __name__ == "__main__":
    main()
