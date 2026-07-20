# The public document publish policy

`published-documents.yaml` is the gate that decides which source documents the **public**
site may serve (epic #274 / #280). It is the demand-side peer of `exhibits.yaml`: where
exhibits are a handful of curated downloads, this governs the whole `/api/doc` byte path.

The policy is **publishable-by-default within reviewed scope, withhold declaratively**: a
rel is public **iff** it falls inside a **cleared** boundary *and* is not on the
**withhold** denylist.

## The model: dev-full, public policy-gated

The object store (R2) holds the **entire** corpus, and in **dev / preview** the `/api/doc`
Function serves all of it so the viewer works on everything. On the **public** production
site, `/api/doc` serves a file **only** if this policy clears it. The same flag is carried
on every `DocumentItem.published` in the content bundle — and the build emits the resolved
public rel set to `/published-documents.json`, which the `/api/doc` Function reads — so the
catalog UI and the server-side gate always agree (both derive from this file).

## Cleared scope — the fail-safe eligibility gate

A boundary is cleared with the same three rule kinds; a rel *inside* a cleared boundary
publishes by default, so you no longer restate each file:

- **`collections:`** — whole `data/documents/<slug>` trees (matched on the first path
  segment).
- **`globs:`** — `fnmatch` patterns over the `data/documents` rel.
- **`documents:`** — exact rels.
- **Exhibits** (`exhibits.yaml`) are **auto-included** — they're already published
  downloads, so the existing links keep working without restating them here.

A file in **no** cleared boundary is **never** public — an unreviewed document stays
private by default. This is what keeps the flip safe: clearing is still a deliberate,
reviewed act; only the *within-boundary* default changed from opt-in to opt-out.

## Withhold — the declarative opt-out

The `withhold:` block carves specific rels back out of the cleared scope. It accepts the
same three rule kinds (mapping form: `collections` / `globs` / `documents`) or a bare list
of exact rels as shorthand. **Withhold wins over everything, including the auto-included
exhibits** — so it is the authoritative way to keep one file (a CBI page, a PII-bearing
recorded instrument, a captured page that turned out to carry a live secret) off the public
surface without un-clearing its whole boundary. Record the reason with each withhold entry,
as with a clear.

## The discipline (load-bearing)

Chain of custody holds: the source bytes are immutable and the store serves them
verbatim. The public gate is **not** byte redaction — it is *exposure control*. A boundary
is cleared in this file **only after a completed
[document publication review](../../docs/legal/document-publication-review.md)** (#281)
has confirmed it carries no material that shouldn't be republished (personal PII,
sealed/NDA'd content). **Every cleared boundary must be traceable to that review** — record
the reviewer + date with the entry. Because clearing now publishes a whole boundary by
default, the review is a review of the **boundary**, not one file: clear a `collection` or
`glob` only when you're satisfied every file it covers (including files that land in it
later) is safe, and reach for `withhold` the moment one is not. Captured third-party web
evidence may embed secrets/tokens — that is *evidence*, not a leak to redact (see the root
`CLAUDE.md`); the policy (a `withhold` rule, not deletion) is how such a document is kept
off the public surface.

When in doubt, leave it out: an uncleared file is never public, and dev/preview still serve
it.
