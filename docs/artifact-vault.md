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
| Store in use today | Git-LFS, plus the rel-keyed R2 store `/api/doc` serves (refilled 2026-09-04, #2149) |

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

**Done, 2026-09-04: 2,260 objects / 1.8 GB uploaded, 1,585 already current, 0 LFS pointers skipped**
— exactly the predicted queue. The rel-keyed store now holds every one of the 392 documents the
build publishes, verified by `watermark objectstore audit --via store` (`store_absent` = 0). The
second upload, under the content address, is #2145's.

⚠️ **The store was only half of #2149**, and the other half is worth carrying into #2145.

Measured on production 2026-09-04, **before** the refill above. Two populations, kept apart because
they answer different questions:

| | offered | served | 404 |
|---|---:|---:|---:|
| every published rel across all 26 committed bundles | 506 | 26 | 480 |
| **what the deployed build actually offers** (the 8 exported sites) | **392** | 26 | 366 |

Of that 392: **9** were gate-admitted and absent from R2 — the cause #2149 named, and the whole of
what the refill fixed. The other **357** were refused by the *publish gate*:
`/published-documents.json` is one network-global asset built from a **per-site** feed, so it
shipped carrying Lima's set alone and 404'd every other site's documents before R2 was ever asked.
(The 114 further 404s in the wider population are documents of non-exported sites, which no built
page offers.) The daily audit reports against the 392 — the population a reader can reach.

A `rel → sha256` map has exactly the same shape as that gate, and putting it in KV does not change
that: if it is assembled per-site it will be wrong in the same way.

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

**Re-derive the totals from the committed record**, so a stale number in a workflow comment is a
fixable fact rather than an argument (#2148 corrected seven of them, three of which understated the
corpus and four overstated it):

```sh
python -c "import yaml,glob; print(sum(yaml.safe_load(open(f))['meta']['counts']['bytes'] \
  for f in glob.glob('data/*/*/vault.yaml'))/2**20, 'MiB')"
```

At 2026-09-04 that reads **3,662 files / 3,586 MiB** — `data/documents` 3,643 / 3,532 MiB,
`data/reference` 19 / 54 MiB, `.git/lfs` on disk 4,638 MiB. **State the unit:** the table above is
MB (10⁶) and this is MiB (2²⁰), which is most of the apparent disagreement between them.

Distribution: median 0.16 MB, p90 1.7 MB, p99 16 MB, max 141 MB — all under the vault's 5 GiB
single-PUT cap (multipart is not implemented upstream).

**476 files are byte-duplicates** (3,662 files, 3,186 addresses), which content addressing
collapses at no cost.

## The record: `watermark documents manifest`

Implemented by #2143. One `vault.yaml` per first-level collection under each vaulted root — 31 under
`documents/`, 4 under `reference/`, covering **3,662 artifacts at 3,186 distinct addresses**.

```sh
watermark documents manifest                            # write every collection's record
watermark documents manifest --collection documents/aedg # one collection
watermark documents manifest --check                    # report drift; write nothing
```

```yaml
artifacts:
- rel: documents/american-township/meetings/1-12-26 minutes.docx
  sha256: 1b85d2f87a4a777d6d6e4da11c2b32b7f219d38d3f4be65955d5364ddbce8c67
  bytes: 19456
  media_type: application/vnd.openxmlformats-officedocument.wordprocessingml.document
  redistributable: true
```

Four properties of that record are deliberate, and each one is a decision rather than a detail:

- **`rel` is `data_dir`-relative** (`documents/…`, `reference/…`), matching
  `watermark.catalog.StorageItem.relpath` rather than `DocumentItem.rel`. The record spans two roots,
  so a documents-relative key would be ambiguous between them; strip `documents/` to recover the
  `/api/doc` key. Within that the path is the **as-received name, verbatim** — spaces, upper-case
  extensions, and the three files carrying none at all.
- **`media_type` comes from the extension table alone, never a content sniff.** A sniff needs real
  bytes, so the same file would type one way on a `git lfs pull`ed machine and another way in CI —
  and a record that varies by checkout cannot be checked. This also matches what the *deployed* feed
  reports for these files, since the production build never pulls LFS either.
- **`redistributable` is written on every artifact**, never left to a default. See §5 above.
- **Duplicates keep both entries.** 476 of the 3,662 files are byte-duplicates of another; two
  custody paths to one blob is a fact about the corpus, and collapsing them would lose one. Content
  addressing dedupes in the store, which is where dedup belongs.

`--check` needs neither the real bytes nor the network — the same argument that makes the record free
— so it gates in CI (#2148). It reports six kinds of drift, and the asymmetry between them matters:
**`unrecorded`** (tracked but in no manifest) is the one that counts, because after the untrack a
file no manifest names is a source byte with no record at all. **`orphaned`** is not automatically
wrong: it is the expected state once nothing is LFS-tracked. **`address-changed`** means a source
file was replaced, which chain of custody forbids outright. **`missing`** is reported rather than
treated as drift, because an absent file on a partial checkout is not evidence the record is wrong.

A run that cannot address a tracked file **refuses to write** rather than omitting it. A manifest
with gaps is worse than none: it reads as complete.

## The configuration: `.yidam/config.toml`

Committed (#2144), which took a **third** negation under `.gitignore`'s `/.yidam/*` beside
`lint-baseline.yml` and `authorship.yml`. It has to travel with the repository, because
`catalog-artifact-unroutable` is **Error**-severity and compares every projected artifact's `vault:`
against the stores declared here — an uncommitted config does not degrade quietly, it reports all
3,662 artifacts as routed nowhere. That is the intended failure mode, and it only works if the file
is there.

```toml
[vault.default]
url = "s3://watermark-documents/vault"
audience = "…"
region = "auto"
endpoint = "https://<account-id>.r2.cloudflarestorage.com"
path_style = true
```

- **The endpoint carries the R2 account id, and that is fine.** yidam has no environment
  interpolation for `endpoint`, so it must be a literal in a committed file. The account id is an
  *identifier*, not a credential — it appears in every R2 dashboard URL, and a request carrying it
  without the key pair fails. [object-store.md](object-store.md) previously grouped it with the two
  real secrets, which read as a prohibition on the one value that is not one; corrected there.
- **Credentials come from the environment only** — `YIDAM_VAULT_DEFAULT_ACCESS_KEY_ID` /
  `_SECRET_ACCESS_KEY`. Bare `AWS_*` would also be honoured, since upstream lets them fall through
  to the vault named `default` and no other; prefer the explicit form, because R2's S3 token is not
  the account's AWS identity and letting an ambient `AWS_*` satisfy this is how the wrong credential
  reaches the right-looking store.
- **One bucket, own prefix** (`/vault`), keeping the content-addressed keyspace clear of the
  rel-keyed objects `/api/doc` still serves.
- `region = "auto"` is R2's SigV4 scope. `path_style` defaults to true whenever an endpoint is set;
  it is stated anyway.

### The `artifacts:` projection

`watermark.site.corpus_catalog.vault_sources` reads the `vault.yaml` manifests and emits **one
catalog entry per vaulted collection** — 35 of them, carrying all 3,662 artifacts — rather than
registering 3,662 files in `data/catalog/**`, which is a register of *datasets* and would be wrecked
by a five-fold inflation to serve a storage layer.

Adopting `artifacts:` arms two Error-severity checks, both satisfied by construction:

| check | what it wants |
|---|---|
| `catalog-artifact-malformed` | a 64-character **lowercase** hex `sha256` (hex is case-insensitive and a store is not, so two spellings would be two keys), and no `from:` naming a location index the entry lacks |
| `catalog-artifact-unroutable` | every `vault:` names a declared store |

So these entries write **no `from:`** — they carry no `location` list, so any index would name nothing
— and **no `retrieved:`**, because nothing records when a given file was obtained and inventing a
date is worse than omitting one.

They also register **no `covers`**. That field is what makes a path resolve to a citation, and a
collection entry spans hundreds of files: covering them would let a node "cite" the whole of
`documents/aedg` when it means one deed. Measured before deciding — no assessment cell cites a path
under a vaulted root today, so registering them would have changed nothing anyway.

Verified against the pinned binary: `yidam vault list` reports *routed 3662 artifacts the corpus
names*, `yidam vault status` groups them, `yidam doctor` gains a `vault` row, and `yidam lint` stays
green (findings 219 → 254, the +35 being `catalog-uncited` at Info severity, which never gates).

## The push, and what it cost (#2145)

All **3,186 distinct addresses** (3,662 files, 3,586 MiB) are in `s3://watermark-documents/vault`,
verified four ways:

| check | result |
|---|---|
| `yidam vault verify` — re-hash the local cache | 3,186 artifacts, **All intact** |
| the store asked directly, one HEAD per address | **3,186 present, 0 missing, 0 size mismatch, 0 errors** |
| restore into a clean cache via `yidam vault get`, one per collection | **35 / 35 verified** |
| an object uploaded by the fallback client, read back through yidam | verified |

The cache holding **3,186** objects for **3,662** files is the dedup, measured a second way: 476 files
are byte-duplicates and the store keeps one blob each.

### ⚠️ `yidam vault push` re-scans every artifact on every invocation

This is the operational trap, and it is worth knowing before repeating the migration. `push` sends
what the corpus names and the vault lacks, which means each run HEADs **every cached artifact** to
find out. So pushing per collection costs *collections × artifacts* requests — here roughly
**128,000** across 35 pushes, growing as the cache fills — where one push at the end costs 3,186.

Do it in two phases instead: **`vault put` everything first** (purely local, no network at all), then
**one `vault push`**. Per-collection pushing is attractive for resumability and it is how this
migration actually ran, but the cost is quadratic and it is what provoked the rate limiting below.

### ⚠️ The pinned binary's HTTP client wedges against R2 under sustained load

After roughly 3,500 artifacts, `yidam vault push` began stalling: **49 minutes elapsed on an 83 MiB
collection having consumed 8 seconds of CPU**, sleeping on I/O. Adding a per-attempt timeout unmasked
the cause — `HTTP 403 Forbidden` on a HEAD to the vault prefix — and after that, push emitted nothing
at all within two minutes, indefinitely.

It is **not** the credential and **not** the service. Measured at the same moment push was wedged:

- the same token HEADed the *rel-keyed* prefix successfully (`200`);
- the same token HEADed the *vault* prefix successfully, for both a present and an absent key — the
  absent one returning a clean 404, so it is not the missing-key-needs-`ListBucket` quirk either;
- an audit of all **3,186** addresses through `watermark.site.objectstore` (httpx, HTTP/1.1)
  completed with **zero** errors.

So the fault is specific to the binary's own client (reqwest/rustls, negotiating HTTP/2) once
Cloudflare starts throttling it, and it fails by hanging rather than by reporting. **Worth reporting
upstream**, in the manner of the `export-graph` trap: a push that stalls silently is
indistinguishable from a slow one, and the 403 only became visible under an external timeout.

The remaining **105** artifacts were therefore uploaded through `watermark.site.objectstore` to the
identical key scheme. That is sound rather than a workaround, and RFC-0023 is what makes it sound:

> No manifests in the store. No index objects. No `latest`.

An object at `<prefix>/sha256/<aa>/<64-hex>` **is** the whole contract, so a byte-identical object is
indistinguishable whoever wrote it. Each was re-hashed before sending — the address is the identity,
so an object whose bytes do not hash to its key would be a corruption nothing downstream could
detect — and one was then read back through `yidam vault get` to prove the substitution transparent.

### Credentials

The existing R2 token works unchanged; only the variable names differ:

```sh
export YIDAM_VAULT_DEFAULT_ACCESS_KEY_ID="$WATERMARK_DOCUMENTS_OBJECT_STORE_ACCESS_KEY_ID"
export YIDAM_VAULT_DEFAULT_SECRET_ACCESS_KEY="$WATERMARK_DOCUMENTS_OBJECT_STORE_SECRET_ACCESS_KEY"
```

### Not yet done

Nothing is untracked from Git-LFS (#2147), and `.git/lfs` is **untouched** — it remains the third
local copy and the fallback that makes everything above reversible. Do not `git lfs prune`.

## Two things that make the migration cheap

**The Git-LFS oid is the sha256 a vault addresses by.** Verified byte-identical on
`data/documents/aedg/PRR-01-bundle.ocr.pdf`. So the whole content-addressed manifest is derivable
from `git lfs ls-files -l` **without materializing a byte**, on a checkout that never pulled LFS.
`data/documents/legal/select-committee-2026/hearings-audio/hearings-audio-externalized.yaml` already
asserts this for four hearing WAVs; #2143 generalizes its shape to the whole corpus.

**The bytes are already here.** A full inventory reported zero skipped pointers, so the working tree
holds real bytes for every LFS object — the first push needs no `git lfs pull`, and the exceeded
quota does not gate it.

## Getting the bytes back: `watermark documents hydrate`

The dev loop (#2146). Restores vaulted bytes into the working tree under their **as-received**
names, reading the manifests for what belongs where:

```sh
yidam vault pull                                   # fill the local cache from the store
watermark documents hydrate                         # link every recorded artifact into place
watermark documents hydrate --collection documents/aedg
watermark documents hydrate --check                 # report; write nothing
watermark documents hydrate --paths-from list.txt   # the selective set (one data/-relative path per line)
```

Credentials for the pull are the vault's, and the existing R2 token works unchanged:

```sh
export YIDAM_VAULT_DEFAULT_ACCESS_KEY_ID="$WATERMARK_DOCUMENTS_OBJECT_STORE_ACCESS_KEY_ID"
export YIDAM_VAULT_DEFAULT_SECRET_ACCESS_KEY="$WATERMARK_DOCUMENTS_OBJECT_STORE_SECRET_ACCESS_KEY"
```

Six outcomes, and the interesting ones are not the successes:

| outcome | meaning |
|---|---|
| `linked` / `copied` | placed from the cache — **hardlinked**, so 3.6 GB is on the disk once, not twice; copied only across devices |
| `present` | already correct in place; untouched |
| `pointer` | an unresolved Git-LFS stub — see the warning below |
| `absent-from-cache` | not on **this machine**; `yidam vault pull` fetches it. Not an error about the record |
| `conflict` | something disagrees with the record. **Nothing is written**, and the command exits non-zero |

**`conflict` never overwrites.** Hydration must not be able to become the thing that altered a
source byte; a tool that resolved a divergence by overwriting it would destroy the evidence that
there was one. The file stays exactly as found, and the exit code fails a gate.

Four disagreements reach it, and the last three were review findings on the first cut of this
command — each one a path by which hydration could have written a byte nobody recorded:

- **the bytes in place** hash to something other than the record. The original case.
- **a pointer in place names a different digest.** The stub is deleted only once its oid is
  confirmed to be `artifact.sha256`; a pointer naming other bytes is a divergence between two
  *committed* records, and unlinking it would settle that by destroying half of it.
- **the cache entry is not what its address claims.** A content-addressed path *asserts* a digest;
  it does not establish one. The entry is hashed before it is materialized — with a
  pointer-**blind** reader, because `content_address` would read a stub parked at an address as the
  content it names, which is the corruption being looked for.
- **a file is at the target that could not be read.** `content_address` answers `None` for
  unreadable as well as absent, so that case reaches the link, where `os.link` raises
  `FileExistsError` — never `shutil.copyfile`, which opens `"wb"` and truncates whatever it found.

Two orderings carry the same argument, and both were the second round of review on this command:

- **the cache is resolved and verified *before* a pointer is unlinked.** Deleting the stub first
  and finding the cache empty second left the tree with neither the bytes nor the record of which
  bytes belong there — a command whose whole promise is "reported, nothing written" removing a file
  on its way to saying `absent-from-cache`.
- **the copy fallback is atomic.** Bytes land in a temporary sibling and the name is claimed from
  the *finished* file with `os.link`, which refuses an existing target rather than replacing it. A
  copy that dies part-way — full disk, unreadable entry, killed process — therefore leaves an
  orphan `.vault-*.part`, never a half-written file wearing a source name. Copying straight into
  the destination is what makes a partial file reachable under the real one's identity, and the
  next run can only report that as a conflict for a human to untangle.

### ⚠️ A pointer hash-matches its own record

This is the trap worth carrying forward. A Git-LFS oid **is** the sha256 of the content — the fact
that makes the manifest derivable without the bytes — so an unresolved 130-byte stub satisfies any
naive "do the hashes agree?" check while being unreadable to everything. `hydrate` therefore names
`pointer` as its own outcome rather than folding it into `present`, and
`.github/workflows/bundle-freshness.yml` gates on it. That workflow's older guard grepped for the
pointer signature for the same reason: *a pointer parsed as data yields zero rows, not an error.*
Do not simplify either one into a hash comparison.

The cache location is read through `watermark.config.get_settings()` and honours yidam's **own**
`YIDAM_VAULT_CACHE` / `XDG_CACHE_HOME` rather than a `WATERMARK_`-prefixed peer, so a machine that
configured it for the binary does not configure it twice — a second value would be a second answer
to *where are the bytes*.

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
