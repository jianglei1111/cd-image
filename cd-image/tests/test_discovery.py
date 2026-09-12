"""Offline regression tests for unified model discovery and route preservation."""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "cd_image_cli.py"
SPEC = importlib.util.spec_from_file_location("cd_image_cli_discovery_tests", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)

FAKE_KEY = "sk-offline-discovery-test-only"


def response(status: int, payload: object) -> httpx.Response:
    return httpx.Response(status, json=payload)


class ModelDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        # Unexpected network traffic fails locally, including paid image calls.
        self.get = self.enterContext(patch.object(cli.httpx, "get"))
        self.post = self.enterContext(patch.object(cli.httpx, "post"))
        self.get.side_effect = AssertionError("Unexpected HTTP GET")
        self.post.side_effect = AssertionError("Unexpected HTTP POST")

    def discover(self) -> dict:
        return cli.discover_model_catalog(FAKE_KEY, timeout=7, retries=1)

    def assert_fallback_requests(self) -> None:
        self.assertEqual(self.get.call_count, 2)
        self.assertEqual(self.get.call_args_list[0].args, (cli.MODELS_URL,))
        self.assertEqual(
            self.get.call_args_list[0].kwargs,
            {"headers": {"Authorization": f"Bearer {FAKE_KEY}", "Accept": "application/json"}, "timeout": 7},
        )
        self.assertEqual(self.get.call_args_list[1].args, (cli.GEMINI_MODELS_URL,))
        self.assertEqual(
            self.get.call_args_list[1].kwargs,
            {"headers": {"x-goog-api-key": FAKE_KEY, "Accept": "application/json"}, "timeout": 7},
        )

    def test_unified_endpoint_accepts_openai_and_gemini_catalog_shapes(self) -> None:
        catalogs = (
            ({"data": [{"id": "gpt-image-2"}, {"id": "gpt-image-2"}, {"id": "gpt-5"}]}, ["gpt-image-2", "gpt-5"]),
            ({"models": [{"name": "models/gemini-3.1-flash-image"}]}, ["gemini-3.1-flash-image"]),
        )
        for payload, expected in catalogs:
            with self.subTest(payload=payload):
                self.get.reset_mock()
                self.get.side_effect = [response(200, payload)]
                result = self.discover()
                self.assertTrue(result["ok"])
                self.assertEqual(result["models"], expected)
                self.assertFalse(result["used_fallback"])
                self.assertEqual(result["discovery_endpoint"], cli.MODELS_URL)
                self.assertEqual(len(result["discovery"]), 1)
                self.assertTrue(result["discovery"][0]["ok"])
                self.get.assert_called_once_with(
                    cli.MODELS_URL,
                    headers={"Authorization": f"Bearer {FAKE_KEY}", "Accept": "application/json"},
                    timeout=7,
                )
        self.post.assert_not_called()

    def test_transport_failure_falls_back_and_keeps_original_diagnostic(self) -> None:
        self.get.side_effect = [
            httpx.ConnectError("connection interrupted"),
            response(200, {"models": [{"name": "models/gemini-3.1-flash-image"}]}),
        ]
        result = self.discover()
        self.assertTrue(result["ok"])
        self.assertTrue(result["used_fallback"])
        self.assertEqual(result["discovery_endpoint"], cli.GEMINI_MODELS_URL)
        self.assertEqual(result["models"], ["gemini-3.1-flash-image"])
        self.assertIn("connection interrupted", result["discovery"][0]["error"])
        self.assertFalse(result["discovery"][0]["ok"])
        self.assertTrue(result["discovery"][1]["ok"])
        self.assert_fallback_requests()

    def test_both_http_failures_remain_distinguishable_and_redact_echoed_key(self) -> None:
        self.get.side_effect = [
            response(403, {"error": {"message": f"OpenAI access denied for {FAKE_KEY}"}}),
            response(400, {"error": {"message": f"Gemini platform mismatch for {FAKE_KEY}"}}),
        ]
        result = self.discover()
        self.assertFalse(result["ok"])
        self.assertEqual(result["models"], [])
        self.assertIsNone(result["discovery_endpoint"])
        self.assertEqual([source["http_status"] for source in result["discovery"]], [403, 400])
        self.assertIn("OpenAI access denied", result["discovery"][0]["error"])
        self.assertIn("Gemini platform mismatch", result["discovery"][1]["error"])
        self.assertNotIn(FAKE_KEY, json.dumps(result))
        self.assertIn("[REDACTED]", json.dumps(result))
        self.assert_fallback_requests()

    def test_network_error_echoing_key_is_redacted_when_fallback_succeeds(self) -> None:
        self.get.side_effect = [
            httpx.ConnectError(f"proxy rejected credential {FAKE_KEY}"),
            response(200, {"models": [{"name": "models/gemini-3.1-flash-image"}]}),
        ]
        result = self.discover()
        self.assertTrue(result["ok"])
        self.assertNotIn(FAKE_KEY, json.dumps(result))
        self.assertIn("[REDACTED]", result["discovery"][0]["error"])

    def test_empty_malformed_and_non_json_catalogs_allow_native_fallback(self) -> None:
        invalid_catalogs = (
            (response(200, {"data": []}), "no model IDs"),
            (response(200, {"data": [{"id": None}, {}, "not-a-model"]}), "no model IDs"),
            (response(200, ["unexpected", "shape"]), "no model IDs"),
            (httpx.Response(200, text="<html>gateway maintenance</html>"), "invalid JSON"),
        )
        for invalid_response, error_fragment in invalid_catalogs:
            with self.subTest(error=error_fragment, body=invalid_response.text):
                self.get.reset_mock()
                self.get.side_effect = [
                    invalid_response,
                    response(200, {"models": [{"name": "models/gemini-3-pro-image"}]}),
                ]
                result = self.discover()
                self.assertTrue(result["ok"])
                self.assertTrue(result["used_fallback"])
                self.assertEqual(result["models"], ["gemini-3-pro-image"])
                self.assertIn(error_fragment, result["discovery"][0]["error"])
                self.assertEqual(result["discovery"][0]["http_status"], 200)
                self.assert_fallback_requests()

    def test_legacy_discover_models_returns_list(self) -> None:
        self.get.side_effect = [response(200, {"data": [{"id": "gpt-image-2"}]})]
        self.assertEqual(cli.discover_models(FAKE_KEY, 7, 1), ["gpt-image-2"])

    def test_legacy_discover_models_raises_with_both_endpoint_errors(self) -> None:
        self.get.side_effect = [
            response(401, {"error": "unified unauthorized"}),
            response(400, {"error": "native incompatible"}),
        ]
        with self.assertRaises(cli.CDImageError) as caught:
            cli.discover_models(FAKE_KEY, 7, 1)
        self.assertIn("unified unauthorized", str(caught.exception))
        self.assertIn("native incompatible", str(caught.exception))

    def run_models(self) -> tuple[int, dict]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = cli.run_models(argparse.Namespace(timeout=7, retries=1, channel="auto"), FAKE_KEY)
        return exit_code, json.loads(output.getvalue())

    def test_models_command_keeps_text_only_catalog_without_selecting_image_model(self) -> None:
        self.get.side_effect = [response(200, {"data": [{"id": "gpt-5"}, {"id": "text-embedding-3-small"}]})]
        exit_code, result = self.run_models()
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertEqual(result["models"], ["gpt-5", "text-embedding-3-small"])
        self.assertEqual(result["image_models"], {"gemini": [], "image2": []})
        self.assertIsNone(result["selected_model"])
        self.assertIsNone(result["selected_channel"])
        self.assertIn("No supported", result["selection_error"])
        self.assertFalse(result["generation_access_verified"])
        self.assertEqual(self.get.call_count, 1)
        self.post.assert_not_called()

    def test_models_command_reports_structured_failure_and_nonzero_status(self) -> None:
        self.get.side_effect = [
            response(401, {"error": f"unified unauthorized {FAKE_KEY}"}),
            response(400, {"error": "native platform mismatch"}),
        ]
        exit_code, result = self.run_models()
        self.assertEqual(exit_code, 1)
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["discovery"]), 2)
        self.assertIn("unified unauthorized", result["error"])
        self.assertIn("native platform mismatch", result["error"])
        self.assertNotIn(FAKE_KEY, json.dumps(result))
        self.post.assert_not_called()

    def test_models_command_selection_is_not_generation_access_verification(self) -> None:
        self.get.side_effect = [response(200, {"data": [{"id": "gpt-image-2"}]})]
        exit_code, result = self.run_models()
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["selected_model"], "gpt-image-2")
        self.assertEqual(result["selected_channel"], "image2")
        self.assertFalse(result["generation_access_verified"])
        self.post.assert_not_called()

    def test_openai_generation_failure_does_not_switch_endpoint_or_model(self) -> None:
        self.get.side_effect = [response(200, {"data": [{"id": "gpt-image-2"}, {"id": "gemini-3.1-flash-image"}]})]
        self.post.side_effect = [response(403, {"error": "image generation unavailable"})]
        args = argparse.Namespace(
            command="generate", count=1, model="auto", channel="auto", timeout=7,
            retries=1, prompt="offline route test", size="4K", aspect_ratio="9:16",
            quality="high", response_format="auto",
        )
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(cli.CDImageError) as caught:
            cli.run_request(args, FAKE_KEY)
        self.assertEqual(caught.exception.status, 403)
        self.get.assert_called_once()
        self.post.assert_called_once_with(
            f"{cli.BASE_URL}/v1/images/generations",
            headers={"Authorization": f"Bearer {FAKE_KEY}", "Accept": "application/json", "Content-Type": "application/json"},
            json={"model": "gpt-image-2", "prompt": "offline route test", "size": "2160x3840", "quality": "high", "n": 1},
            timeout=7,
        )

    def test_explicit_model_skips_catalog_and_uses_inferred_channel(self) -> None:
        # Explicit selection must work even when both model-list endpoints are
        # unavailable; the selected model is sent directly to its channel.
        self.get.side_effect = AssertionError("model discovery must be skipped")
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            cli, "request_image2", return_value=("image/png", b"png-bytes", {"sent_size": "1024x1024"}, 1)
        ) as request:
            args = argparse.Namespace(
                command="generate", count=1, model="gpt-image-2", channel="auto", timeout=7,
                retries=1, prompt="explicit route", size="1K", aspect_ratio="1:1",
                quality="high", response_format="auto", output_dir=tmp, output=None,
                slug="explicit-route",
            )
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = cli.run_request(args, FAKE_KEY)
            self.assertEqual(exit_code, 0)
            request.assert_called_once()
            self.get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
