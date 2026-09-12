---
name: cd-image
description: Generate or edit images through the CD relay with model discovery, automatic Gemini/Image2 routing, prompt optimization guidance, local references, and labelled sizing.
---

# CD-image

Use `scripts/cd_image_cli.py` for the command-line workflow. The gateway is fixed at `https://sp.chedankj.com`; do not change it based on prompt content.

## User-selected model and credentials

For a new request, first show the model menu and ask the user to choose one model (or provide an exact model ID). After the model is selected, ask the user to send the image-group API key. Then pass the selected model explicitly to the CLI and generate or edit. Explicit selection skips model discovery, so a broken catalog endpoint does not block the chosen model. Never silently switch model or channel after an API error.

Available image models (availability depends on the supplied key):

- **Gemini** — `gemini-3.1-flash-image`, `gemini-3-pro-image`, `gemini-2.5-flash-image`
- **OpenAI Images** — `gpt-image-2.5-sunburst`, `gpt-image-2`, `gpt-image-1.5`, `gpt-image-1`

Require a user-provided image-group key. Never write the key to a file, prompt, history, log, command-line argument, or test report. Pass it through an environment variable for the current process:

```powershell
$env:CD_IMAGE_API_KEY="sk-..."
```

The optional `models` command queries `GET /v1/models` and reports the image models exposed to that key. Use it only when the user explicitly asks to inspect a key's catalog. Automatic routing remains available when the user selects `auto`:

- `gemini-*-image` uses Gemini `POST /v1beta/models/{model}:generateContent`.
- `gpt-image-*` uses Image2/OpenAI-compatible `POST /v1/images/generations` or `POST /v1/images/edits`.

When Image2 is selected, `gpt-image-2.5-sunburst` is preferred when the key actually exposes it, followed by `gpt-image-2`, `gpt-image-1.5`, and `gpt-image-1`. Gemini preferences remain unchanged. If both channel families are available, Image2 remains the automatic channel preference. A forced model or channel is never silently replaced after a failure.

Keep `--model auto --channel auto` unless the user explicitly requests a model or channel. Use `models` for discovery without generation.

## Prompt and operation guidance

The agent should prepare a concise production prompt once before invoking the client. Read [prompt-optimization.md](references/prompt-optimization.md) for the common pass and profiles. Preserve complete prompts, exact labels, named entities, and user language; resolve only real ambiguity. For a verbatim request, pass the text unchanged. For edits, describe the requested change and repeat invariants that must survive. Do not require approval for routine prompt clarification.

Use `generate` for text-to-image. Use `edit` with one or more local references; Image2 accepts exactly one input while Gemini accepts multiple. Masks, multi-turn history, Responses routing, and delivery-size decisions are covered by [requests.md](references/requests.md). Protocol and compatibility details are in [channel.md](references/channel.md).

## Size and quality defaults

The CLI defaults to one image, `2K`, square `1:1`, and Image2 quality `high`. Use `1K` for quick checks and `2K` for normal final work; request `4K` only when needed. The client converts tiers to valid Image2 pixel sizes. Explicit Image2 sizes must use multiples of 16, have a long edge no greater than 3840, an aspect ratio no greater than 3:1, and 655,360–8,294,400 total pixels.

`--quality` applies only to Image2. Gemini accepts tier sizes (`1K`, `2K`, `4K`) rather than explicit pixel dimensions.

## Commands

Discover models and the automatic route:

```powershell
python <skill_dir>\scripts\cd_image_cli.py models
```

Generate:

```powershell
python <skill_dir>\scripts\cd_image_cli.py generate "prepared prompt" --size 2K --aspect-ratio 1:1 --quality high --slug final-image --timeout 600
```

Edit:

```powershell
python <skill_dir>\scripts\cd_image_cli.py edit "edit instruction" --input .\source.png --size 2K --aspect-ratio 1:1 --quality high --slug edited-image --timeout 600
```

Force a route only when requested:

```powershell
python <skill_dir>\scripts\cd_image_cli.py generate "prepared prompt" --model gemini-3.1-flash-image --channel gemini --size 2K --aspect-ratio 2:3 --timeout 600
```

Run generation with a process timeout of at least 11 minutes when using the default 600-second request timeout. Confirm the saved file exists and report the selected model, channel, and final path.

## Failure handling and verification

The client retries transient network and gateway statuses, but never switches models or channels automatically. Report validation (`400`), authorization (`401`/`403`), quota (`429`), and gateway (`5xx`/`52x`) failures clearly. A successful HTTP response without usable image bytes is still a failure.

Install the only runtime dependency if needed:

```powershell
python -m pip install httpx
```

Run offline tests from the repository root:

```powershell
python -B -m unittest discover -s tests -p "test_*.py"
```
