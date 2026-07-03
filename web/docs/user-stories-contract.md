# User-authored Stories — the owner axis + shared render contract (#1092)

The written contract the rest of epic #1090 (#1094–#1099) builds against. It defines **one Story
resource on an owner axis**, and the **shared render/output seam** (the SDM block model + the
preordained component vocabulary + the resolver interface) that both Story owners resolve into.
No behavior change to today's editorial stories — this is additive modeling.

## One resource, two owners

A Story is **not** a new type competing with today's editorial stories. It is the same resource,
partitioned by an owner discriminator so the two never contend — not in naming, storage, or routing:

```ts
interface StoryOwner { kind: "site" | "user"; id: string }
```

- **site-owned** — today's editorial stories (`walk.STORIES`, sourced from the `stories` MDX
  collection, editorially vetted). `owner = { kind: "site", id: <site-slug> }`, so `owner.id ===
  story.site`. This is unchanged by the epic; `walk.ts` is **not** renamed — it is recognized as
  the `site` special case of the axis.
- **user-owned** — the new feature. `owner = { kind: "user", id: <user-id> }`, sourced from D1
  (#1095), never from `data/**` (chain of custody preserved by construction).

Types + helpers live in [`src/lib/walk.ts`](../src/lib/walk.ts): `StoryOwner`, `siteOwner(site)`,
and `storiesOwnedBy(stories, owner)`. **Surfaces filter by owner:** a site page lists its own
site-owned stories (and, later, featured user-owned ones); an account page lists a user's own —
all via `storiesOwnedBy`, which matches on the `(kind, id)` pair so a site slug and a user id that
happen to share a string can never collide.

## The write path (one pipeline, pluggable front-end)

```
parse → assertNoCode → sanitize → resolveHandles → lowerToSDM → persist
```

Only `parse`/`assertNoCode` are format-specific (DSL for the untrusted user tier; MDX stays only
for the trusted, build-time editorial tier). Everything downstream is **shared**. Borrowing
Nextra's *compile-once-store-run-many*: the dangerous + expensive steps run at **write time**
(authenticated, rate-limited); the public read path only ever renders **pre-validated SDM**.

#1092 defines the seam and its output type (the SDM); #1094 implements parse → lower for the DSL.

## The Story Document Model (SDM) — data, not code

[`src/lib/sdm.ts`](../src/lib/sdm.ts). A normalized block tree that is **data, not code** — the
safety line versus executable Remote-MDX. An untrusted Story can only *arrange* the preordained
vocabulary, never introduce a component, expression, or raw HTML.

- **Inline (a markdown subset):** `text`, `strong`, `emphasis`, `code`, `link`. No raw HTML.
- **Blocks:** `heading` (levels 2–4 only — `h1` is the Story title chrome, not forgeable body),
  `paragraph`, `blockquote`, `list`, and `atom`.
- **`atom` block** — the **only** way a Story pulls in platform content: `{ type: "atom", handle }`
  referencing a catalog handle (`:::atom[<kind>:<site>:<localId>]`). A **live pointer**, resolved
  against the catalog at render time — never a copy of the cited atom. Reader prose renders
  visually distinct from these cited atoms.

`StoryDocument = { version, blocks }`. `version` records the `SDM_CONTRACT_VERSION` the body was
lowered under (compile-once-store-run-many); a bump means stored docs may need revalidation
(#1099). `validateStoryDocument(value)` structurally validates an untrusted value against the
closed vocabulary — the runtime "data, not code" guard (there is nowhere for a script node to hide).

## The preordained component vocabulary

`ATOM_RENDER_SLOTS: Record<CatalogKind, "atom:<kind>">` — exactly **one render slot per catalog
kind**, so the runtime renderer (#1097) has a closed, exhaustive dispatch table. A Story can grab
any kind but never add a render component. The kinds are the closed set from the hydrated catalog
([`src/lib/catalog.ts`](../src/lib/catalog.ts), #1093).

## The resolver seam (SDM × catalog)

The catalog (#1093) is the addressable index; resolution is a **live pointer** (chain of custody):

- `sdmHandles(doc)` — every catalog handle the SDM references, in document order (write-path
  validation + #1099 revalidation read this).
- `resolveSdmAtoms(doc, catalog)` — resolve each handle via `catalog.resolveHandle`, keyed by
  handle. The seam the runtime renderer (#1097) and the write-path validator (#1094) share.
- `sdmIsResolvable(doc, catalog)` — the write-time gate (before persist) and the health signal a
  stored Story is re-checked against when the catalog changes (#1099).

## Out of scope (deliberately)

- Migrating the editorial MDX path onto the DSL — the contract makes a future convergence cheap,
  but we don't pay for it now. The editorial path keeps its MDX; both paths only need to *lower
  into the same SDM* to share the renderer.
- The DSL parser (#1094), the renderer components (#1097), the D1 store (#1095), authoring UX
  (#1096), sharing/moderation (#1098). Each builds against the types above.
