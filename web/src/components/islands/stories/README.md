# User-authored Stories — the React islands (#1096 / #1097)

The presentation tier for reader-authored Stories. The site is pure-static (no SSR) and user
Stories come from D1 at runtime, so this is all **client islands** (`client:only="react"`) that
resolve the SDM against a catalog fetched at runtime. Editorial (site-authored) Stories share the
exact same renderer — the only difference is the byline. See
[`../../../../docs/user-stories-contract.md`](../../../docs/user-stories-contract.md) for the model.

## The pieces

| File | Role |
|---|---|
| `StoryRenderer.tsx` | **#1097** — walks the closed SDM block vocabulary; reader prose renders visually distinct from cited atoms. |
| `StoryAtom.tsx` | **#1097** — the closed dispatch table: each of the 14 catalog kinds → one embedded-scale treatment, with **resolved / loading / dangling** states. Never a broken card. |
| `StoryReader.tsx` | **#1097** — the page-level reader: owner eyebrow + title chrome + byline over `StoryRenderer`. Fetches `?id=` (owner's own) or renders a `?preview=` fixture. |
| `StoryEditor.tsx` | **#1096** — the block-by-block authoring canvas over the closed vocabulary. Serializes to **DSL source** and lets the server recompile — never ships SDM. Surfaces author errors (paste-blocked, unsafe-link, dangling atom, server validation). |
| `StoryGrab.tsx` | **#1096** — the grab affordance (`GrabPin`) + the persistent non-modal tray. Grabbing drops a thin snapshot into `sessionStorage`, which the editor seeds from. The default export is a demo host + integration reference. |
| `MyStories.tsx` | **#1096** — the owner-scoped account view: Stories by status, edit / share / delete, empty state. |
| `parts.tsx` | Shared render primitives (evidence pill, hand-rolled sparkline/bars, pins) — the React echoes of the Astro presentation components an island can't import. |
| `client.ts` | Browser plumbing: authed fetch against `/api/stories`, the render-catalog asset load, wire types. |
| `tray.ts` | The grab→editor handoff (thin snapshots in `sessionStorage`). |

## Why a hydrated render catalog

An island can't reach the Astro components (`RecordBlock.astro`, …) or the content bundle on disk,
so `StoryAtom` renders from a **`HydratedAtom`** (the embedded-scale payload per kind). Those are
served as a build asset, `/stories-atoms.json` ([`~/lib/renderCatalog.ts`](../../../lib/renderCatalog.ts)) —
a superset of the thin `/stories-catalog.json` resolver catalog — fetched at runtime (the same
static-asset-at-runtime pattern as `/ask-index.json`). Resolution stays a live pointer: a missing
handle ⇒ dangling (render the write-time snapshot), never a copy.

## Discipline

- **Data, not code.** The renderer is exhaustive over the closed SDM vocabulary; there is no
  custom-component escape hatch. Reader prose and cited platform evidence stay unmistakably distinct.
- **Evidence palette is for evidence.** Story chrome/affordances use forest/ink; the `--ev-*` tokens
  only ever encode an atom's evidence tag.
- **Pure logic is split out** into `~/lib/storyAtoms.ts` (families, block⇄DSL serializers, hydration)
  and unit-tested there — the islands themselves stay declarative (no React DOM test dep in the repo).
