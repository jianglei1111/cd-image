# CD relay protocol and compatibility

Default site: https://www.chedankj.com/ . The client accepts site-root or /v1 configuration and appends exactly one /v1. Do not replace it with sp.chedankj.com, a BananaHub service, or a direct ChatGPT internal endpoint unless the user explicitly changes the destination.

Config stores an empty api_key and names IMAGE2_API_KEY as its environment source. A nonempty key in config is rejected to keep distributable files credential-free.

## Wire formats

Images generation: POST /v1/images/generations, JSON with image model, prompt, size, quality, output_format=png, n=1, stream, and partial_images for streaming.

Images edits: POST /v1/images/edits, multipart image[] plus optional mask; the same image controls are form fields. Let the HTTP library set the multipart boundary.

Responses: POST /v1/responses. Top-level model defaults to gpt-5.6-sol; tools[0] is image_generation with model=gpt-image-2.5-sunburst, action=generate/edit and image controls. Input text and an optional source image data URL are sent together. A mask data URL is tools[0].input_image_mask.image_url. tool_choice selects image_generation; store=false. An instruction requests exactly one image.

Do not send max_tool_calls on this relay path: it was rejected. A textual one-image instruction is not a hard server-side tool-call limit; preserve unexpected additional images and report them. Do not send previous_response_id: local source replay implements editing.

Headers: Bearer relay key; Accept is text/event-stream or application/json. JSON Content-Type/multipart boundary comes from the HTTP library. No ChatGPT cookies, account tokens or fabricated browser headers.

## Controls

Request dimensions must be multiples of 16, maximum edge 3840, maximum ratio 3:1, total pixels 655360–8294400; auto is accepted. These are request limits, not a guarantee of actual output dimensions.

Quality supports low, medium, high, xhigh, max, auto for the 2.5 models; default high. Advanced levels require explicit selection, and acceptance does not prove they were honored. The known gpt-image-2 model rejects local xhigh/max validation. Explicit alternative model IDs are passed through, not silently remapped by the client.

stream defaults true; partial_images defaults zero, permitted range 0–3. Fewer previews than requested is not necessarily failure. Only completed decoded images count as output.

## Result interpretation

Keep these separate:
- requested: image model, Responses main model, size, quality.
- response: main model, response ID/status/store.
- tool_metadata: returned image tool configuration.
- image_metadata: completed image call/event, quality, size, revised_prompt.
- images: dimensions and SHA-256 computed from original returned bytes.
- deliveries: local resizing/padding/crop result, or the unchanged original path.
- usage: relay-reported usage; not a verified billing statement.

Responses output_item.done may contain a valid image before response.completed. Save the bytes but continue reading until completion/error; a later error or interrupted stream is not reported as a complete successful response. Images completion events can terminate an open stream immediately. Both API JSON and named/multiline SSE forms are handled. Repeated image bytes in final events are deduplicated.

Original images/previews are saved without transcoding. Do not fetch URL-only outputs automatically. Persist compact events, request IDs and status during execution so an interrupted task can inspect existing work.

## Dated observations: 2026-09-11

The user's CD account group was tested with Sunburst:
- Images and Responses generation, nonstream generation, streaming previews, image edits and masked request forms produced images.
- gpt-5.5 and, after the group was updated, gpt-6-astra worked as Responses main models.
- gpt-5.6-sol also completed a live source-image edit through this client. It returned 1536x1024 and final quality low despite requesting high; the client retained the original and created a 2048x1365 Lanczos delivery.
- Responses commonly reported image tool gpt-image-2-codex/auto and completed image quality medium or low; requested 2048x1152 frequently became 1536x1024.
- Images sometimes delivered exact requested dimensions and sometimes did not; stream=true alone does not explain the mismatch.
- store=true was returned as false. HTTP previous_response_id was rejected with: "previous_response_id requires an OpenAI API-key account for HTTP requests".
- Responses max_tool_calls was rejected. Three corrected requests omitting it succeeded.
- Both masked forms completed the intended edit; mask enforcement was not isolated from explicit text instructions, so no pixel-exact guarantee is warranted.

The observations concern one relay/group/time. Account availability changes; an earlier model rejection is not a permanent prohibition. No silent capability probes, recurring checks or billable tests are required on ordinary calls. Report an actual rejection and re-evaluate when the user retries or the station changes.

## Sources and limitations

Official guidance:
- https://developers.openai.com/api/docs/guides/image-generation
- https://developers.openai.com/api/docs/guides/image-prompting?model=gpt-image-2.5
- https://developers.openai.com/api/docs/guides/conversation-state

Source inspection: Wei-Shaw/sub2api at 4726bdd08b6201d426a80529b79be123a4008d20. Its OAuth transform forces store=false; image controls can be normalized by upstream; actual byte dimensions repair metadata. This does not identify the CD deployment version or establish a fixed local image resizer. Relay metadata does not independently prove the true upstream model.

The user's tests motivated local image replay and separate delivery sizing. Current tests do not establish universal API quality rankings or pricing differences. Files API, remote URLs, multi-image inputs, Conversations and WebSocket are not implemented in this client.
