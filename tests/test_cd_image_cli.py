from __future__ import annotations

import importlib.util
import argparse
import base64
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "cd-image" / "scripts" / "cd_image_cli.py"
SPEC = importlib.util.spec_from_file_location("cd_image_cli", SCRIPT)
assert SPEC and SPEC.loader
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)


class ModelRoutingTests(unittest.TestCase):
    def test_parse_openai_model_list(self) -> None:
        data = {"data": [{"id": "gpt-image-2"}, {"id": "gemini-3.1-flash-image"}]}
        self.assertEqual(cli.parse_model_ids(data), ["gpt-image-2", "gemini-3.1-flash-image"])

    def test_parse_gemini_model_list(self) -> None:
        data = {"models": [{"name": "models/gemini-3-pro-image"}]}
        self.assertEqual(cli.parse_model_ids(data), ["gemini-3-pro-image"])

    def test_model_discovery_merges_formats_and_ignores_invalid_items(self) -> None:
        data = {
            "data": [{"id": "models/gpt-image-2.5-sunburst"}, {"id": ""}, None],
            "models": [{"name": "models/gpt-image-2.5-sunburst"},
                       {"name": "models/gemini-3-pro-image"}, {"name": 1}],
        }
        self.assertEqual(cli.parse_model_ids(data), ["gpt-image-2.5-sunburst", "gemini-3-pro-image"])

    def test_generation_defaults_are_preserved(self) -> None:
        with patch("sys.argv", ["cd_image_cli.py", "generate", "test prompt"]):
            args = cli.parse_args()
        self.assertEqual((args.model, args.channel), ("auto", "auto"))
        self.assertEqual((args.size, args.aspect_ratio, args.quality, args.count), ("2K", "1:1", "high", 1))

    def test_auto_routes_gemini_only_key(self) -> None:
        self.assertEqual(
            cli.resolve_model(["gemini-3-pro-image"], "auto", "auto"),
            ("gemini-3-pro-image", "gemini"),
        )

    def test_auto_routes_image2_only_key(self) -> None:
        self.assertEqual(
            cli.resolve_model(["gpt-image-2"], "auto", "auto"),
            ("gpt-image-2", "image2"),
        )

    def test_image2_prefers_25_sunburst_when_available(self) -> None:
        models = ["gpt-image-2", "gpt-image-2.5-sunburst", "gpt-image-1"]
        self.assertEqual(
            cli.resolve_model(models, "auto", "image2"),
            ("gpt-image-2.5-sunburst", "image2"),
        )

    def test_image2_preference_is_case_insensitive(self) -> None:
        self.assertEqual(
            cli.resolve_model(["GPT-IMAGE-2.5-SUNBURST"], "auto", "image2"),
            ("GPT-IMAGE-2.5-SUNBURST", "image2"),
        )

    def test_auto_prefers_image2_when_both_are_exposed(self) -> None:
        models = ["gemini-3.1-flash-image", "gpt-image-2"]
        self.assertEqual(cli.resolve_model(models, "auto", "auto"), ("gpt-image-2", "image2"))

    def test_channel_override_selects_matching_family(self) -> None:
        models = ["gemini-3.1-flash-image", "gpt-image-2"]
        self.assertEqual(
            cli.resolve_model(models, "auto", "gemini"),
            ("gemini-3.1-flash-image", "gemini"),
        )

    def test_model_channel_mismatch_is_rejected(self) -> None:
        with self.assertRaises(cli.CDImageError):
            cli.resolve_model([], "gpt-image-2", "gemini")


class SizeRoutingTests(unittest.TestCase):
    def test_image2_tier_conversion(self) -> None:
        self.assertEqual(cli.image2_size("2K", "2:3"), "1344x2016")
        self.assertEqual(cli.image2_size("4K", "16:9"), "3840x2160")

    def test_valid_custom_size(self) -> None:
        self.assertEqual(cli.validate_image2_size("2048x1152"), (2048, 1152))

    def test_invalid_custom_size(self) -> None:
        with self.assertRaises(cli.CDImageError):
            cli.validate_image2_size("4096x2160")


class FakeResponse:
    def __init__(self, data: dict, content: bytes = b"") -> None:
        self.status_code = 200
        self._data = data
        self.content = content
        self.headers: dict[str, str] = {}
        self.reason_phrase = "OK"
        self.text = ""

    def json(self) -> dict:
        return self._data


class EndpointRoutingTests(unittest.TestCase):
    def request_args(self, command: str = "generate") -> argparse.Namespace:
        return argparse.Namespace(
            command=command,
            prompt="test prompt",
            size="1K",
            aspect_ratio="1:1",
            quality="high",
            response_format="auto",
            timeout=30,
            retries=1,
            input=[],
        )

    def test_image2_generation_uses_openai_compatible_endpoint(self) -> None:
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
        response = FakeResponse({"data": [{"b64_json": base64.b64encode(png).decode("ascii")}]})
        with patch.object(cli.httpx, "post", return_value=response) as post:
            mime_type, image, metadata, _ = cli.request_image2(self.request_args(), "secret", "gpt-image-2")
        self.assertEqual(mime_type, "image/png")
        self.assertEqual(image, png)
        self.assertEqual(post.call_args.args[0], f"{cli.BASE_URL}/v1/images/generations")
        self.assertEqual(post.call_args.kwargs["json"]["size"], "1024x1024")
        self.assertEqual(metadata["sent_size"], "1024x1024")

    def test_image25_generation_keeps_high_quality_and_existing_size_mapping(self) -> None:
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
        response = FakeResponse({"data": [{"b64_json": base64.b64encode(png).decode("ascii")}]})
        args = self.request_args()
        args.size = "2K"
        with patch.object(cli.httpx, "post", return_value=response) as post:
            cli.request_image2(args, "secret", "gpt-image-2.5-sunburst")
        self.assertEqual(post.call_args.args[0], f"{cli.BASE_URL}/v1/images/generations")
        payload = post.call_args.kwargs["json"]
        self.assertEqual((payload["model"], payload["quality"], payload["size"]),
                         ("gpt-image-2.5-sunburst", "high", "2048x2048"))

    def test_gemini_generation_uses_generate_content_endpoint(self) -> None:
        jpeg = b"\xff\xd8\xff" + b"\x00" * 24
        response = FakeResponse({
            "candidates": [{
                "content": {"parts": [{
                    "inlineData": {
                        "mimeType": "image/jpeg",
                        "data": base64.b64encode(jpeg).decode("ascii"),
                    }
                }]}
            }]
        })
        with patch.object(cli.httpx, "post", return_value=response) as post:
            mime_type, image, _, _ = cli.request_gemini(
                self.request_args(), "secret", "gemini-3.1-flash-image"
            )
        self.assertEqual(mime_type, "image/jpeg")
        self.assertEqual(image, jpeg)
        self.assertEqual(
            post.call_args.args[0],
            f"{cli.BASE_URL}/v1beta/models/gemini-3.1-flash-image:generateContent",
        )


if __name__ == "__main__":
    unittest.main()
