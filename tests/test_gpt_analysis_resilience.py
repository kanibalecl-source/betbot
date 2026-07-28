from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import gpt_match_value_engine as engine


def valid_analysis_json() -> str:
    return json.dumps(
        {
            "decision": "WATCH",
            "confidence": 72,
            "value_score": 5.5,
            "risk": "medium",
            "quality_score": 8,
            "main_reason": "Dane są obiecujące, ale niepełne.",
            "summary": "Wymagana ponowna kontrola składów.",
            "analysis": {
                "najwazniejsze_dane": "Dane A-H.",
                "forma": "Forma stabilna.",
                "styl_matchup": "Dopasowanie neutralne.",
                "liga_rozgrywki": "Liga o średniej zmienności.",
                "kontuzje_kadra": "Brak potwierdzonych braków.",
                "motywacja_atmosfera": "Motywacja wysoka.",
                "value_kurs": "Value umiarkowane.",
                "argumenty_za": "Forma gospodarzy.",
                "argumenty_przeciw": "Niepełne składy.",
                "ryzyka": "Rotacja.",
                "dopasowanie_profilu": "Profil główny.",
                "alternatywa": "Brak.",
                "rekomendacja": "Obserwować.",
                "zrodla": "https://example.test",
            },
        },
        ensure_ascii=False,
    )


class FakeResponse:
    def __init__(self, output_text: str, request_id: str = "req_test") -> None:
        self.output_text = output_text
        self.status = "completed"
        self._request_id = request_id


class FakeResponses:
    def __init__(self, outcomes) -> None:
        self.outcomes = list(outcomes)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def fake_openai_module(responses: FakeResponses):
    module = types.ModuleType("openai")

    class OpenAI:
        def __init__(self, **kwargs) -> None:
            self.responses = responses

    module.OpenAI = OpenAI
    return module


class GptAnalysisResilienceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.item = {
            "profile": "model_ai",
            "match": "A vs B",
            "bet": "Over 1.5",
            "odds": "2.10",
            "league": "Test League",
            "time": "2026-07-28T20:00:00+02:00",
        }
        self.env = {
            "OPENAI_API_KEY": "test-key-not-a-secret",
            "GPT_ANALYSIS_MODEL": "gpt-5.6-terra",
            "GPT_ANALYSIS_FALLBACK_MODEL": "gpt-4.1-mini",
        }

    def test_parse_failure_retries_and_structured_output_is_used(self) -> None:
        responses = FakeResponses(
            [
                FakeResponse('{"decision": WATCH}'),
                FakeResponse(valid_analysis_json()),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, self.env, clear=False
        ), patch.dict(
            sys.modules, {"openai": fake_openai_module(responses)}
        ):
            result = engine.analyze_match_with_gpt(Path(tmp), self.item)

        self.assertEqual(result["execution_status"], "success")
        self.assertEqual(result["provider_attempt"], "primary_without_search")
        self.assertEqual(len(responses.calls), 2)
        first, second = responses.calls
        self.assertEqual(first["tools"], [{"type": "web_search"}])
        self.assertNotIn("tools", second)
        self.assertEqual(
            first["text"]["format"]["type"],
            "json_schema",
        )
        self.assertTrue(first["text"]["format"]["strict"])

    def test_failure_is_not_cached_and_next_click_retries(self) -> None:
        responses = FakeResponses(
            [
                FakeResponse("not-json"),
                FakeResponse("still-not-json"),
                FakeResponse("also-not-json"),
                FakeResponse(valid_analysis_json()),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, self.env, clear=False
        ), patch.dict(
            sys.modules, {"openai": fake_openai_module(responses)}
        ):
            root = Path(tmp)
            with self.assertRaises(engine.GPTAnalysisError):
                engine.analyze_match_with_gpt(root, self.item)
            self.assertEqual(list((root / engine.CACHE_DIR).glob("*.json")), [])

            result = engine.analyze_match_with_gpt(root, self.item)

        self.assertEqual(result["execution_status"], "success")
        self.assertEqual(len(responses.calls), 4)

    def test_only_success_is_reused_from_cache(self) -> None:
        responses = FakeResponses([FakeResponse(valid_analysis_json())])
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, self.env, clear=False
        ), patch.dict(
            sys.modules, {"openai": fake_openai_module(responses)}
        ):
            root = Path(tmp)
            first = engine.analyze_match_with_gpt(root, self.item)
            second = engine.analyze_match_with_gpt(root, self.item)

        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])
        self.assertEqual(len(responses.calls), 1)

    def test_cache_identity_changes_with_odds_and_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, self.env, clear=False
        ):
            root = Path(tmp)
            first = engine._cache_path(root, self.item, model="gpt-5.6-terra")
            changed_odds = dict(self.item, odds="2.20")
            second = engine._cache_path(
                root, changed_odds, model="gpt-5.6-terra"
            )
            third = engine._cache_path(
                root, self.item, model="gpt-4.1-mini"
            )

        self.assertNotEqual(first, second)
        self.assertNotEqual(first, third)

    def test_missing_key_is_visible_and_not_cached(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "",
                "GPT_ANALYSIS_MODEL": "gpt-5.6-terra",
            },
            clear=False,
        ):
            root = Path(tmp)
            with self.assertRaisesRegex(
                engine.GPTAnalysisError, "OPENAI_API_KEY"
            ):
                engine.analyze_match_with_gpt(root, self.item)
            self.assertFalse((root / engine.CACHE_DIR).exists())


if __name__ == "__main__":
    unittest.main()
