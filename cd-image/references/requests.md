# Request schema, delivery and versioned edits

Requests are UTF-8 JSON. Only documented fields are accepted; credentials and HTTP state IDs do not belong here. The Agent prepares the content; users normally speak naturally.

## Fields

| Field | Meaning/default |
|---|---|
| original_prompt / prompt | Original brief and submitted prompt, both required |
| optimization | mode auto/raw, profile photo/product/text-heavy/diagram/illustration/general |
| optimization.exact_text | Literal strings that must survive into the submitted prompt |
| optimization.must_keep / must_avoid / notes | Lists recording constraints and assumptions |
| operation | generate/edit; inferred from source if absent |
| api | images/responses/auto; Agent may choose explicitly |
| routing_reason | Brief reason; no transport secrets |
| model | Image model, default Sunburst |
| responses_model | Independent main model, default gpt-5.6-sol |
| quality | high by default |
| size | Upstream WIDTHxHEIGHT or auto; new default 2048x2048; edit inherits source if valid |
| stream / partial_images | true / 0 by default; previews 0–3 only when streaming |
| source_image | One local edit image; absolute or relative to request file |
| source_version | latest or actual ID from selected session; exclusive with source_image |
| mask | Optional local alpha mask matching source dimensions and format |
| delivery | Local output requirements, separately recorded from requested API size |

Do not include n, api_key, previous_response_id or arbitrary provider fields. The default model IDs are configuration, not a permanent allowed-model list. Explicit user-selected alternative IDs are passed through; unsupported models fail visibly.

## Example: landscape, 2K minimum long edge

~~~json
{
  "original_prompt": "一只猫在窗边晒太阳，横图，2K",
  "prompt": "A natural photograph of a cat resting in sunlight beside a window. Calm everyday setting, believable fur texture and soft daylight, clean landscape composition.",
  "optimization": {
    "mode": "auto",
    "profile": "photo",
    "exact_text": [],
    "must_keep": ["cat", "window", "sunlight"],
    "must_avoid": [],
    "notes": ["Added photographic clarity without inventing extra subjects."]
  },
  "operation": "generate",
  "api": "images",
  "routing_reason": "Single photograph after local prompt refinement.",
  "size": "2048x1152",
  "delivery": {"mode": "long_edge", "long_edge": 2048}
}
~~~

This requests a landscape canvas but only promises local long-edge delivery. If 16:9 is a firm requirement, use exact mode.

## Example: edit the last delivery

~~~json
{
  "original_prompt": "只把杯子改成蓝色，其他不变",
  "prompt": "Edit the supplied image: change only the mug to cobalt blue. Preserve the exact black text \"K7M-42\", the mug shape and right-side handle, the yellow cube, navy notebook, their positions, the background and lighting. Add no objects or text.",
  "optimization": {
    "mode": "auto",
    "profile": "product",
    "exact_text": ["K7M-42"],
    "must_keep": ["mug shape", "right-side handle", "yellow cube", "navy notebook", "composition"],
    "must_avoid": ["extra text", "extra objects"],
    "notes": ["Inherited accepted details from the selected image."]
  },
  "operation": "edit",
  "api": "responses",
  "routing_reason": "Preserve the selected source while changing one property.",
  "source_version": "latest"
}
~~~

Use the same --output-dir/--session as the preceding result. Omitting size/delivery inherits the delivered image, not the previous nominal request. Replace source_version with source_image for an imported image.

Inspect the selected image and read relevant history. A hash mismatch rejects an altered version file rather than silently editing different content; explicitly select the modified file as source_image when intended.

## Delivery options

- Only “2K”: {"mode":"long_edge","long_edge":2048}. Increase the long edge only if below the target, preserve ratio; do not shrink a larger original.
- Exact canvas: {"mode":"exact","size":"2048x1152","fit":"pad","background":"white"}. Padding preserves the full image. Background can be transparent or a Pillow color such as #f3f3ef.
- Crop to fill: {"mode":"exact","size":"2048x1152","fit":"crop"}. Center-crop after proportional scaling; use only when required content remains visible. For an off-center crop, prepare a deliberate separate local edit instead of assuming center crop preserves the subject.
- Native/no local resizing: {"mode":"original"}.

Processed output is PNG; original bytes stay intact. Alpha is preserved when possible. The client never stretches a mismatched ratio.

For backward compatibility, explicit API size without a delivery object uses exact delivery to that size (padding if needed). New Agent-authored “2K” requests should explicitly use long_edge. With no explicit size/source, delivery defaults to long_edge 2048. With an edit source and no new size, delivery defaults to source dimensions.

Delivery sizes may differ from legal upstream sizes. A resized 2048x1365 source is locally valid; the next edit requests upstream size=auto because 1365 is not a multiple of 16, then restores 2048x1365 for delivery. Masks must match that actual source, not a rounded surrogate.

## Masks and source copies

Source and mask must share dimensions/format; mask alpha must include a transparent editable region. Create/inspect the mask against the exact selected source. Both APIs transmit the original source and mask; the mask remains guidance, not a guaranteed pixel-exact boundary.

Each run snapshots input-source and input-mask with hashes. If the source already contains local padding/cropping, build the mask on that version. Do not silently reuse a mask for a different canvas.

## Session and result files

--output-dir contains unique run folders and session.json by default. --session can point to an existing task's manifest independently of the output folder.

A run contains request.json, wire-request.json (large image data replaced with hashes), compact events.json, result.json, original images, optional previews, optional local deliveries, and input snapshots. Agent visual findings go in qa.json.

session.json records version IDs, original/delivery paths, delivery hashes, parent version, prompts, constraints and delivery operations. current_version points to the latest successfully completed single-image delivery. Select any earlier ID to branch without overwriting history. The user's most recent visual choice overrides automatic latest selection.

A live session owns session.json.lock. Concurrent mutation fails before another HTTP call. After interruption, inspect the process and run result before clearing a confirmed stale lock. Timeout does not mean the server did not produce or bill an image.

The session references local files; moving output folders manually requires updating paths. Raw response IDs are diagnostic metadata only.
