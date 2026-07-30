# The `impact-study` feed — design (#1804)

> feat. Phase 1 of the impact-study data-tier epic (#1803); the Python realization of the
> missing-impact-study frontend epic (PRs #1795-#1802).
> Status: **implemented** — the `impact-study` feed (`watermark.site.impact_study`,
> contract 1.44.0). The study ships as a committed, citable bundle artifact.

## 1. The problem

The missing-impact-study epic made each site's primary artifact the environmental + economic
impact study its community never received — but as a **frontend derivation**:
`web/packages/core/src/study.ts` composed every chapter's verdict (`data | partial | gap | na`)
and model (headline stats, gap findings, caveats) from the bundle's feeds at the Astro build.
The study was therefore not itself an artifact: nothing committed carried its verdicts, no
machine-readable gap inventory shipped with a bundle, and the curated gap → lead joins lived in
a TypeScript constant no export could validate.

## 2. What it is

A **post-pass projection** — like `open-questions` (#1568) and `facts` (#1587), it re-loads no
corpus and mints no claims. After `export_bundle` assembles the base feeds, the projector
re-derives each of the 13 study chapters from those same payloads and emits one row per
chapter, keyed `(chapter, facility_key)`:

```text
impact-study  ←  facility + hydrology-scenarios + thermal + grid + economics-baseline + …
                 (row counts + content probes → verdict; composers → the chapter model)
```

One `ImpactStudyItem` per chapter:

| field | meaning |
|---|---|
| `chapter` | the study chapter id (`water-supply`, `fiscal`, …) |
| `facility_key` | the resolved primary campus (`null` for a facility-less site-level study) |
| `lead_ids` | the chapter-level curated gap → lead joins (the annex "residual asks") |
| `model` | the chapter's plain-JSON model, serialized with the frontend's own camelCase keys |

The `model` is byte-for-byte the frontend's `StudyChapterModel`: verdict + `statusReasons`,
`stats` (each wearing a `verified | inference | open` evidence tag), `gaps` (the fixed
three-line grammar — the requirement, the absence `[open]`, the ask), and the MUST-render
`caveats`. Display strings are formatted with JS semantics in Python (`Math.round` half-up,
`toFixed`, template-literal number printing) so the shipped strings are identical to what the
TS composers produce.

## 3. Parity is the contract

`studyChapterModel` prefers a shipped row **wholesale** (exact `(chapter, facility_key)`
match — a null key never wildcards onto a campus's rows), with the TS composers surviving as
the fallback for a bundle predating the feed. That preference is why drift would be silent:
a divergent projector doesn't fail a build, it changes a published verdict. Two gates make
that impossible to ship:

- **`web/packages/core/src/study.parity.test.ts`** — over every committed bundle, every
  shipped model must equal the TS-composed model (`composeStudyChapterModel`), canonicalized
  only for the null-vs-omitted optional spelling. Regenerating bundles with a drifted
  projector fails here; editing `study.ts` without re-mirroring the projector fails here too.
- **`study.guardrails.test.ts`** — the 26-bundle invariant sweep (status vocabulary, `na`
  semantics, the noun-phrase gap grammar, JSON round-trip) now runs against the shipped rows
  by construction.

## 4. Curation moved home

`STUDY_GAP_LEADS` — the strictly-curated per-site gap → lead joins (never a fuzzy keyword
match) — now lives in `watermark.site.impact_study`, its ONE owner. The export **refuses the
write** when a curated id stops reconciling against the site's own `leads` feed (the
drift-test discipline, moved to the producer), and the frontend's `studyGapLeads` became a
thin reader of the shipped row's `lead_ids`. A bundle predating the feed simply has no joins;
its gap panels degrade to the submit CTA alone.

## 5. What deliberately did not change

- **No readiness coupling.** The study never locks; the projector consults the facility
  domain state only for the probes the frontend already ran (`facilityState`,
  `facilityLoadAvailable`), computed from the same `domain_states` inputs the manifest block
  gets — the shipped verdicts and the manifest readiness can never disagree.
- **No multi-facility rows.** The primary campus only; the key is threaded so a second
  campus later gets its own rows without a schema change.
- **No prose.** Narrative stays in the per-site MDX slots (`web/src/content/study/`); the
  feed carries data.
- **No catalog atom.** A pure projection over already-catalogued sources introduces no new
  dataset (the `open-questions` precedent).
