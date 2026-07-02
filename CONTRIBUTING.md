# Contributing

## Data discipline

The corpus is litigation evidence. These rules are non-negotiable:

- **Never alter a source document.** Files under `data/documents/` are immutable
  as received. Do not rename them to "fix" typos — record the canonical name in
  a `filename-map.yaml` alias manifest alongside them.
- **Never fabricate a number or a source.** If a figure can't be read off the
  page or returned by an official database, leave it blank and flag it. Mark
  uncertain scan transcriptions `~` (e.g. `~2490`) rather than rounding to exact.
- **Keep the chain of custody.** Dollar totals and subtotals are high-confidence.
  Quantities in degraded scans are often `~`. Cite source file and page in every
  extraction's `meta` block.
- **Tag every claim.** Use `[verified]`, `[inference]`, `[reference]`, or `[open]`
  throughout extracted YAML, docs prose, and site-profile citations.

## Adding source documents

Large binaries (PDFs, images) are tracked via **Git LFS** (see `.gitattributes`).
Run `git lfs install --local` once after cloning. Add new file types to LFS
tracking before committing them.

Collection placement mirrors `data/documents/`:

| Document type | Collection |
|---|---|
| Ohio EPA NPDES permits, fact sheets | `oepa/<site>/` |
| Indiana IDEM permits | `idem/<site>/` |
| Engineering cost estimates | `aedg/` |
| Recorder filings, deeds | `recorder/` |
| County commission minutes | `commissioners/meetings/` |
| Regulatory/SWP3/plan records | `plans/` or `regulatory/` |

Record provenance in a `filename-map.yaml` alongside the files — SHA256,
source URL, fetch date, and the canonical name if the as-received filename
is malformed.

## Adding extractions

Structured extractions are YAML validated against `watermark.models`. Every
committed extraction must stay schema-valid — `test_extracted_yaml_valid.py`
checks all of them on every CI run.

Filenames follow the pattern `<subject>.<kind>[.<variant>].yaml`
(e.g. `roundabouts.summary.opc.yaml`, `1PV00037.npdes.yaml`). Land the file
under the same first-level collection as its source document.

After writing a new extraction, register it in the data catalog:

```bash
watermark catalog reconcile      # update _observed.yaml
watermark catalog audit --apply  # apply inferred fields
watermark catalog check          # must pass before committing
```

The `oepa-permit` mise task does this automatically for permit runs.

## Adding a reference dataset

1. Create `data/reference/<source>/` with a `README.md` naming the source,
   access URL, column descriptions, and known gaps.
2. Keep raw API responses in `data/cache/` (git-ignored). Commit only the
   processed CSV/YAML to `data/reference/`.
3. Add a CLI command (`watermark <name>`) that regenerates the committed file
   from cache or live pull.
4. Add a catalog entry in `data/catalog/reference/`.

## Commit and PR conventions

- Title format: `type(scope): description` — e.g. `feat(research): add …`,
  `fix(grid): …`, `chore(catalog): …`, `data(oepa): ingest …`.
- One `type:*` label + one or more `area:*` labels + an optional `status:*` label
  per PR. The label vocabulary is **managed as code** in
  [`.github/config/`](.github/config/README.md) (`index.ts`, applied by Pulumi) —
  `type:*` (bug/docs/enhancement/chore/gap/…), `area:*` (the subsystem), `status:*`
  (triage state), plus the automation namespaces `agent:*`/`orlop:*` (the agent work
  queue, see [AGENTS.md](AGENTS.md)) and `lead:*` (open-leads board). Run
  `gh label list` for the live set; don't invent an off-vocabulary label.
- Run `mise run check` (backend) or `mise run //web:check` (frontend)
  before opening a PR. Both must pass on `mise run ci`.
- Markdown edits: run `npx markdownlint-cli2` locally. Common failures are
  `MD032` (missing blank line before list) and `MD012` (consecutive blank lines).

## Catalog waiver

If a change modifies a `producer`-tagged dataset's source code without changing
its committed output, add `[catalog-waiver: <reason>]` to the commit message to
skip the producer-check CI gate for that commit.

## Investigative method

The methodology layer lives in `docs/investigative-method/` and
`.claude/skills/`. The six skills are abstract (no project facts, no statute
numbers); the `ENRICHMENT.md` binds them to this repo's artifacts. Evidentiary
discipline is the spine — all other skills are explicitly subordinate to it.
New investigations replace `ENRICHMENT.md`; the skills stay put.
