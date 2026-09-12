# Integrated BananaHub prompt optimization

Adapted from BananaHub's constraint extraction, conservative enhancement, and task profiles; see the pinned source and license in `../THIRD_PARTY_NOTICES.md`. Integrated with the official GPT Image prompting and image-generation guides (links in channel.md), including edit invariants, precise text and task-appropriate composition. These instructions run in the current Codex Agent. The transport script does not optimize text.

## Common pass

1. **Lock meaning.** Extract the subject, action, setting, intended use, exact display text, quantities, explicit style, and must-avoid details. Earlier confirmed choices remain in force. Treat subsequent requests as changes to that brief; do not silently replace the subject or brand.
2. **Choose a profile.** Prefer explicit style and intended output over isolated keywords: `photo`, `product`, `text-heavy`, `diagram`, `illustration`, or `general`. A photographic ad can use `photo` plus the exact-text rules. Unclear style falls back to `general` rather than an invented genre.
3. **Clarify the description.** Put the subject and action early. Turn keyword fragments into clear sentences; remove SD/Midjourney weighting syntax only when it actually is weighting, never from mathematical expressions. Remove empty quality-tag spam. Retain meaningful exclusions such as “no extra text”, “no retouching”, and “no unrelated logos”; do not replace them with vague positive adjectives.
4. **Use appropriate language.** Natural English is a useful default for newly expanded scene descriptions, following BananaHub's convention, not a guarantee of superior output. Preserve Chinese/other-language labels, names, formulas and slogans verbatim. Honor a requested prompt language. Keep an already precise Chinese technical brief in Chinese if translation adds risk or no value. In raw mode do not translate, decode entities, trim, or rewrite the original prompt.
5. **Fill useful gaps once.** Add spatial clarity, readable hierarchy, material realism, or other details strongly implied by the request. Choose ordinary defaults needed to compose a coherent image and record material assumptions in `optimization.notes`. Do not add tattoos, props, ethnicities, camera brands, a particular film stock, dramatic weather, or a new palette merely to lengthen a prompt. When creative direction is open, leave it open instead of interrogating the user about every parameter.
6. **Cross-check.** Compare original and final prompts: all required objects/actions remain; exact text and counts are intact; explicit exclusions survive; added details do not conflict. Keep API parameters outside the prose. A complete prompt can pass unchanged. Length should follow complexity; do not truncate scientific content to a generic word limit.

The default is **automatic optimization then generation**. No “approve optimized prompt” screen. Ask only for missing content whose absence prevents a faithful result, such as a requested slogan that was never supplied or an unspecified mechanism that cannot be inferred from source material. If the user asks only for suggestions or optimization, do not generate.

## Photo

- Make photographic intent clear. Preserve the action and environment; frame all required subjects so that a secondary subject is not accidentally cropped out.
- Describe real texture and plausible material wear when relevant, especially for “真实、纪实、抓拍”. Preserve natural skin detail and avoid unintended beauty retouching.
- Specify light, shot size, lens, depth of field, or film grain when the user supplies or clearly implies them. These are visual cues, not claims of physical camera simulation. Avoid defaulting every request to shallow-focus cinematic golden-hour portraits.
- Check skin, hands, object contact, dog/animal anatomy, net/rope continuity, and background geometry in the result.

Example brief: “老水手在船上整理渔网，旁边有只狗，真实一点”.
Suitable expansion: a candid photograph, hands/net/dog visible, natural skin and worn fishing gear, everyday unposed appearance. Tattoos and a specific film stock are not implied by that abbreviated brief; include them only if the user also requested them.

## Text-heavy / brand / poster

- Separate the exact text list from visual instructions. Quote each required label and specify hierarchy, placement, and repetition only as needed.
- Preserve slogans, punctuation, capitalization and Chinese copy. Do not invent prices, dates, URLs, extra logos or filler microcopy.
- Use the supplied audience/brand tone to guide composition. Ensure text/background contrast and breathing room. Do not impose a font family or decorative style that changes the brief.
- Check every visible required character, duplicate slogans, and unwanted filler after generation. A prompt cannot guarantee correct lettering.

## Diagram / scientific mechanism

- Extract entities, directed relations, grouping, sequence, feedback loops, pass/fail branches, labels and formulas before styling. Layout follows these relationships.
- Make the reading order and the endpoints of important arrows explicit. Distinguish data, models, actions and outputs when the brief does.
- Group long explanations into short labels without dropping required entities or modifying scientific meaning. Use whitespace and concise callouts; retain necessary formulas. There is no fixed node-count limit that authorizes omitting the user's content.
- Do not invent measurements, spectra, metrics, materials, mechanisms, citations or model capabilities. Preserve complex-valued notation and all matrix elements when requested.
- Photography cues such as cinematic lighting or bokeh usually do not belong in a mechanism diagram. A hand-drawn style changes rendering, not the scientific graph.
- Inspect the generated connections and formulas. Mark concrete errors; do not present generated conceptual art as experimental evidence.

## Product

- Preserve product geometry, supplied materials, colorway, packaging text and platform context. Do not invent labels or material claims.
- Use white backgrounds/even studio light only for a requested or clearly implied catalog use. Lifestyle scenes can remain open when not specified.
- Frame the product clearly and describe its prominent materials when known. Check shape, reflections, labels and contact shadows.

## Illustration / general

- Preserve explicit medium, era and genre. Clarify subject relationships and composition only where helpful.
- Do not add photographic effects to flat illustration or force human facial features onto objects and robots. Follow explicit anthropomorphism requests when present.
- If no profile fits, perform only the common pass. A concise prompt that preserves the intent is preferable to speculative decoration.

## Follow-ups

Read the selected image and relevant session history. Keep accepted composition, subjects and copy stable when the user asks for a limited change; list what changes and what remains. New user choices override earlier constraints. Submit the selected source bytes for edits rather than reconstructing the image from a description.

The client supports one source image and an optional alpha mask through Images edits or Responses. For Responses, keep local refinement focused on clarity and invariants; the main model may perform its own revision. Save and examine revised_prompt when important requirements change. Raw mode means no local rewrite, not suppression of upstream revision.

Separate scene instructions from pixel requirements. Request image controls structurally; handle local sizing through the delivery policy. Do not add unsupported claims such as guaranteed native 4K or treat a prompt sentence as a reliable replacement for API size controls. A mask guides the edit without guaranteeing every outside pixel remains unchanged.
