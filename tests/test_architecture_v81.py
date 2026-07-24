from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import app_launcher
import scheduler_engine
import persistence_runtime
from quality_governance_v8_loop import run_cycle
from runtime_health_v81 import RUNTIME_SCHEMA, atomic_json, read_json
from settings_v81 import ConfigurationError, load_settings


class SettingsV81Tests(unittest.TestCase):
    def test_safe_defaults_and_secret_free_snapshot(self):
        settings = load_settings({})
        self.assertFalse(settings.betting_enabled)
        self.assertFalse(settings.capital_real_enabled)
        serialized = json.dumps(settings.public_snapshot()).lower()
        self.assertNotIn("password", serialized)
        self.assertNotIn("api_key", serialized)
        self.assertEqual(len(settings.fingerprint()), 64)

    def test_real_betting_without_capital_opt_in_fails_startup(self):
        with self.assertRaises(ConfigurationError):
            load_settings({"BETTING_ENABLED": "true", "BETBOT_CAPITAL_REAL_ENABLED": "0"})

    def test_invalid_numeric_value_fails_startup(self):
        with self.assertRaises(ConfigurationError):
            load_settings({"BETBOT_GOVERNOR_CHECK_MINUTES": "fast"})


class SingleOwnerArchitectureTests(unittest.TestCase):
    def test_launcher_has_one_quality_retraining_owner(self):
        specs = app_launcher.build_process_specs(load_settings({}))
        commands = [" ".join(command) for command in specs.values()]
        self.assertIn("autonomous_quality_v11", specs)
        self.assertNotIn("retraining", specs)
        self.assertFalse(any("auto_retraining_loop.py" in command for command in commands))
        self.assertEqual(sum("quality_governance_v8_loop.py" in command for command in commands), 1)

    def test_scheduler_does_not_run_owned_background_pipelines(self):
        scheduler_source = Path(scheduler_engine.__file__).read_text(encoding="utf-8")
        self.assertNotIn("run_live_pipeline_once()", scheduler_source)
        self.assertNotIn("persistence_run_once()", scheduler_source)
        self.assertNotIn("AutoRetrainingRuntime()", scheduler_source)

    def test_persistence_does_not_duplicate_settlement_owner(self):
        persistence_source = Path(persistence_runtime.__file__).read_text(encoding="utf-8")
        self.assertNotIn("settle_stored_picks()", persistence_source)

    def test_quality_cycle_has_one_orchestrator_owner(self):
        calls = []

        class Orchestrator:
            def run(self):
                calls.append("orchestrator")
                return {"status": "HEALTHY", "phase": "COLLECTING_QUALITY_DATA"}

        result = run_cycle(Orchestrator())
        self.assertEqual(calls, ["orchestrator"])
        self.assertEqual(result["status"], "HEALTHY")


class RuntimeHealthContractTests(unittest.TestCase):
    def test_atomic_versioned_runtime_health(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "runtime_health.json"
            payload = {
                "schema_version": RUNTIME_SCHEMA,
                "generated_at": "2026-07-23T00:00:00+00:00",
                "contains_secrets": False,
                "source_history_modified": False,
            }
            atomic_json(path, payload)
            self.assertEqual(read_json(path), payload)
            self.assertFalse(path.with_suffix(".json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
