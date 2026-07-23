"""Production process supervisor — Architecture Hardening v8.1.

Importing this module has no side effects.  Quality Governance is the single
owner of controlled retraining; the legacy retraining loop is not launched.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from typing import Any

from runtime_health_v81 import (
    RUNTIME_SCHEMA,
    atomic_json,
    quality_health_path,
    read_json,
    runtime_health_path,
    utc_now,
)
from server_start_guard import run_server_start_guard_once
from settings_v81 import RuntimeSettings, load_settings


def build_process_specs(settings: RuntimeSettings | None = None) -> dict[str, list[str]]:
    config = settings or load_settings()
    python = sys.executable or "python3"
    specs = {
        "scheduler": [python, "scheduler_engine.py"],
        "live_pipeline": [python, "live_pipeline_runtime.py"],
        "settlement": [python, "settle_loop.py"],
        "persistence": [python, "persistence_runtime.py"],
        "quality_governance_v8": [python, "quality_governance_v8_loop.py"],
        "dashboard": [
            python, "-m", "streamlit", "run", "dashboard_streamlit.py",
            "--server.port", str(config.port),
            "--server.address", "0.0.0.0",
            "--server.headless", "true",
        ],
    }
    if config.volleyball_enabled:
        specs["volleyball_shadow"] = [python, "-m", "volleyball_v9.runtime"]
    return specs


class ProcessSupervisor:
    def __init__(self, settings: RuntimeSettings) -> None:
        self.settings = settings
        self.specs = build_process_specs(settings)
        self.processes: dict[str, subprocess.Popen[str]] = {}
        self.metadata: dict[str, dict[str, Any]] = {
            name: {"restart_count": 0, "last_started_at": None, "last_exit_code": None}
            for name in self.specs
        }
        self.started_at = utc_now()
        self.health_path = runtime_health_path()
        self.quality_path = quality_health_path()

    @staticmethod
    def _stream_output(process: subprocess.Popen[str], prefix: str) -> None:
        try:
            if process.stdout is None:
                return
            for line in iter(process.stdout.readline, ""):
                if line:
                    print(f"{prefix} {line.strip()}", flush=True)
        except Exception as exc:
            print(f"{prefix} OUTPUT STREAM ERROR: {exc}", flush=True)

    def start_process(self, name: str, command: list[str], *, restart: bool = False) -> subprocess.Popen[str]:
        print(f"START {name}: {' '.join(command)}", flush=True)
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        threading.Thread(
            target=self._stream_output,
            args=(process, f"[{name.upper()}]"),
            daemon=True,
        ).start()
        info = self.metadata[name]
        info["last_started_at"] = utc_now()
        if restart:
            info["restart_count"] = int(info.get("restart_count", 0)) + 1
        print(f"{name} STARTED pid={process.pid}", flush=True)
        return process

    def start_all(self) -> None:
        for name, command in self.specs.items():
            self.processes[name] = self.start_process(name, command)

    def tick(self) -> dict[str, bool]:
        states: dict[str, bool] = {}
        for name, command in self.specs.items():
            process = self.processes.get(name)
            alive = process is not None and process.poll() is None
            if not alive:
                exit_code = None if process is None else process.poll()
                self.metadata[name]["last_exit_code"] = exit_code
                print(f"{name} CRASHED exit={exit_code} -> RESTART", flush=True)
                self.processes[name] = self.start_process(name, command, restart=True)
                alive = True
            states[name] = alive
        return states

    def write_health(self, states: dict[str, bool]) -> dict[str, Any]:
        quality = read_json(self.quality_path)
        process_details = {
            name: {
                "alive": bool(states.get(name)),
                "pid": self.processes[name].pid if name in self.processes else None,
                **self.metadata[name],
            }
            for name in self.specs
        }
        payload = {
            "schema_version": RUNTIME_SCHEMA,
            "generated_at": utc_now(),
            "supervisor_started_at": self.started_at,
            "supervisor_pid": os.getpid(),
            "configuration_fingerprint": self.settings.fingerprint(),
            "all_required_processes_alive": all(states.values()),
            "single_retraining_owner": "quality_governance_v8",
            "legacy_retraining_process_started": False,
            "processes": process_details,
            "quality_governance": quality,
            "financial_execution": {
                "betting_enabled": self.settings.betting_enabled,
                "capital_real_enabled": self.settings.capital_real_enabled,
                "volleyball_execution_enabled": False,
            },
            "sports": {
                "football": {"enabled": True, "storage": "existing"},
                "volleyball": {
                    "enabled": self.settings.volleyball_enabled,
                    "shadow_only": self.settings.volleyball_shadow_only,
                    "storage": "isolated",
                },
            },
            "contains_secrets": False,
            "source_history_modified": False,
        }
        atomic_json(self.health_path, payload)
        return payload

    def shutdown(self) -> None:
        print("SHUTDOWN START", flush=True)
        for name, process in list(self.processes.items()):
            try:
                print(f"TERMINATE {name}", flush=True)
                process.terminate()
            except Exception:
                pass
        print("SHUTDOWN COMPLETE", flush=True)


def main() -> int:
    settings = load_settings()
    print("APP LAUNCHER v10.0 START", flush=True)
    print(
        f"CONFIG VALID schema={settings.schema_version} fingerprint={settings.fingerprint()}",
        flush=True,
    )
    run_server_start_guard_once()
    supervisor = ProcessSupervisor(settings)

    def stop(*_: object) -> None:
        supervisor.shutdown()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    supervisor.start_all()
    while True:
        try:
            states = supervisor.tick()
            supervisor.write_health(states)
            state_text = " | ".join(f"{name}={alive}" for name, alive in states.items())
            print(f"HEARTBEAT v10.0 | {state_text}", flush=True)
            time.sleep(settings.heartbeat_seconds)
        except Exception as exc:
            print(f"APP LAUNCHER ERROR: {exc}", flush=True)
            time.sleep(15)


if __name__ == "__main__":
    raise SystemExit(main())
