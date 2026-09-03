# The artifact vault

*Where the source corpus keeps its bytes now that git is not the right place for them — and the
decisions that settled it.*

The corpus under `data/documents/**` is 3,643 files and 3,690 MB. It lived in Git-LFS until that
store ran out of budget mid-ingest, and it now lives in a **yidam artifact vault** (RFC-0023): a
content-addressed object store where the repository keeps the *record* of which bytes exist and
the store keeps the bytes.

> **A vault stores bytes. Git stores the record of them** — which bytes, and which vault they are
> allowed in.

Epic #2141 tracks the migration. This file is the decision record for **#2142** (its first phase)
and the runbook the later phases fill in.

## Status

| | |
|---|---|
| Decisions below | settled 2026-09-03 |
| Implementation | not started — see #2143 through #2148 |
| Store in use today | Git-LFS, plus the rel-keyed R2 store `/api/doc` serves (#2149) |

## The decisions

### 1. Untracking does not reclaim the LFS budget — so this is not a budget fix

GitHub's documentation is explicit:

> "After you remove files from Git LFS, the Git LFS objects still exist on the remote storage and
> will continue to count toward your Git LFS storage quota."
>
> "To remove Git LFS objects from a repository, delete and recreate the repository."
>
> "If you need to purge a removed object and you are unable to delete the repository, please
> contact support for help."

— [Removing files from Git Large File Storage](https://docs.github.com/en/repositories/working-with-files/managing-large-files/removing-files-from-git-large-file-storage).
[Git LFS billing](https://docs.github.com/en/billing/concepts/product-billing/git-lfs) adds that
storage is *"calculated based on all Git LFS objects associated with a repository, regardless of
when they were uploaded"*, and that a mid-month deletion is not recalculated until the following
month.

Deleting and recreating this repository is **off the table**: it destroys issues, stars and forks,
and this repository's issue history is part of the record. So the ~3.7 GB already pushed stays
billed until a support purge, which is a one-line request rather than an engineering task.

The visible edge of that: `.git/lfs` holds **4.5 GB** against 3,747 MB at HEAD. The ~800 MB
difference is objects only history references.

### 2. What the migration is for: it unblocks ingest, going forward

Two other rationales were tried and both failed against the evidence. It is not a budget fix
(above). It is not an exposure control either: this repository is public and `data/documents/**` is
a **public-records corpus** — Ohio R.C. 149.43 productions and U.S. Government works — with nothing
in the catalog marking an artifact non-redistributable. (`access_tier` is `public` / `keyed` /
`throttled` and describes who can fetch a dataset's *upstream*, not who may hold its bytes.)
Withholding a document from the searchable public site while the underlying public record stays
public is a deliberate and separate act; see `data/site/published-documents.yaml`.

What carries the migration is that **the quota wall is live and already costing evidence.** On
#2074, 261 documents were fetched and screened and only 93 could be committed — 168 deferred for
want of quota — and nine other sites still hold unextracted WWTP permits from the #2065 sweep. Once
new bytes land in a vault instead of LFS, that wall stops being hit. Nothing has to be reclaimed
and no ticket has to be answered first.

**A fix for the forward problem; a containment for the sunk one.**

### 3. The key scheme: content-addressed, in one move

These bytes already live in two stores: Git-LFS, and the Cloudflare R2 bucket
`watermark-documents`, keyed by `data/documents`-relative path, populated by
`watermark objectstore sync` and streamed by the `/api/doc` Pages Function. A vault is keyed by
content address (`<prefix>/sha256/<aa>/<64-hex>`), so the two do not coincide.

The intermediate step — keep the rel-keyed store for serving, move only LFS to the vault — was
rejected on measurement. A full dry-run found **1,672 objects present and 2,173 absent**, a
2,260-file / 1.8 GB upload queue: 57% of the rel-keyed store does not exist to preserve, and those
objects must be uploaded regardless (#2149). Uploading them once under the content address beats
twice.

So `/api/doc` resolves rel → sha256 through a map, measured at **718 KB raw / 179 KB gzipped** for
3,662 entries. That map belongs in **KV**, not the Functions bundle.

#### The rel-keyed store is refilled once more before it is retired

#2149 — `/api/doc` returning 404 for 456 of the 506 published documents, because the rel-keyed store
is 2,173 objects behind — is fixed by running `watermark objectstore sync` against the **existing
rel-keyed keyspace**, without waiting for the vault. The same ~1.8 GB therefore uploads twice: once
now to make the document viewer work, once again under the content address when #2145 lands.

**That is a deliberate decision, not an oversight.** The alternative is leaving 90% of the published
corpus unservable for the length of an epic, and R2 storage and egress on 1.8 GB are cheap beside
that. Recorded here so the second upload is not later read as a mistake, and so #2149 stays
independent of #2144 / #2145 rather than blocked behind them.

### 4. One bucket, one prefix

A single bucket, with the vault under its own prefix, distinct from the rel-keyed keyspace it
replaces. Separate buckets were considered so a second vault could carry its own credential; with
one audience (below) there is nothing for that boundary to separate, and a second bucket would be
an isolation boundary that isolates nothing.

### 5. One vault, and `redistributable: true`

yidam supports several vaults, each declaring an `audience` and a `holds` list, so that a
repository's own derived output and third-party documents held under a licence to read can be kept
apart. **This corpus has no second audience.** It is public records, in a public repository.

```toml
[vault.default]
url      = "s3://<bucket>/<prefix>"
audience = "Anyone who can read this corpus — a public-records corpus published under Ohio R.C. 149.43 and U.S. Government work terms."
```

No `holds`: a single vault holds everything, which is the shipped default. Credentials come from
the environment only — `.yidam/config.toml` is committed and must never carry one.

Two rules that survive the simplification, both about the next acquisition rather than this one:

- **`redistributable` is written explicitly on every artifact**, never left to a default. yidam's
  refusal is per-artifact, and its point is that a licence assertion should be something a person
  stated. The first document obtained under a licence to read rather than to host is the one that
  needs the field to already mean something.
- **Never derive `redistributable` from `published-documents.yaml`.** That file answers *may this
  be served from a searchable public site* — a question about aggregation, answered `no` for two
  files whose underlying records are public. `redistributable` answers *may these bytes be stored
  elsewhere*. Conflating them would withhold public records from the vault.

Adding a second store later requires `holds` on **both** vaults — enforced upstream — so the
migration will be a deliberate edit rather than a silent re-route.

### 6. `data/reference/**` moves in the same pass

19 files, 56 MB. Small, and the higher-risk half: they are what
`watermark catalog lfs-paths` emits (31 paths, ~59 MB) and what `bundle-freshness.yml` selectively
pulls before an export, because the catalog *observes* each dataset's hash into
`data/catalog/_observed.yaml` and from there into the committed bundles.

The mechanism transfers one-for-one — the same paths, the same pre-export hydration, the same
outcome check — and one hazard does **not** transfer: `watermark.catalog.reconcile` is already
pointer-aware (`_is_lfs_pointer`), recording `sha256: None` for an unresolved pointer *and* for an
absent file. So vaulting these cannot write a pointer's hash into a bundle. What does change is
`exists` and `size_bytes`, which flip from a pointer's to an absent file's. Anything regenerating a
committed bundle must therefore hydrate first — which is already true today, for the same reason.

All 19 are source PDFs behind derived CSV/YAML datasets; no test or module reads one by name.

## Measurements

Taken 2026-09-03, at HEAD. The `~5.4 GB` in `agent-worker.yml`, the `~5 GB across ~1,600 files` in
[object-store.md](object-store.md) and the `~2.8 GB` in `bundle-freshness.yml` are all stale
(#2148).

| | files | bytes |
|---|---:|---:|
| `data/documents/**` | 3,643 | 3,690 MB |
| `data/reference/**` | 19 | 56 MB |
| total at HEAD | 3,662 | 3,747 MB |
| distinct content addresses | 3,186 | — |
| `.git/lfs` on disk | — | 4,500 MB |

Distribution: median 0.16 MB, p90 1.7 MB, p99 16 MB, max 141 MB — all under the vault's 5 GiB
single-PUT cap (multipart is not implemented upstream).

**476 files are byte-duplicates** (3,662 files, 3,186 addresses), which content addressing
collapses at no cost.

## Two things that make the migration cheap

**The Git-LFS oid is the sha256 a vault addresses by.** Verified byte-identical on
`data/documents/aedg/PRR-01-bundle.ocr.pdf`. So the whole content-addressed manifest is derivable
from `git lfs ls-files -l` **without materializing a byte**, on a checkout that never pulled LFS.
`data/documents/legal/select-committee-2026/hearings-audio/hearings-audio-externalized.yaml` already
asserts this for four hearing WAVs; #2143 generalizes its shape to the whole corpus.

**The bytes are already here.** A full inventory reported zero skipped pointers, so the working tree
holds real bytes for every LFS object — the first push needs no `git lfs pull`, and the exceeded
quota does not gate it.

## One capability this repository declines

`yidam vault materialize` hardlinks cached artifacts into the working tree under
`<entry-slug>-<hash8>.<ext-from-media_type>`. Measured against `cli/v0.8.0`, `1-12-26 minutes.docx`
materialized as `multi-527ba1ba.bin`, and an extensionless source — one of three in this corpus,
bound to LFS by exact glob precisely because it must never be renamed — also became `.bin`.

That naming is right for upstream's case and wrong for this one. **The as-received filename is
evidence**; it is why `filename-map.yaml` exists and why a malformed source name is never fixed in
place. So `watermark documents hydrate` (#2146) reads the same committed record and hardlinks to
`data/documents/<rel>` instead. This is the only place the projection declines something the binary
offers, and it declines it for chain of custody.

## See also

- `.yidam.toml` — the pinned upstream; `mise run yidam-build` installs it to `.yidam/bin/`
- [object-store.md](object-store.md) — the rel-keyed R2 store and the `/api/doc` Function
- Epic #2141, and #2149 for the store's current staleness
