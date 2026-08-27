# CD-image

Codex skill for image generation and editing through the fixed CD gateway. It
discovers the image models available to the current API key and routes each
request to the matching API automatically:

- Gemini image models use the Gemini-native `generateContent` endpoint.
- GPT Image models use the Image2/OpenAI-compatible image endpoints.

## Install

Download [`CD-image.zip`](https://github.com/jianglei1111/cd-image/raw/refs/heads/main/CD-image.zip),
then drag it into a Codex conversation and ask Codex to install it. After
installation, invoke it as `$cd-image`.

## Key

Pass the key through `CD_IMAGE_API_KEY` for the current command. Keys are not
stored in the skill or repository.

```powershell
$env:CD_IMAGE_API_KEY="sk-..."
python .\cd-image\scripts\cd_image_cli.py models
```

## Generate

```powershell
python .\cd-image\scripts\cd_image_cli.py generate "a polished product photograph" --size 2K --aspect-ratio 1:1 --quality high --timeout 600
```

The command prints the discovered model, selected channel, and saved output
path. Pass `--model` or `--channel` only when a manual override is needed.
