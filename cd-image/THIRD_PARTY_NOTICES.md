# BananaHub attribution

The prompt-optimization instructions are adapted from
https://github.com/bananahub-ai/bananahub-skill at commit
`ffee193d135a0e84875a2073ed403c121014e393`, inspected 2026-09-11.

Source files: `SKILL.md`, `references/optimization-pipeline.md`,
`references/prompt-guide.md`, and `references/profiles/{photo,diagram,text-heavy,product}.md`.

Adaptation: retain constraint-first optimization, task-specific refinement and exact-text preservation; make one-pass optimization automatic as requested; preserve raw prompts verbatim locally; use CD Images/Responses transport with local image history and separately labelled delivery resizing. Responses may additionally revise the prompt upstream. This package is self-contained and does not incorporate BananaHub's provider runtime, remote template catalog, telemetry, credential persistence or automatic model fallback. Original Gemini-specific numerical heuristics are not treated as validated GPT Image limits.

## Upstream license

MIT License

Copyright (c) 2026 bananahub contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
