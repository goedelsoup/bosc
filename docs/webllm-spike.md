# WebLLM corpus shell — spike & decision (#1576)

**Status:** complete · **Recommendation:** **split verdict** — **adopt the retrieval half**
(in-browser vector search over the corpus mirror, surfacing cited nodes) and fold it into
**D2 ([#1575](https://github.com/watermark-directory/the-watermark-directory/issues/1575))**;
**do _not_ ship the WebLLM generation shell** on the public wiki. Generation stays server-side
on the grounded Claude `/api/ask`. · **Scope:** Epic [#1560](https://github.com/watermark-directory/the-watermark-directory/issues/1560)
workstream D3.

This is the decision artifact for [#1576](https://github.com/watermark-directory/the-watermark-directory/issues/1576).
The runnable prototype is [`spikes/webllm-corpus-shell/`](../spikes/webllm-corpus-shell/) — a
zero-build page (mirroring [`docs/deckgl-spike.md`](./deckgl-spike.md)'s UMD approach) that puts
the two halves of `yidam export web` side by side against **241 real Lima mirror nodes**.

## Why we're looking at this

`yidam export web` produces a **static WebLLM chat shell** over a corpus + an Arrow vector index:
a single-page app that (1) retrieves relevant nodes with an in-browser vector index and (2) feeds
them to a **quantised LLM running entirely in the browser via WebGPU**, so the whole "ask the
corpus" loop runs client-side with no server. The question for the wiki (Epic #1560, workstream D)
is whether that fits — on **bundle size**, **WebGPU support**, and the **Swiss-03 / evidentiary**
design system — as an embeddable feature.

The context that decides it: BOSC **already has** a grounded "ask the corpus" surface —
[`web/src/pages/ask.astro`](../web/src/pages/ask.astro) + the `/api/ask` Cloudflare Pages Function
— which retrieves passages and answers with **Claude**, streaming, with citations, behind a
Turnstile check, under a hard rule: _"an answer drawn **only from the extracted corpus**, with
citations back to the source. If the record is silent, the answer says so — it never guesses."_
So the spike is really: **does moving generation into the browser buy enough to justify its cost,
given a better-grounded server path already exists?**

## What was tested

The prototype separates `yidam export web` into its two mechanically-distinct halves and makes each
cost tangible against the real corpus (projected by `watermark corpus-mirror`, #1561):

| Half | What the prototype does | Verdict it evidences |
|---|---|---|
| **Retrieval** (Arrow vector index) | Lexical scorer over `corpus.json` (241 nodes); instant, zero-dependency, no WebGPU, no download; returns cited nodes with evidence chips. Every example question returns the right grounded nodes (design low flow → _Dilution_ + _7Q10_; the RDA → _Roadwork Development Agreement_ + _Grant-refund clause_; the Bistrozzi permit → its open-comment question). | **GO** — small, grounded, fits the evidence grammar. |
| **Generation** (WebLLM) | `@mlc-ai/web-llm` from a CDN, WebGPU-gated; downloads a 0.3–0.9 GB quantised model, then generates from the retrieved nodes under an `/api/ask`-style "cite the nodes, say when the record is silent" system prompt. | **NO-GO** — see the three axes below. |

The retrieval half is the recommended shape made concrete: production swaps the demo's lexical
scorer for the committed **MiniLM / LanceDB index we already build** —
[`watermark.site.yidam_index`](../src/watermark/site/yidam_index.py) — same nodes, same citations.
The generation half exists so a reviewer _feels_ the download, the WebGPU requirement, and the
small-model hallucination.

## Axis 1 — bundle size

The WebLLM **runtime** is small (~1–3 MB gzipped JS + a few-hundred-KB TVM WASM). The **model
weights** are the cost, and they dwarf everything the site ships today:

| Artifact | Transfer size | Basis | For comparison |
|---|---|---|---|
| Whole committed Lima bundle (`web/sites/lima`, 44 feeds) | **~3.7 MB** | measured | the entire data tier |
| Corpus mirror snapshot (241 nodes, `corpus.json`) | **64 KB** (17 KB gzip) | measured | what retrieval needs |
| MiniLM embedder (in-browser, retrieval) | **~80 MB**, WASM-capable | cited | one-time, WebGPU-optional |
| WebLLM · SmolLM2-360M q4f16 | **~0.3 GB** | cited | ~80× the bundle |
| WebLLM · Qwen2.5-0.5B q4f16 | **~0.4 GB** | cited | weakest usable chat model |
| WebLLM · Llama-3.2-1B q4f16 | **~0.9 GB** | cited | smallest _tolerable_ quality |
| WebLLM · Llama-3.2-3B / Phi-3.5-mini q4f16 | **~1.7–2.1 GB** | cited | first genuinely useful tier |

**Measurement basis** (so the table is reproducible without changing its conclusions): the two
_measured_ rows are the **uncompressed committed bytes** on this branch on **2026-07-31** —
`find web/sites/lima -name '*.json' | xargs cat | wc -c` (3,925,480 B ≈ 3.7 MB; `du -sh` reports
4.8 MB block-rounded) and `wc -c` / `gzip -c` on `corpus.json`. The _cited_ rows are
**first-load (uncached) transfer** for the `q4f16_1` MLC conversions as published in WebLLM's
`prebuiltAppConfig` model list / model cards — **not independently re-downloaded in this spike**,
so they are approximate (±20%) and marked `~`. The WebLLM runtime referenced throughout is pinned
to **`@mlc-ai/web-llm@0.2.84`** (the prototype's `esm.run` import), the version verified on npm at
that date.

Weights cache in the browser (Cache API / IndexedDB) after first load, so _repeat_ visits are
cheap — but the **first-load tax** is a 0.4–2 GB uncached download for a wiki whose current
heaviest single feed is ~1.75 MB (`documents.json`). The whole documentary ethos of the site is
lightness and honesty in every environment; a multi-hundred-MB-to-GB blob to answer one question is
the opposite of that. The **retrieval** half, by contrast, is an ~80 MB one-time embedder over a
64 KB corpus — in the same order as the existing `/ask` embeddings, and something we already build.

## Axis 2 — WebGPU support

WebLLM has **no usable fallback**: no WebGPU means no model (the WASM-only path is too slow to be
real). WebGPU is now broadly but not universally shipped — **≈70% of global users, ≈30% without**
([caniuse: WebGPU](https://caniuse.com/webgpu), read 2026-07-31; the exact share drifts, so treat
it as approximate) — and the gaps land on exactly the users a public-records site must not turn
away:

| Browser | WebGPU | Note |
|---|---|---|
| Chrome / Edge desktop | ✅ since 113 (2023) | the happy path |
| Chrome Android | ✅ since 121 (2024) | but a ≥0.4 GB pull on mobile data + phone GPU is punishing |
| Safari (macOS / iOS) | ✅ Safari 26, on macOS Tahoe 26 / iOS 26 (2025) | earlier Safari: unsupported ([WebKit: WebGPU in Safari 26](https://webkit.org/blog/17278/webgpu-in-safari/)) |
| Firefox | ✅ 141 — **Windows only** (2025); Mac/Linux still rolling out | ([MDN: WebGPU API compatibility](https://developer.mozilla.org/en-US/docs/Web/API/WebGPU_API#browser_compatibility)) |
| Older / locked-down / enterprise browsers | ❌ | silent dead end |

The prototype's top banner is a live WebGPU probe: on an unsupported browser the whole generation
pane disables and only retrieval remains — which is precisely the production failure mode. A
feature that silently dies for the ~30% of visitors without WebGPU (skewed toward mobile and older
devices) cannot be the default "ask" path. Retrieval degrades far better: the MiniLM embedder runs
in WASM where WebGPU is absent.

## Axis 3 — Swiss-03 / evidentiary fit (the decisive axis)

This is where the WebLLM shell fails hardest, and it is not a styling problem — the widget can be
made to look on-brand (the prototype is). It is a **grammar** problem.

- **The corpus is litigation evidence.** The platform's entire discipline is
  `[verified]` / `[inference]` / `[reference]` / `[open]` tagging and "never guess." The **risk
  hypothesis** — not demonstrated in this spike, which did not run the model in a WebGPU browser, but
  the well-documented behaviour of sub-1B instruction models generally — is that a 0.5–1B in-browser
  model **cannot hold that line** the way Claude does: it is likely to paraphrase figures, drop or
  invent `[n]` citations, and confabulate when the record is thin. A fabricated claim about a permit
  or a dollar figure would not be a cosmetic glitch here — it is a **chain-of-custody and
  defensibility failure**. That risk alone is disqualifying on an evidence platform; confirming it
  empirically (the manual browser pass in the prototype README) would only sharpen a "no-go" that the
  size and support axes already establish. Shipping a generator with that failure mode against
  evidence contradicts the reason the platform exists.
- **Swiss-03 spends the evidence palette on meaning, never on decoration.** A chat box that emits
  ungrounded prose fights that grammar; a retrieval surface that returns **cited nodes with
  evidence chips** (what the demo's left pane does) _is_ the grammar — it points at the record
  instead of narrating over it.
- **We already have the better answer.** `/api/ask` is grounded, cited, streaming, and cheap
  server-side. WebLLM's only genuine wins over it are (a) zero per-query API cost, (b) the
  **question text stays on-device at inference time** (it is not sent to a server to be answered),
  and (c) offline once cached. Note (b) is bounded, not "full client-side privacy": the runtime and
  the multi-hundred-MB model weights are still fetched from a CDN, which sees the visit and can
  correlate it — only the query itself avoids a round-trip. (a) is already inexpensive; (b) and (c)
  do not outweigh a GB download plus the hallucination risk on evidence for a public wiki.

## Recommendation

1. **Adopt the retrieval half.** Ship in-browser, client-side **semantic search over the corpus
   mirror** — the MiniLM / LanceDB index (`watermark.site.yidam_index`) exported as a static
   artifact, surfacing cited nodes with evidence chips and "ask this concept" entry points. It is
   small, WebGPU-optional, grounded, offline-capable, and on-grammar. **This is exactly what D2
   ([#1575](https://github.com/watermark-directory/the-watermark-directory/issues/1575)) already
   scopes** — this spike's left pane is its proof of concept. Fold the work there.
2. **Do not ship the WebLLM generation shell** on the public wiki. Keep generation server-side on
   the grounded Claude `/api/ask`. The bundle-size tax, the WebGPU cliff, and — decisively — the
   hallucination-on-evidence risk each disqualify it against a design system built on evidentiary
   discipline and an existing server path that already does the job better.
3. **Optional, deferred:** if there is ever appetite for a fully-offline "lab" mode, WebLLM could
   live behind an explicit opt-in flag (as marimo was scoped —
   [`docs/marimo-integration-investigation.md`](./marimo-integration-investigation.md)), never on
   the default wiki path, and never presented as a reading of the record. Not now.

## Trade-offs & risks (and how we handle them)

- **"But it's zero-server."** The server cost `/api/ask` pays is already small and the quality gap
  is large; trading grounded Claude for a hallucinating 0.5B model to save cents is a bad trade on
  an evidence platform.
- **Retrieval still needs an index artifact.** The MiniLM index over 241 nodes is tiny; exporting
  it as a static file (Arrow/JSON) alongside the bundle is a modest D2 task, not a new subsystem —
  we already build the LanceDB table.
- **Offline demand.** If a genuine offline use case appears, the deferred opt-in flag (item 3)
  covers it without putting a GB download on the default path.

## What the D-workstream inherits

- **D2 ([#1575](https://github.com/watermark-directory/the-watermark-directory/issues/1575)):**
  promote the prototype's retrieval pane into the wiki — static MiniLM/Arrow index over the mirror,
  cited-node results, "ask this concept." This is the shippable outcome of D3.
- **D1 ([#1574](https://github.com/watermark-directory/the-watermark-directory/issues/1574)):**
  the graph exports (rdf/graphml/sqlite) are the downloadable-artifact peer of the same index;
  unaffected by this decision.
- **`/api/ask`:** remains the generation path. No WebLLM dependency enters `web/`.

## Verification notes

Following the `docs/deckgl-spike.md` convention: the prototype's module script was syntax-checked,
and the retrieval logic was exercised against the real `corpus.json` in Node — all four example
questions return the correct grounded nodes. It was **not** opened in a WebGPU browser during the
spike (no browser automation), so a reviewer should do the quick manual pass in the
[prototype README](../spikes/webllm-corpus-shell/README.md) — that pass is the demonstration: it is
where the 0.4–0.9 GB download and the small-model hallucination against the record become concrete,
and where this recommendation earns its "no-go."
