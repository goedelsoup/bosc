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

Only `parse`/`assertNoCode` are format-specific (the `StoryFormat` seam); everything downstream is
**shared**. Borrowing Nextra's *compile-once-store-run-many*: the dangerous + expensive steps run
at **write time** (authenticated, rate-limited); the public read path only ever renders
**pre-validated SDM**. The compiler ([`src/lib/storyCompile.ts`](../src/lib/storyCompile.ts),
#1094) is **pure** — `(source, format, catalog) → SDM | author-facing errors` — like `buildStory`.

Two front-ends implement the seam, so DSL vs. MDX-restricted-to-data is a bake-off on identical
SDM output:

- **DSL** (`dslFormat`) — a markdown subset (remark-parse, no GFM/HTML) plus container directives
  via remark-directive: `:::atom{handle="<kind>:<site>:<localId>"}` (the handle is a **quoted
  attribute** — a bracketed `[handle]` label would mis-parse its inner `:`s as nested directives)
  and `:::callout{variant=note|info|warning}`. No JSX / imports / `{expressions}` — UGC-safe by
  construction.
- **MDX-as-data** (`mdxDataFormat`) — parse-only MDX (remark-mdx) that hard-rejects
  `mdxFlowExpression` / `mdxTextExpression` / `mdxjsEsm`, so `<Atom handle="…"/>` / `<Callout
  variant="…">` JSX lowers to the *same* SDM. Editorial MDX stays trusted + build-time.

`assertNoCode` rejects raw HTML (DSL) or executable MDX (MDX-data); `sanitize` drops unsafe link
URLs (only relative / `http(s):` / `mailto:` survive); `resolveHandles` resolves each cited handle
against the catalog (unknown → author error), capturing the atom's thin snapshot; `lowerToSDM`
emits the block tree. An out-of-vocabulary block/inline or an unknown directive/component is an
author-facing error, never silently dropped.

## The Story Document Model (SDM) — data, not code

[`src/lib/sdm.ts`](../src/lib/sdm.ts). A normalized block tree that is **data, not code** — the
safety line versus executable Remote-MDX. An untrusted Story can only *arrange* the preordained
vocabulary, never introduce a component, expression, or raw HTML.

- **Inline (a markdown subset):** `text`, `strong`, `emphasis`, `code`, `link`. No raw HTML.
- **Blocks:** `heading` (levels 2–4 only — `h1` is the Story title chrome, not forgeable body),
  `paragraph`, `blockquote`, `list`, `callout` (`{ variant, children }` — an author-framed aside),
  and `atom`.
- **`atom` block** — the **only** way a Story pulls in platform content:
  `{ type: "atom", handle, kind, title }` referencing a catalog handle. A **live pointer**,
  resolved against the catalog at render time — never a copy. The `kind`/`title` are a **thin
  snapshot** captured at write time, so a later-dangling handle still renders a labeled placeholder
  while the full payload resolves live (chain of custody). Reader prose renders visually distinct
  from these cited atoms.

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
- Sharing/moderation (#1098) and catalog revalidation (#1099). Each builds against the types above.
  (The DSL parser + write-path pipeline landed in #1094 — [`src/lib/storyCompile.ts`](../src/lib/storyCompile.ts);
  the D1 store + owner-scoped CRUD Functions landed in #1095 — [`functions/api/stories.ts`](../functions/api/stories.ts) +
  [`functions/api/_lib/storiesStore.ts`](../functions/api/_lib/storiesStore.ts), which run the
  write path server-side against the runtime `/stories-catalog.json` catalog.)

## The renderer + authoring UX (#1096 / #1097 — landed)

The presentation tier is a set of **React client islands** under
[`src/components/islands/stories/`](../src/components/islands/stories/) (the site is pure-static, so
user Stories render client-side). See that directory's `README.md`. In brief:

- **Runtime renderer (#1097)** — `StoryRenderer` walks the SDM block tree (reader prose rendered
  visually distinct from cited atoms); `StoryAtom` is the closed dispatch table made concrete: each
  of the 14 kinds routes to one embedded-scale treatment, with **resolved / loading / dangling**
  states. Because an island can't use the Astro presentation components, atoms resolve against a
  hydrated **render catalog** — the `/stories-atoms.json` build asset ([`src/lib/renderCatalog.ts`](../src/lib/renderCatalog.ts),
  a superset of the thin `/stories-catalog.json`) — fetched at runtime (the ask-index pattern).
- **Authoring UX (#1096)** — `StoryGrab` (grab affordance + persistent tray), `StoryEditor` (the
  block-by-block canvas over the closed vocabulary; it serializes to **DSL source** and lets the
  server recompile — never ships SDM), and `MyStories` (the owner-scoped account view). The block
  model + block⇄DSL serializers are the pure, tested seam in [`src/lib/storyAtoms.ts`](../src/lib/storyAtoms.ts).

Both tiers are build-time gated by `storiesUiEnabled()` (Cognito + `PUBLIC_STORIES_ENABLED`), the
UI peer of the server-side `STORIES_ENABLED` kill switch; a `?preview` mode renders a bundled fixture
Story with no auth/D1 so the design is legible in any build.

## Public sharing + moderation (#1098 — landed)

Publishing a Story mints an unguessable `share_id` and sets `status=published`; the reader route
serves it publicly at `?share=<share_id>` (the client fetches `GET /api/stories/shared/:shareId`, the
only unauthenticated read). The public projection carries no owner id and no editable source; a
disclosure line frames it as a reader's curated reading over the archive, not a statement of the
record. The moderation rails reuse the existing infra:

- **Publish gate** — publishing is early-access-gated initially (a `standard` user saves drafts but
  can't share); `STORIES_ENABLED` is the coarse kill switch; writes are rate-limited.
- **Report** — `POST /api/stories/report` (public, rate-limited, Turnstile-verified when
  `TURNSTILE_SECRET` is set) files a flag onto an admin review queue (`ReportControl` on the public
  reader).
- **Admin takedown** — `/api/admin/stories` (admin role) lists the queue and flips `moderation` to
  `removed`, which 404s the public read instantly and survives an owner edit. An unpublished or
  removed Story is never reachable by its share URL.

`share_id`/`published_at` are **sticky** (an unpublish→republish keeps the same share URL). Schema in
[`migrations/0002_stories_moderation.sql`](../migrations/0002_stories_moderation.sql).
