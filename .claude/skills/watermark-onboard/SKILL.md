---
name: watermark-onboard
description: Use when running `watermark onboard <slug>`, interpreting its output table, deciding what to do after a step fails/skips, or checking whether a site is ready for promotion. Trigger on onboard output, "basin-screen skipped", "hydrology-scenarios: 0", "skipped/error" step statuses, or any question about the onboarding workflow for a new watershed-point site.
---

# watermark onboard — reading and acting on the output

`watermark onboard <slug>` scaffolds per-site data dirs, runs the portable reach connectors, and
returns a blocking review checklist. It **proposes; it never promotes** — flipping a site live
in `web/src/lib/sites.ts` is always a separate, human, parity-gated edit.

## Command flags

| flag | effect |
|---|---|
| _(none)_ | Live run: scaffold + all connectors + write outputs |
| `--dry-run` | Preview target paths, write nothing |
| `--offline` | Use cached/committed fixtures only (no network calls) |
| `--check` | Lint the SiteProfile for unfilled / Lima-copied fields, exit |
| `--research` | Also run the discipline-bound self-research first pass (paid/online LLM call) |

## Output table: columns

```
step         status   output
scaffold     ok       created N dir(s); M README(s)
derive-...   ok       reference/hydrology/low-flow-7q10.derived.yaml
...
```

- **step** — the connector that ran (see below)
- **status** — `ok` | `skipped` | `dry-run` | `error`
- **output** — `data_dir`-relative path when a file was written; otherwise the detail message

## Status semantics

| status | meaning | action |
|---|---|---|
| `ok` | Ran and wrote output | None; verify the value |
| `dry-run` | Would run but can't yet — either `--dry-run` mode, or an offline miss (NWIS/NOAA unreachable); the fixture path shown is where to record it | Fix connectivity or record the fixture |
| `skipped` | A prerequisite is absent (geometry, inventory, etc.) — non-fatal, run continues | See per-step guidance below |
| `error` | Connector threw unexpectedly — non-fatal, run continues | Check detail; rerun that connector standalone |

## Steps, what they do, and what skipped/error means

### `scaffold`
Creates per-site data dirs + house-style READMEs (idempotent). Status is `ok` on a live run and `dry-run` when `--dry-run` is passed.

### `derive-low-flows`
NWIS → basin 7Q10 for every curated mainstem in `_MAINSTEM_GAGES`. Output is a **single shared file** (`reference/hydrology/low-flow-7q10.derived.yaml`) covering all basins; it is appended-to, not replaced, across site onboards.

- `dry-run` → NWIS offline; needs network. The output file is committed after a successful run.
- `ok` but the new site's receiving-water gauges not in `_MAINSTEM_GAGES` in `src/watermark/hydrology/basin.py` → 7Q10 row won't appear; add the gauges to that dict.

### `corridor-ddf`
NOAA Atlas-14 corridor design-storm DDF. Per-site, slug-scoped output.

- `dry-run` → NOAA offline or TTL cached; retry online.

### `ssurgo-hsg`
SSURGO dominant hydrologic soil group over the parcel assemblage geometry. Requires `parcels_relpath` GeoJSON in the SiteProfile.

- `skipped` → **Normal for first onboard.** No committed parcel geometry yet. Needs the per-jurisdiction GIS connector (review gate item 4). The hydrology water balance will use the profile's `dominant_hsg` field as a default in the interim.
- If it runs and the HSG differs from the profile: update `dominant_hsg` in the SiteProfile with a citation.

### `climatology`
NASA-POWER annual averages. Per-site, slug-scoped output.

- `dry-run` → NASA-POWER offline; retry online.

### `basin-screen`
Reads the ECHO POTW inventory for this basin against the shared 7Q10 table. **Read-only; no output written.**

Output detail: `N/M dischargers screened (V violations, T tight)`.

- `skipped (total=0)` → ECHO POTW inventory not yet pulled. Run:
  ```
  WATERMARK_HYDRO_REQUEST_TIMEOUT_S=120 watermark npdes --basin <basin-slug>
  ```
  Then re-run `watermark onboard`. The `--basin` slug is the value of `basin` in the site's `SiteProfile`.
  Large basins (>100 facilities) commonly time out at the default 30 s — always use the 120 s override for a new basin.
- `ok — N/M screened (no_7q10=N, ...)` → screened=0 and no_7q10>0 means the receiving-water mainstem gauges aren't in `_MAINSTEM_GAGES` in `basin.py`. Without 7Q10, the water balance and hydrology scenarios can't run. File a gap issue and add the gauge(s) to that dict.

### `econ-baseline`
Census + QCEW county economic baseline. Per county FIPS.

- `error` → check that the SiteProfile's `county_fips` is set and that Census/QCEW are reachable.

### `rsei`
EPA RSEI county toxics inventory. Per county FIPS.

### `consumer-energy`
EIA consumer energy prices. Per state (`eia_state` in SiteProfile).

### `grid-profile`
EIA-861 utility profile. Per utility (`eia861_utility_number` in SiteProfile).

- `skipped` → `eia861_utility_number` not set; look up the muni utility in the EIA-861 Short Form data (see the EIA fixtures memory).

## Review gate (blocking)

Printed after the step table. Six items must all be satisfied before promotion:

1. Every reference value reviewed against a cited source — no fabricated values.
2. SSURGO HSG matches the SiteProfile, or the profile is updated with a citation.
3. `basin-screen` coverage is sane for this site's receiving waters.
4. Per-jurisdiction GIS connector exists (parcels/zoning; the known lift — see `docs/onboarding.md`).
5. Self-research first pass reviewed (`--research`; triage `data/research/<slug>-<date>/`).
6. Promotion is a **separate manual edit**: flip `status → live` + `selectable → true` for the slug in `web/src/lib/sites.ts`, parity-gated. `onboard` never auto-promotes.

These are written into `data/extracted/<slug>/ONBOARDING.md` (not committed if the file already exists — preserves human check marks).

## Catalog readiness section

```
Catalog readiness — 4/7 datasets present · 3 missing
  still needed: data-centers, meetings, parcel-assemblage
```

Shows how many per-site catalog entries exist. Missing entries block `watermark export` feeds for those dimensions. Common gaps:

| missing entry | what's needed |
|---|---|
| `data-centers` | Corpus extraction of permit/entity records |
| `meetings` | Civic pipeline ingest for local meeting minutes |
| `parcel-assemblage` | GIS connector output (same lift as review gate item 4) |

## After onboard: verify the bundle

```
watermark export --site <slug>
```

Check the summary line for `hydrology-scenarios: N`. If `N = 0`:

1. `basin-screen` ran with `no_7q10 > 0` → the basin's mainstem gauges are absent from `_MAINSTEM_GAGES` in `src/watermark/hydrology/basin.py`. Add them, re-run `watermark derive-low-flows`, then re-run `watermark onboard`.
2. `basin-screen: skipped` → ECHO inventory still missing; pull it first.

`hydrology-scenarios > 0` and all five hydrology feeds non-empty confirms the water balance fed through.

## Common flow for a new site

```
# 1. Register a SiteProfile in watermark.sites.SITES (code edit)
watermark onboard --check <slug>           # lint profile fields before spending network budget

# 2. Pull ECHO NPDES inventory for the basin (one-time; shared)
WATERMARK_HYDRO_REQUEST_TIMEOUT_S=120 watermark npdes --basin <basin-slug>

# 3. Full onboard
watermark onboard <slug>

# 4. If basin-screen shows no_7q10 > 0:
#    → add mainstem gauges to _MAINSTEM_GAGES in basin.py, re-run derive-low-flows, re-onboard

# 5. Verify bundle
watermark export --site <slug>

# 6. Commit all data/reference/<slug>/ + data/extracted/<slug>/ outputs
# 7. Work through the review gate checklist in data/extracted/<slug>/ONBOARDING.md
# 8. When all gate items clear: flip web/src/lib/sites.ts (manual edit)
```
