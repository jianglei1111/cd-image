---
name: cd-image
description: Generate or edit images through the fixed CD gateway by discovering the image models available to a user-provided key and routing automatically to either the Gemini-native or Image2/OpenAI-compatible channel. Use for CD image generation, editing, model discovery, or when the key's image group is unknown.
---

# CD-image

Use `scripts/cd_image_cli.py`. The gateway is fixed at
`https://sp.chedankj.com`; never change it based on prompt content.

## Key And Routing

Require a user-provided image-group key. Never write the key to a file, prompt,
log, command-line argument, or test report. Pass it only through an environment
variable for the current command:

```powershell
$env:CD_IMAGE_API_KEY="sk-..."
```

The client queries `GET /v1/models` and selects an image model exposed to that
key. It then routes by model family:

- `gemini-*-image` -> Gemini-native
  `POST /v1beta/models/{model}:generateContent`
- `gpt-image-*` -> Image2/OpenAI-compatible
  `POST /v1/images/generations` or `POST /v1/images/edits`

Keep `--model auto --channel auto` unless the user explicitly requests a model
or channel. Use the `models` command for a no-generation discovery check. Never
silently retry a failed request on a different model or channel: that could use a
different price, capability, or upstream group.

## Workflow

1. Improve a rough image request into a concise production prompt unless the
   user says the prompt is exact.
2. Use `generate` for text-to-image. Use `edit` when one or more local reference
   images are supplied; Image2 accepts one input while Gemini accepts multiple.
3. Use `2K` for normal final work and `1K` for quick checks. Choose the requested
   aspect ratio. The client converts tiers to valid Image2 pixel sizes when that
   channel is selected.
4. `--quality` applies only to Image2. Use `high` for final work.
5. Use `--timeout 600` for generation and run the shell command with at least an
   11-minute timeout. Wait for concrete script output and confirm the file exists.

Install the only dependency if needed:

```powershell
python -m pip install httpx
```

## Commands

Discover models and the automatic route:

```powershell
python <skill_dir>\scripts\cd_image_cli.py models
```

Generate with automatic routing:

```powershell
python <skill_dir>\scripts\cd_image_cli.py generate "final prompt" --size 2K --aspect-ratio 1:1 --quality high --slug final-image --timeout 600
```

Edit with automatic routing:

```powershell
python <skill_dir>\scripts\cd_image_cli.py edit "edit instruction" --input .\source.png --size 2K --aspect-ratio 1:1 --quality high --slug edited-image --timeout 600
```

Force a model or channel only when requested:

```powershell
python <skill_dir>\scripts\cd_image_cli.py generate "final prompt" --model gemini-3.1-flash-image --channel gemini --size 2K --aspect-ratio 2:3 --timeout 600
```

`--size` accepts `1K`, `2K`, `4K`, or `WIDTHxHEIGHT`. Explicit pixel sizes are
for Image2 only and must satisfy all of these constraints: both dimensions are
multiples of 16, long edge at most 3840, aspect ratio at most 3:1, and total
pixels from 655,360 through 8,294,400.

## Failure Handling

- No discovered image model: the key is assigned to a non-image group or the
  group's model configuration is incomplete.
- `400`: report the validation message and check model-specific size parameters.
- `401` or `403`: the key is invalid, disabled, or lacks group permission.
- `429`: the selected channel is rate limited or out of quota.
- `500`, `502`, `503`, `504`, `522`, or `524`: the gateway or selected upstream
  account is unavailable or timed out. The client retries transient statuses.
- A successful HTTP response without a usable image is a failure. Report the
  model text, finish reason, or response-shape error printed by the client.

Always report the selected model, selected channel, and final saved path.
