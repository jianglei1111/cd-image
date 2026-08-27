#!/usr/bin/env python3
"""Discover a CD image key's models and route requests to Gemini or Image2."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import struct
import sys
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - exercised on fresh systems
    httpx = None


BASE_URL = "https://sp.chedankj.com"
MODELS_URL = f"{BASE_URL}/v1/models"
DEFAULT_TIMEOUT = 600
TRANSIENT_STATUSES = {408, 429, 500, 502, 503, 504, 522, 524}
VALID_CHANNELS = ("auto", "gemini", "image2")
VALID_TIERS = ("1K", "2K", "4K")
VALID_ASPECT_RATIOS = (
    "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"
)
GEMINI_PREFERENCES = (
    "gemini-3.1-flash-image",
    "gemini-3-pro-image",
    "gemini-2.5-flash-image",
)
IMAGE2_PREFERENCES = (
    "gpt-image-2",
    "gpt-image-1.5",
    "gpt-image-1",
)
# Prefer Image2 only when a key genuinely exposes both channel families.
CHANNEL_PREFERENCES = ("image2", "gemini")
MIME_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
IMAGE2_TIER_SIZES = {
    "1K": {
        "1:1": "1024x1024", "2:3": "1024x1536", "3:2": "1536x1024",
        "3:4": "768x1024", "4:3": "1024x768", "4:5": "832x1040",
        "5:4": "1040x832", "9:16": "720x1280", "16:9": "1280x720",
        "21:9": "1344x576",
    },
    "2K": {
        "1:1": "2048x2048", "2:3": "1344x2016", "3:2": "2016x1344",
        "3:4": "1536x2048", "4:3": "2048x1536", "4:5": "1600x2000",
        "5:4": "2000x1600", "9:16": "1152x2048", "16:9": "2048x1152",
        "21:9": "2016x864",
    },
    "4K": {
        "1:1": "2880x2880", "2:3": "2304x3456", "3:2": "3456x2304",
        "3:4": "2448x3264", "4:3": "3264x2448", "4:5": "2560x3200",
        "5:4": "3200x2560", "9:16": "2160x3840", "16:9": "3840x2160",
        "21:9": "3808x1632",
    },
}


class CDImageError(Exception):
    def __init__(self, message: str, status: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status = status
        self.body = body


def normalize_size(value: str) -> str:
    value = value.strip()
    tier = value.upper()
    if tier in VALID_TIERS:
        return tier
    match = re.fullmatch(r"(\d+)[xX](\d+)", value)
    if not match:
        raise argparse.ArgumentTypeError("size must be 1K, 2K, 4K, or WIDTHxHEIGHT")
    return f"{int(match.group(1))}x{int(match.group(2))}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CD image auto-routing client")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_network_options(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
        subparser.add_argument("--retries", type=int, default=3)

    models = subparsers.add_parser("models", help="Discover image models and automatic route")
    models.add_argument("--channel", choices=VALID_CHANNELS, default="auto")
    add_network_options(models)

    def add_request_options(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("prompt", help="Image prompt or edit instruction")
        subparser.add_argument("--model", default="auto")
        subparser.add_argument("--channel", choices=VALID_CHANNELS, default="auto")
        subparser.add_argument("--size", type=normalize_size, default="2K")
        subparser.add_argument("--aspect-ratio", choices=VALID_ASPECT_RATIOS, default="1:1")
        subparser.add_argument("--quality", choices=("low", "medium", "high", "auto"), default="high")
        subparser.add_argument("--count", "-n", type=int, default=1)
        subparser.add_argument("--output", default=None)
        subparser.add_argument("--output-dir", default=".")
        subparser.add_argument("--slug", default=None)
        subparser.add_argument("--response-format", choices=("auto", "b64_json", "url"), default="auto")
        add_network_options(subparser)

    generate = subparsers.add_parser("generate", help="Generate an image")
    add_request_options(generate)

    edit = subparsers.add_parser("edit", help="Edit one or more reference images")
    add_request_options(edit)
    edit.add_argument("--input", action="append", required=True)
    return parser.parse_args()


def require_httpx() -> None:
    if httpx is None:
        raise CDImageError("Missing dependency: httpx. Install it with: python -m pip install httpx")


def get_api_key() -> str:
    key = (
        os.environ.get("CD_IMAGE_API_KEY")
        or os.environ.get("IMAGE2_API_KEY")
        or os.environ.get("BANANA_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    if not key:
        raise CDImageError("Missing API key. Set CD_IMAGE_API_KEY for the current command.")
    return key


def auth_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "x-goog-api-key": api_key,
        "Accept": "application/json",
    }


def parse_error_message(raw: str) -> str:
    if not raw:
        return ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw[:800]
    error = data.get("error") if isinstance(data, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or error.get("status") or error.get("code") or "")
    if isinstance(error, str):
        return error
    return raw[:800]


def request_with_retries(
    request: Callable[[], Any], retries: int, label: str
) -> tuple[Any, int]:
    attempts = max(1, retries)
    started = time.monotonic()
    for attempt in range(1, attempts + 1):
        try:
            response = request()
        except httpx.RequestError as exc:
            if attempt < attempts:
                delay = min(2 ** (attempt - 1), 8)
                print(f"[cd-image] {label} network error; retrying {attempt}/{attempts} in {delay}s", flush=True)
                time.sleep(delay)
                continue
            raise CDImageError(f"{label} network error after {attempts} attempts: {exc}") from exc

        if response.status_code == 200:
            return response, int((time.monotonic() - started) * 1000)
        if response.status_code in TRANSIENT_STATUSES and attempt < attempts:
            retry_after = response.headers.get("retry-after", "").strip()
            delay = int(retry_after) if retry_after.isdigit() else min(2 ** (attempt - 1), 8)
            print(f"[cd-image] {label} HTTP {response.status_code}; retrying {attempt}/{attempts} in {delay}s", flush=True)
            time.sleep(delay)
            continue
        message = parse_error_message(response.text) or response.reason_phrase
        raise CDImageError(
            f"{label} HTTP {response.status_code}: {message}",
            status=response.status_code,
            body=response.text[:2000],
        )
    raise CDImageError(f"{label} failed after retries")


def parse_model_ids(data: dict[str, Any]) -> list[str]:
    models: list[str] = []
    openai_items = data.get("data")
    if isinstance(openai_items, list):
        for item in openai_items:
            model_id = item.get("id") if isinstance(item, dict) else None
            if isinstance(model_id, str) and model_id.strip():
                models.append(model_id.removeprefix("models/").strip())
    gemini_items = data.get("models")
    if isinstance(gemini_items, list):
        for item in gemini_items:
            name = item.get("name") if isinstance(item, dict) else None
            if isinstance(name, str) and name.strip():
                models.append(name.removeprefix("models/").strip())
    return list(dict.fromkeys(models))


def discover_models(api_key: str, timeout: int, retries: int) -> list[str]:
    headers = auth_headers(api_key)
    response, _ = request_with_retries(
        lambda: httpx.get(MODELS_URL, headers=headers, timeout=timeout),
        retries,
        "model discovery",
    )
    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise CDImageError("Model discovery returned invalid JSON", status=200) from exc
    models = parse_model_ids(data if isinstance(data, dict) else {})
    if not models:
        raise CDImageError("Model discovery returned no model IDs", status=200)
    return models


def model_channel(model: str) -> str | None:
    normalized = model.removeprefix("models/").lower()
    if normalized.startswith("gemini-") and "image" in normalized:
        return "gemini"
    if normalized.startswith("gpt-image-"):
        return "image2"
    return None


def image_models_by_channel(models: list[str]) -> dict[str, list[str]]:
    grouped = {"gemini": [], "image2": []}
    for model in models:
        channel = model_channel(model)
        if channel:
            grouped[channel].append(model.removeprefix("models/"))
    return grouped


def preferred_model(models: list[str], channel: str) -> str:
    grouped = image_models_by_channel(models)
    candidates = grouped[channel]
    if not candidates:
        raise CDImageError(f"No {channel} image model is available for this API key")
    preferences = IMAGE2_PREFERENCES if channel == "image2" else GEMINI_PREFERENCES
    by_lower = {model.lower(): model for model in candidates}
    for preference in preferences:
        if preference in by_lower:
            return by_lower[preference]
    return sorted(candidates, key=str.casefold)[-1]


def resolve_model(models: list[str], requested_model: str, requested_channel: str) -> tuple[str, str]:
    model = requested_model.removeprefix("models/").strip()
    if model and model.lower() != "auto":
        inferred = model_channel(model)
        if inferred is None:
            raise CDImageError(f"Cannot infer an image channel from model: {model}")
        if requested_channel != "auto" and requested_channel != inferred:
            raise CDImageError(f"Model {model} requires channel {inferred}, not {requested_channel}")
        return model, inferred

    if requested_channel != "auto":
        return preferred_model(models, requested_channel), requested_channel
    grouped = image_models_by_channel(models)
    for channel in CHANNEL_PREFERENCES:
        if grouped[channel]:
            return preferred_model(models, channel), channel
    available = ", ".join(models[:16])
    raise CDImageError(f"No supported Gemini or GPT image model is available (models: {available})")


def image2_size(size: str, aspect_ratio: str) -> str:
    if size in VALID_TIERS:
        return IMAGE2_TIER_SIZES[size][aspect_ratio]
    validate_image2_size(size)
    return size


def validate_image2_size(size: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d+)x(\d+)", size)
    if not match:
        raise CDImageError(f"Invalid Image2 size: {size}")
    width, height = int(match.group(1)), int(match.group(2))
    pixels = width * height
    if width % 16 or height % 16:
        raise CDImageError("Image2 width and height must both be multiples of 16")
    if max(width, height) > 3840:
        raise CDImageError("Image2 long edge must not exceed 3840 pixels")
    if max(width, height) / min(width, height) > 3:
        raise CDImageError("Image2 aspect ratio must not exceed 3:1")
    if not 655_360 <= pixels <= 8_294_400:
        raise CDImageError("Image2 total pixels must be between 655360 and 8294400")
    return width, height


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return re.sub(r"-{2,}", "-", value).strip("-")[:60] or "cd-image-output"


def read_input(raw_path: str) -> tuple[Path, str, bytes]:
    path = Path(raw_path).expanduser().resolve()
    if not path.is_file():
        raise CDImageError(f"Input image does not exist or is not a file: {path}")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise CDImageError(f"Failed to read input image {path}: {exc}") from exc
    if not data:
        raise CDImageError(f"Input image is empty: {path}")
    return path, detect_mime_type(data, path.name), data


def detect_mime_type(data: bytes, filename: str = "") -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    guessed, _ = mimetypes.guess_type(filename)
    if guessed in MIME_EXTENSIONS:
        return str(guessed)
    raise CDImageError(f"Unsupported image type: {filename or 'response data'}")


def output_path(args: argparse.Namespace, index: int, mime_type: str) -> Path:
    extension = MIME_EXTENSIONS.get(mime_type, ".bin")
    count = max(1, args.count)
    if args.output:
        base = Path(args.output).expanduser()
        if base.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            base = base.with_suffix(extension)
        elif not base.suffix:
            base = base.with_suffix(extension)
    else:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        base = Path(args.output_dir).expanduser() / f"{slugify(args.slug or args.prompt)}-{stamp}{extension}"
    if count > 1:
        base = base.with_name(f"{base.stem}-{index}{base.suffix}")
    path = base.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def image_dimensions(data: bytes, mime_type: str) -> tuple[int | None, int | None]:
    if mime_type == "image/png" and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if mime_type == "image/jpeg" and data.startswith(b"\xff\xd8"):
        offset = 2
        sof = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
        while offset + 9 < len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            marker = data[offset + 1]
            offset += 2
            if marker in {0xD8, 0xD9}:
                continue
            length = int.from_bytes(data[offset:offset + 2], "big")
            if marker in sof:
                return (
                    int.from_bytes(data[offset + 5:offset + 7], "big"),
                    int.from_bytes(data[offset + 3:offset + 5], "big"),
                )
            if length < 2:
                break
            offset += length
    return None, None


def gemini_payload(prompt: str, size: str, aspect_ratio: str, inputs: list[str]) -> dict[str, Any]:
    if size not in VALID_TIERS:
        raise CDImageError("Gemini size must be 1K, 2K, or 4K; pixel sizes are Image2-only")
    parts: list[dict[str, Any]] = [{"text": prompt}]
    for raw_path in inputs:
        _, mime_type, data = read_input(raw_path)
        parts.append({
            "inlineData": {
                "mimeType": mime_type,
                "data": base64.b64encode(data).decode("ascii"),
            }
        })
    return {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"imageSize": size, "aspectRatio": aspect_ratio},
        },
    }


def extract_gemini_image(data: dict[str, Any]) -> tuple[str, bytes, list[str], dict[str, Any]]:
    if isinstance(data.get("response"), dict):
        data = data["response"]
    images: list[tuple[str, str]] = []
    texts: list[str] = []
    finish_reasons: list[str] = []
    candidates = data.get("candidates")
    if isinstance(candidates, list):
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            finish_reason = candidate.get("finishReason") or candidate.get("finish_reason")
            if finish_reason:
                finish_reasons.append(str(finish_reason))
            content = candidate.get("content")
            if not isinstance(content, dict):
                continue
            parts = content.get("parts")
            if not isinstance(parts, list):
                continue
            for part in parts:
                if not isinstance(part, dict) or part.get("thought") is True:
                    continue
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    texts.append(text.strip())
                inline = part.get("inlineData") or part.get("inline_data")
                if isinstance(inline, dict) and isinstance(inline.get("data"), str):
                    mime_type = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                    images.append((str(mime_type), inline["data"]))
    if not images:
        details = []
        if texts:
            details.append("model text: " + " ".join(texts)[:500])
        if finish_reasons:
            details.append("finish reason: " + ", ".join(finish_reasons))
        raise CDImageError("Gemini response contained no image: " + ("; ".join(details) or "no inlineData"))
    mime_type, encoded = max(images, key=lambda item: len(item[1]))
    try:
        image = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise CDImageError(f"Gemini returned invalid base64 image data: {exc}") from exc
    if not image:
        raise CDImageError("Gemini returned an empty image")
    usage = data.get("usageMetadata")
    return mime_type, image, texts, usage if isinstance(usage, dict) else {}


def request_gemini(
    args: argparse.Namespace, api_key: str, model: str
) -> tuple[str, bytes, dict[str, Any], int]:
    inputs = getattr(args, "input", None) or []
    payload = gemini_payload(args.prompt, args.size, args.aspect_ratio, inputs)
    url = f"{BASE_URL}/v1beta/models/{quote(model, safe='')}:generateContent"
    headers = auth_headers(api_key)
    headers["Content-Type"] = "application/json"
    response, duration_ms = request_with_retries(
        lambda: httpx.post(url, headers=headers, json=payload, timeout=args.timeout),
        args.retries,
        "Gemini request",
    )
    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise CDImageError("Gemini returned invalid JSON", status=200) from exc
    mime_type, image, texts, usage = extract_gemini_image(data)
    return mime_type, image, {"model_text": "\n".join(texts), "usage": usage}, duration_ms


def extract_image2_item(
    item: dict[str, Any], timeout: int, retries: int
) -> tuple[str, bytes]:
    encoded = item.get("b64_json")
    if isinstance(encoded, str) and encoded:
        try:
            image = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise CDImageError(f"Image2 returned invalid base64 image data: {exc}") from exc
        return detect_mime_type(image), image
    image_url = item.get("url")
    if isinstance(image_url, str) and image_url:
        response, _ = request_with_retries(
            lambda: httpx.get(image_url, follow_redirects=True, timeout=timeout),
            retries,
            "image download",
        )
        if not response.content:
            raise CDImageError("Image2 image URL returned an empty response")
        return detect_mime_type(response.content, image_url), response.content
    raise CDImageError("Image2 response item contains neither b64_json nor url")


def request_image2(
    args: argparse.Namespace, api_key: str, model: str
) -> tuple[str, bytes, dict[str, Any], int]:
    size = image2_size(args.size, args.aspect_ratio)
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    if args.command == "generate":
        headers["Content-Type"] = "application/json"
        payload: dict[str, Any] = {
            "model": model,
            "prompt": args.prompt,
            "size": size,
            "quality": args.quality,
            "n": 1,
        }
        if args.response_format != "auto":
            payload["response_format"] = args.response_format

        def request():
            return httpx.post(
                f"{BASE_URL}/v1/images/generations",
                headers=headers,
                json=payload,
                timeout=args.timeout,
            )
    else:
        inputs = args.input or []
        if len(inputs) != 1:
            raise CDImageError("Image2 edit accepts exactly one --input image; Gemini supports multiple inputs")
        path, mime_type, _ = read_input(inputs[0])

        def request():
            with path.open("rb") as image_file:
                files = {"image": (path.name, image_file, mime_type)}
                data: dict[str, Any] = {
                    "model": model,
                    "prompt": args.prompt,
                    "size": size,
                    "quality": args.quality,
                }
                if args.response_format != "auto":
                    data["response_format"] = args.response_format
                return httpx.post(
                    f"{BASE_URL}/v1/images/edits",
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=args.timeout,
                )

    response, duration_ms = request_with_retries(request, args.retries, "Image2 request")
    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise CDImageError("Image2 returned invalid JSON", status=200) from exc
    items = data.get("data") if isinstance(data, dict) else None
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        raise CDImageError("Image2 response does not contain image data")
    mime_type, image = extract_image2_item(items[0], args.timeout, args.retries)
    return mime_type, image, {
        "revised_prompt": items[0].get("revised_prompt", ""),
        "sent_size": size,
    }, duration_ms


def run_models(args: argparse.Namespace, api_key: str) -> int:
    models = discover_models(api_key, args.timeout, args.retries)
    grouped = image_models_by_channel(models)
    selected_model, selected_channel = resolve_model(models, "auto", args.channel)
    result = {
        "ok": True,
        "image_models": grouped,
        "selected_model": selected_model,
        "selected_channel": selected_channel,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


def run_request(args: argparse.Namespace, api_key: str) -> int:
    if args.count < 1:
        raise CDImageError("count must be at least 1")
    models = discover_models(api_key, args.timeout, args.retries)
    model, channel = resolve_model(models, args.model, args.channel)
    if args.model.lower() != "auto" and model not in models:
        print("[cd-image] warning: forced model is not present in the key's discovered model list", flush=True)
    print(f"[cd-image] selected model={model} channel={channel}", flush=True)
    print(f"[cd-image] starting mode={args.command} size={args.size} aspect_ratio={args.aspect_ratio}", flush=True)
    results: list[dict[str, Any]] = []
    for index in range(1, args.count + 1):
        if channel == "gemini":
            mime_type, image, metadata, duration_ms = request_gemini(args, api_key, model)
        else:
            mime_type, image, metadata, duration_ms = request_image2(args, api_key, model)
        if not image:
            raise CDImageError("Selected channel returned an empty image")
        path = output_path(args, index, mime_type)
        try:
            path.write_bytes(image)
        except OSError as exc:
            raise CDImageError(f"Failed to save image to {path}: {exc}") from exc
        width, height = image_dimensions(image, mime_type)
        result = {
            "path": str(path),
            "mime_type": mime_type,
            "bytes": len(image),
            "width": width,
            "height": height,
            "duration_ms": duration_ms,
        }
        result.update(metadata)
        sent_size = metadata.get("sent_size")
        if isinstance(sent_size, str):
            expected_width, expected_height = validate_image2_size(sent_size)
            result["resolution_match"] = width == expected_width and height == expected_height
            if not result["resolution_match"]:
                print(
                    f"[cd-image] warning: Image2 requested {sent_size} but returned {width}x{height}",
                    flush=True,
                )
        results.append(result)
        print(f"[cd-image] saved {index}/{args.count}: {path} ({width}x{height}, {len(image)} bytes)", flush=True)
    summary = {
        "ok": True,
        "mode": args.command,
        "model": model,
        "channel": channel,
        "requested_size": args.size,
        "aspect_ratio": args.aspect_ratio,
        "outputs": results,
    }
    print("[cd-image] OK", flush=True)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


def main() -> int:
    args = parse_args()
    try:
        require_httpx()
        api_key = get_api_key()
        if args.command == "models":
            return run_models(args, api_key)
        return run_request(args, api_key)
    except CDImageError as exc:
        prefix = f"[cd-image] ERROR HTTP {exc.status}" if exc.status else "[cd-image] ERROR"
        print(f"{prefix}: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
