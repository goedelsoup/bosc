# CLAUDE.md — `watermark.pipeline`

The ingest → extract → analyze stages plus the cross-document layers. Defers to the
root [`CLAUDE.md`](../../../CLAUDE.md).

- **Stages:** `ingest.py` (inventory `data/documents`, no parsing) → `extract.py`
  (hybrid vision read → Pydantic `Estimate`) → `analyze.py` (deterministic
  `reconcile` **and** the agentic `research_question`).
- **`extract.py` dispatches by document `kind`** (`opc` today) via `EXTRACTORS`, and
  within OPC by **`Profile`** (`watermark.profiles`). Keep it contractor-agnostic: section
  taxonomy and markup rate come from the data/profile — **don't add fixed section
  fields**. Add a contractor by registering a `Profile`, not by editing models here.
- **`analyze.reconcile_*` is format-agnostic** (line item → subtotal → total, markup
  convention from the profile). The legacy `reconcile`/`OPCSummary` path (25%
  convention) still covers the assembled summary artifact — leave it intact.
- `corpus.py`, `entities.py`, `timeline.py`, `hydrology.py` build the cross-document
  layers the site/agent read. They consume **committed `data/extracted/**` +
  `data/reference/**`** — never re-read raw documents or fabricate links.
- **A per-site builder takes `Settings`; it must not call `get_settings()` for the active
  profile.** `get_settings()` is `lru_cache`d on the process-global site, and an export is
  routinely handed a *different* one (`export_bundle(Settings(site=…))` — how the whole test
  suite builds peer bundles). `build_timeline` read its corridor vocabulary that way and
  filtered a peer's own meeting indices through the default site's subjects (#2025); the
  `settings or get_settings()` idiom used everywhere else is the fix. Passing `scope` alone
  is not enough — scope picks the files, the profile picks what they're read *for*.
- Figures come from the image, never the garbled OCR digits.
