# WebLLM corpus shell — spike prototype (#1576)

A runnable, zero-build prototype for [#1576](https://github.com/watermark-directory/the-watermark-directory/issues/1576)
(Epic #1560, workstream D3): evaluate a static, in-browser **WebLLM chat shell** over the
yidam corpus mirror + a vector index. The decision this feeds is
[`docs/webllm-spike.md`](../../docs/webllm-spike.md).

It puts the two halves of `yidam export web` side by side against real data so a reviewer can
*feel* each cost:

1. **Retrieve** — a lexical index over `corpus.json` (241 real Lima mirror nodes). Instant,
   zero-dependency, no WebGPU, no download. This is the half the spike **recommends shipping**
   (production swaps the lexical scorer for the committed MiniLM / Arrow vector index —
   `watermark.site.yidam_index` — same nodes, same citations).
2. **Generate** — `@mlc-ai/web-llm` loaded from a CDN, gated behind WebGPU. Downloads a small
   quantised model (0.3–0.9 GB), then generates a grounded answer from the retrieved nodes.
   This is the half the spike **recommends *not* shipping** — it is here so the download, the
   WebGPU requirement, and the hallucination risk against litigation evidence are tangible.

## Run it

The page fetches `corpus.json`, so serve it over HTTP (a `file://` open is blocked by CORS):

```sh
cd spikes/webllm-corpus-shell
python3 -m http.server 8080
# open http://localhost:8080/  in Chrome/Edge 113+, Safari 26 (macOS Tahoe 26 / iOS 26),
#   or Firefox 141+ (Windows) — the chat pane needs WebGPU; see docs/webllm-spike.md
```

- The **retrieve** pane works in any browser, offline. Click an example or type a corpus term.
- The **generate** pane needs **WebGPU** (banner at the top tells you) and **network** (it pulls
  the WebLLM runtime + model weights from `esm.run`). Pick a model, *Download & load* (first load
  is the big one; it caches afterward), then *Answer grounded question*.

## `corpus.json`

Regenerate the snapshot from the live corpus mirror:

```sh
uv run watermark --site lima corpus-mirror         # writes .yidam/corpus (git-ignored)
uv run python spikes/webllm-corpus-shell/make_corpus.py
```

Each node is `{id, cls, label, desc, tag, scope}` — the projected `label`/`description` a
mirror node carries, plus its class and claim tag. 64 KB (17 KB gzipped) for 241 nodes.

## What was verified

Following the `docs/deckgl-spike.md` convention: the module script was syntax-checked, and the
retrieval logic was exercised against the real `corpus.json` in Node — every example question
returns the correct grounded nodes (design low flow → *Dilution* + *7Q10*; the RDA → *Roadwork
Development Agreement* + *Grant-refund clause*; the Bistrozzi permit → its open-comment question).
It was **not** opened in a WebGPU browser during the spike (no browser automation), so the chat
pane needs a quick manual pass per the run steps above — that pass is the point of the demo: it
is where the download size and the small-model hallucination become concrete.

## Not shipped

This directory is a spike, not part of the `web/` build. It loads WebLLM and model weights from a
public CDN — a local-demo allowance that would violate the site's offline / self-contained /
no-external-host production constraints.
