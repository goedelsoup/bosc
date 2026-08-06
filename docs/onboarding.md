# Onboarding a watershed-point site

How to bring a new site in the BOSC network (epic [#323](https://github.com/watermark-directory/the-watermark-directory/issues/323) / [#308](https://github.com/watermark-directory/the-watermark-directory/issues/308))
from nothing to a "coming soon" page, repeatably. Lima is the live reference build; the
basin sites (Fort Wayne, Defiance, …) come online one at a time. The scaffold is
registry-driven and the data tier is per-site keyed ([#325](https://github.com/watermark-directory/the-watermark-directory/issues/325)),
so onboarding is a short, ordered chain — `watermark onboard <slug>` runs the middle of it.

> **`onboard` proposes; it never promotes.** Flipping a site to a live, switchable build is
> a separate, human, **parity-gated** edit (step 5). Onboarding seeds reviewable data and a
> blocking checklist — nothing it writes is a finding until a human verifies it against a
> cited source.

**Readiness is a standing property, not an onboard endpoint** (epic
[#1220](https://github.com/watermark-directory/the-watermark-directory/issues/1220)). Onboarding's real job is
to **seed the floor** — the coordinate/FIPS/state-keyed connectors (climatology, Atlas-14,
WBD, SSURGO, Census/QCEW economics, EIA consumer-energy, RSEI) that carry zero curation and
no fabrication risk. Once a site has them and runs `watermark export`, it bundles at **Backdrop
tier** and renders a real watershed + economy page. Readiness itself is **computed in Python at
every `watermark export`** (`watermark.site.readiness`) and written into the bundle
`manifest.json` as a `readiness` block: the five domains (**backdrop, facility, places, record,
inquiry**), each `absent | seeded | live`, plus a derived **tier** (`stub → backdrop → case →
reference`). It **rises when a source lands and falls when one dries up** — you never re-run
`onboard` to recompute it. The floor is always pulled; **above the floor lights up only on its
own evidence** (a disclosed facility, committed parcel geometry, an extracted corpus, a study
that answers) — never scaffolded. The **tier is derived from the four record-bearing domains
only**: `inquiry` is reported and never gates it
([#1971](https://github.com/watermark-directory/the-watermark-directory/issues/1971)).
The **blocking checklist below governs promotion**
(step 5), **not** readiness: a registered site is renderable at whatever tier its data earns
long before it is `selectable`.

## The chain

### 1. Register the `SiteProfile` (code edit)

A site's identity is a `SiteProfile` in [`src/watermark/sites.py`](../src/watermark/sites.py)
`SITES` — the Python peer of the frontend registry. **Start from the scaffold, not a Lima
copy** — Lima's values are Lima-specific and the ones you forget will silently produce wrong
output:

```sh
watermark sites new <slug>     # prints a paste-ready SiteProfile(...) stub
```

The stub fills identity + pre-slug-scopes the six output relpaths (collision-safe by
construction) and leaves every other field a typed `TODO`. Paste it into `SITES`, fill each
`TODO` from a cited source (field guide below), then lint it:

```sh
watermark onboard <slug> --check   # flags fields still unfilled (placeholder) or copied from Lima
```

`--check` writes nothing and exits non-zero while placeholders remain. `watermark sites list` and
`watermark sites show <slug>` inspect the registry. Two hard rules the tooling enforces:

- **Slug-scope every per-site output relpath** — `climatology_relpath`, `corridor_ddf_relpath`
  (→ `reference/hydrology/<slug>/…`), `baseline_relpath` (→ `reference/economics/<slug>/…`),
  `rsei_relpath` (→ `reference/rsei/<slug>/…`), `consumer_energy_relpath` + `grid_relpath`
  (→ `reference/eia/<slug>/…`). If you leave Lima's un-slugged paths, onboarding would
  overwrite Lima's committed files — `watermark onboard` now **refuses** when these aren't unique
  to the site (and a CI test enforces it), but scope them correctly from the start.
- The `SITES` key must equal the profile's `slug` (CI enforces this too).

The frontend needs no hand-edit: register the site's identity in
[`data/sites.yaml`](../data/sites.yaml) with `status: "tracking"` (or `"queued"` once the build
is queued) and `selectable: false`, then run `watermark sites sync` — that regenerates
[`web/packages/core/src/sites-registry.json`](../web/packages/core/src/sites-registry.json),
which auto-builds the site's `/network/<slug>` page and places it in both selector lenses.
Fill in `state` and `basin_major` while you're there: they are the two grouping axes, and
`groupSites` throws naming the site rather than dropping it if either is missing or unknown
(#1863). `watermark sites check` — a CI job — gates that the YAML, the Python profiles, and the
JSON registry all agree.

#### SiteProfile fields, by category

**Must set per-site** (geography/identity — wrong values mislead):

| Field(s) | What |
|---|---|
| `slug`, `place`, `basin` | identity (`basin` is the major-basin axis, e.g. `maumee`). Set `basin_major:` in [`data/sites.yaml`](../data/sites.yaml) to the same slug — the YAML carries it for every entry (that is what the frontend groups by) while the profile carries the cited HUC-8 provenance, and `watermark sites check` fails if the two disagree (#1863). |
| `nwis_sites`, `abstraction_gage`, `supply_gage_primary`, `supply_gage_secondary` | the site's USGS gages (supply + abstraction reach) |
| `design_lat/lon`, `nasa_power_lat/lon`, `map_view_lat/lon/zoom` | the design point, met point, and map centroid |
| `rsei_fips`, `econ_fips`, `county_name` | the county (**Fort Wayne = Allen County, *Indiana*, FIPS `18003`** — not Ohio's `39003`). Set `county:` in [`data/sites.yaml`](../data/sites.yaml) rather than `county_name` here: the YAML is the SSOT, back-fills the profile, and carries the county to the frontend registry for the ask-index's `county` search facet (#1691). `watermark sites check` fails if a profile literal disagrees with it. |
| `eia_state`, `eia861_utility_number`, `lmp_usd_mwh`, `lmp_citation` | the retail utility + its market zone |
| `hydro_utm_epsg`, `gnis_default_state`, `lsc_default_ga` | projection + state/legislature for lookups |
| `toxic_corridor_bbox`, `receiving_water_name` | the industrial receiving-water corridor |
| `plant_receiving` | per-WWTP receiving-water fallback (Lima's are Lima WWTPs — **replace**) |
| `climatology_relpath`, `corridor_ddf_relpath`, `baseline_relpath`, `rsei_relpath`, `consumer_energy_relpath`, `grid_relpath` | the six per-site **output** relpaths — slug-scope all of them (`reference/<source>/<slug>/…`); `parcels_relpath`/`footprint_relpath` point at the site's own committed geometry |
| `dominant_hsg`, `hsg_citation`, `pre_cover`, `post_cover`, `developed_pervious_cover`, `noaa_fallback_24h_depth_in` | stormwater design assumptions (onboarding's SSURGO step validates `dominant_hsg`; record a dual group like `B/D` **verbatim**) |
| `pre_drainage_condition`, `post_drainage_condition`, `drainage_condition_citation` | which letter of a dual HSG each scenario runs on — defaults `drained`/`undrained`; override only with a cited drainage record |
| `passby_primary_cfs`, `passby_secondary_cfs` | the two supply rivers' in-stream passby minimums |

**Reused from the basin** (don't regenerate for a Maumee site): the curated mainstem 7Q10s
(`low-flow-7q10.derived.yaml`) and the ECHO POTW/NPDES inventory — both Maumee-wide.

**Needs research before it's trustworthy:** the GIS URLs (`parcels_url`,
`zoning_url`, `floodzone_url`) — for Lima these are **Allen-County/City-of-Lima ArcGIS endpoints**;
a new jurisdiction has *different* endpoints and needs its own connector (the known lift,
below); the utility number + LMP; and `plant_receiving`, which must come from the site's own
NPDES fact sheets. Until verified, prefer omission/`[open]` over a copied Lima value.

### 2. Run the onboard chain

```sh
watermark onboard <slug>            # live connectors
watermark onboard <slug> --offline  # cached/committed fixtures only (hermetic)
```

`watermark onboard <slug>` ([`src/watermark/onboard.py`](../src/watermark/onboard.py)) builds its own
`Settings(site=<slug>)` (the global `--site` flag is not needed) and, for that site:

- **scaffolds** the per-site dirs (`data/reference/<slug>/`, `data/extracted/<slug>/`,
  and the per-output subdirs `reference/{hydrology,economics,eia,rsei}/<slug>/`) — each with
  a house-style README (source + gaps + regenerate). Idempotent: an existing README is left
  untouched.
- runs the **hydrology reach connectors**: NWIS → basin-derived 7Q10 (basin-level, see
  below), NOAA Atlas-14 → corridor DDF (per-site), SSURGO → dominant HSG over the footprint
  (a validation read against the profile), NASA-POWER → climatology (per-site).
- runs the **economics connectors**: Census+QCEW → county baseline (per-FIPS), EPA RSEI →
  county toxics inventory (per-FIPS), EIA → consumer energy (per-state), EIA-861 + grid →
  grid profile (per-utility — **sparse until the site has a documented facility load**, the
  data-center dimension). All per-site outputs are slug-scoped so they never clobber Lima.
- runs **`basin-screen`** as a coverage validation (read-only).
- **scaffolds the civic registry**: an empty per-site subdivisions stub
  (`data/reference/subdivisions/<slug>/subdivisions.yaml` — `meta.site` + `subdivisions: []`) and
  a house-style README, so the site has a place to enumerate its meeting-holding bodies and a
  prompt to discover them (`watermark.civic`). Idempotent — a curated registry is never
  clobbered. It's **evidence-gated**: an empty registry does **not** flip the `record`/`inquiry`
  readiness domains live ([#1220](https://github.com/watermark-directory/the-watermark-directory/issues/1220)).
- prints a step table + the **blocking review checklist** (step 4).

Use `watermark onboard <slug> --dry-run` to preview the plan (every step + its target path)
without writing anything.

A brand-new site has no committed fixtures and no seed data, so offline the connector steps
record as `dry-run` (naming the cache key to record) or `skipped` — the run always completes.

### 3. Populate + review the per-site data

Seed the site's `data/extracted/<slug>/` and `data/reference/<slug>/` from its corpus, and
fill any `dry-run` connector outputs by running the connectors live and committing the
result. **The connector ordering is no longer prose — it's the catalog's dependency DAG**
([#1025](https://github.com/watermark-directory/the-watermark-directory/issues/1025)): the
`onboard-bundle` aggregate entry (`data/catalog/derived/onboard-bundle.yaml`) declares every
reach/economics connector and its prerequisites, and `watermark catalog run` resolves them
upstream-first, skipping entries still within their refresh TTL:

```sh
watermark catalog run onboard-bundle --site <slug> --dry-run   # preview the resolved plan
watermark catalog run onboard-bundle --site <slug>             # execute it
```

Before committing the regenerated outputs, preview which catalogued datasets actually moved
with `watermark catalog diff` (the committed `_observed.yaml` snapshot vs. live disk — the
`git diff` to reconcile's `git add`), then record the new baseline:

```sh
watermark catalog diff --site <slug>   # what content/membership/freshness moved (observes only)
watermark catalog reconcile            # write the new data/catalog/_observed.yaml baseline
watermark catalog audit --apply        # regenerate COMPLETENESS.md (else `catalog check`/CI fails)
```

(`mise run onboard-site <slug>` prints the same dry-run plan.) Every value is
an **onboarding seed** until reviewed against a cited source — keep the
`[verified]`/`[inference]`/`[reference]`/`[open]` discipline (see the
[evidentiary-discipline skill](../.claude/skills/evidentiary-discipline/SKILL.md); the tag
taxonomy lives in `web/packages/core/src/evidence.ts`, surfaced on the network `/methodology` hub);
"no data-center here yet" is a finding, not a gap.

### 4. The review gate (blocking)

`onboard` prints this checklist **and persists it** to a living
`data/extracted/<slug>/ONBOARDING.md` (created on the first run, carrying the
dimension-coverage and review-gate boxes; your checks survive re-runs). It is the human gate
before promotion:

1. Every written reference value reviewed against a cited source (no fabricated values).
2. SSURGO dominant HSG matches the profile **verbatim**, or the profile is updated **with a
   citation**. A dual rating (`B/D`, `C/D`) is recorded as the dual group, never collapsed to
   its first letter — the drained-vs-undrained choice belongs to
   `pre_drainage_condition`/`post_drainage_condition`, not to this field.
3. `basin-screen` coverage is sane for the site's receiving waters.
4. The site's GIS field-maps are registered (`gis_parcel`/`gis_zoning`/`gis_flood`) for the
   layers it publishes — field names taken from the live `/<layer>?f=json`, not fabricated; a
   layer the site lacks stays `None` (the connector refuses cleanly). See the known lift below.
5. The civic registry is enumerated: fill
   `data/reference/subdivisions/<slug>/subdivisions.yaml` (scaffolded empty by onboard) with the
   county's meeting-holding bodies from a committed roster (grounded facts + `grounded_from`),
   then run `watermark --site <slug> subdivisions discover` and fold the confirmed `publishing:`
   platforms in **by hand** (discovery is read-only). An empty registry does not make
   `record`/`inquiry` live.
6. Self-research first pass reviewed (`watermark onboard <slug> --research`; triage the proposals — see below).
7. Promotion is a separate manual edit (step 5).

The invariant is also enforced in CI by
[`web/packages/core/src/sites.test.ts`](../web/packages/core/src/sites.test.ts): every `selectable`
site must be `status: "live"`, and no `onboarding`/`open` site may be `selectable` — so a
site cannot slip live without the deliberate two-field change.

### 5. Promote (manual, parity-gated)

Once the site reaches parity, flip `status: "live"` + `selectable: true` for it in
[`data/sites.yaml`](../data/sites.yaml) — the identity SSOT — then run `watermark sites sync` so
the generated frontend registry carries it. Both fields are YAML-authoritative; nothing in
`web/` is hand-edited to promote a site. **Note the single-live-build constraint:** only Lima is a
built site at its *own root* (re-rooted under `/bosc`); standing up a *second* root build is a
deeper, separate cutover, not part of routine onboarding. Promoting a peer to `selectable` is not
that cutover — it publishes the site's inner pages under `/network/<slug>/…`, which Fort Wayne,
Urbana and Troy-Piqua already do.

**Promotion is what publishes a site at all.** `selectableSitePaths()` in
[`web/packages/core/src/sites.ts`](../web/packages/core/src/sites.ts) drives `getStaticPaths` for
every `network/[site]/…` route, so an un-promoted site serves only its landing page no matter how
complete its bundle is. A site sitting at `case` or `reference` tier while non-selectable has
committed, merged investigation that no reader can reach — treat that as a backlog item, not a
steady state.

## What's shared vs. per-site vs. the known lift

- **Basin / PJM / national (shared — reuse for free):** the curated mainstem 7Q10s
  (`watermark derive-low-flows` → `data/reference/hydrology/low-flow-7q10.derived.yaml`), the ECHO
  NPDES/POTW inventory (`watermark npdes`, Maumee HUC-8-wide), the PJM balancing-authority
  interchange (`ba-interchange.yaml`), and the federal energy backdrop (`federal-energy.yaml`).
  A new site does not regenerate these.
- **Per-site (slug-scoped via the profile `*_relpath` fields — what `onboard` writes):**
  *hydrology* — NASA-POWER climatology, Atlas-14 corridor DDF; *economics* — the Census+QCEW
  county **baseline** (FIPS), the RSEI county **toxics** inventory (FIPS), EIA **consumer
  energy** (state), and the **grid profile** (utility). Writes go to `reference/<source>/<slug>/…`;
  the **read** side stays Lima-keyed until a site reaches parity (the site build still consumes
  Lima's data until then — a deliberate, documented deferral).
- **Per-site design-storm routing tables (authored, not pulled — #1806, epic #1803 P3):** the
  reach-network map and the routed design storm read three committed tables that resolve
  slug-scoped through the profile pins (Lima keeps its legacy un-slugged
  `reference/hydrology/{network,reaches,reach-nav}.yaml`; a peer commits its own under
  `reference/hydrology/<slug>/`). The **geometry tier** un-gates the study's stormwater
  chapter (§II·7) on its own: author `reach-nav.yaml` (NLDI navigation anchors — cited USGS
  gage coordinates), a magnitude-free `network.yaml` topology, and a `reaches.yaml` whose
  reach lengths are DERIVED from the navigated NHDPlus arcs, then run
  `watermark --site <slug> reaches --write` (record the NLDI responses under
  `tests/fixtures/hydrology/nldi/` so `--offline` regen is byte-stable). Keep
  `catchments: {}` until a **cited** CN/Tc/area screening set exists — a geometry-grade table
  deliberately ships the reach map WITHOUT a routed-hydrograph feed (the #1364 rule; an
  all-zero routed storm would read as "screened"). Lighting the routed feed is the full lift:
  cited catchments + channel slopes + the site's own Atlas-14 depth
  (`noaa_fallback_24h_depth_in`), under the WS-09 Muskingum subdivision and WS-10 peak-fidelity
  disciplines (`hydrology/CLAUDE.md`). Fort Wayne (the Three Rivers confluence) is the first
  peer set and the worked example.
- **Two dimensions captured, one not:** onboard captures **hydrology** and **economics**.
  The third dimension — **data-center activity** (extracted permits/records + entity graph) —
  is corpus extraction + the self-research pass (#247 seam), not a connector pull; it's also
  why the **grid profile** is sparse for a coming-soon site (it aggregates the facility's power
  load, which doesn't exist until that dimension is populated).
- **Per-jurisdiction GIS — now config, not a copied connector (#237):** the coordinate/id-based
  connectors (NWIS / Atlas-14 / SSURGO / NASA-POWER) are free for any reach. County/City parcel
  & zoning GIS is still jurisdiction-specific, but the connectors
  ([`allen_gis.py`](../src/watermark/hydrology/connectors/allen_gis.py) /
  [`lima_gis.py`](../src/watermark/hydrology/connectors/lima_gis.py)) are now **schema-driven**: the
  ArcGIS field names + encodings live in a `GisParcelSchema`/`GisZoningSchema`/`GisFloodSchema`
  ([`watermark.connectors.gis_schema`](../src/watermark/connectors/gis_schema.py)) registered on the
  profile (`gis_parcel`/`gis_zoning`/`gis_flood`, alongside the existing `*_url`s). **The lift
  shrinks to: find the layer + register its field-map** (read the live `/<layer>?f=json` to get
  the real field names — never fabricate them). A layer the site doesn't publish stays `None`
  (the connector/CLI refuses cleanly). **Floodzone is essentially free:** the shared national
  FEMA NFHL field-map (`NATIONAL_NFHL_FLOOD_SCHEMA`) serves any US site — point `floodzone_url`
  at the NFHL layer and reference it. *Worked example — Findlay:* zoning = the City's hosted
  FeatureServer (polygon-only → district catalog, no parcel join); flood = the national NFHL;
  parcels = `[open]` (Hancock County publishes no ArcGIS-REST parcel layer — Beacon/Schneider
  only; the substitute is the Ohio statewide parcel layer filtered to FIPS 39063). *Worked
  example — Ottawa (the full fit):* Putnam County self-hosts its own valid-cert ArcGIS, so parcels
  = the county's `Parcels` layer (`PUTNAM_PARCEL_SCHEMA`, [#420](https://github.com/watermark-directory/the-watermark-directory/issues/420))
  — owner **and** auditor CAMA values on one layer, no statewide substitute needed; flood = the
  national NFHL; zoning = `[open]` (the village's zoning is parcel-class-coded / map-only, no REST).
  This is where reading the live `?f=json` earns its keep: the populated land-use code was `CLASS_1`
  (not the `Class` field, which is 0/unused) and `SALEDATE` is a `MM-DD-YY` string (a per-schema
  `date_decode`) — both only discoverable from the real layer, never guessable.

## The self-research first pass (`--research`, #247)

The flow chains a **discipline-bound `watermark.agent` first pass** that investigates the new site
over the corpus and emits a *proposal* artifact a human triages — the agent proposes, never
promotes. The investigative skills + system prompt are now wired into the agent
([#247](https://github.com/watermark-directory/the-watermark-directory/issues/247)), so onboard runs it as an **opt-in step**:

```sh
watermark onboard <slug> --research
# -> data/research/<slug>-<date>/{findings.md, manifest.yaml}  (review, then triage proposals)
```

It's a **paid/online** LLM call (needs `ANTHROPIC_API_KEY`), so it's opt-in and **skips
cleanly** without a key or under `--offline`. The proposal manifest feeds the step-3 review;
the equivalent standalone command is `watermark research run --topic "…"`.

## Curating a site's content (people / places / exhibits)

Steps 2–3 cover the connector + corpus data; this is the **hand-curated** layer the content
bundle renders. The bundle is **per-site** (#762): `watermark --site <slug> export` reads a site's
*own* curated stores via `watermark.sites.site_scoped_path`, so a non-Lima site never inherits
Lima's. Lima (the reference build) keeps the flat committed layout; every other site lives
under a `<slug>/` subdir. Scaffold these — Fort Wayne's are the worked example
(`data/entities/people/fort-wayne/`, `data/entities/poi/fort-wayne/`, `data/site/fort-wayne/exhibits.yaml`):

| Feed | Lima reads | A site `<slug>` reads |
| --- | --- | --- |
| `people` | `data/entities/people/*.md` | `data/entities/people/<slug>/*.md` |
| `places` (+ imagery) | `data/entities/poi/*.md` | `data/entities/poi/<slug>/*.md` |
| `exhibits` | `data/site/exhibits.yaml` | `data/site/<slug>/exhibits.yaml` |
| `candidates` | `entities/profiles/…` | `entities/<slug>/profiles/…` |
| `lei` | `reference/gleif/…` | `reference/<slug>/gleif/…` |
| `geo/watershed` | `reference/hydrology/wbd/` | `reference/<slug>/hydrology/wbd/` |

An empty/absent store yields a legitimately-empty feed — never Lima's. Every curated record
cites a committed source; **never fabricate a person, place, or exhibit** (chain of custody).

## The narrative: a site's study, not a walk

**A new site does not owe the network a guided walk.** That expectation was retired by
[#1968](https://github.com/watermark-directory/the-watermark-directory/issues/1968) — it had made
hand-authored MDX the price of a site's fifth readiness domain, and it produced ten open issues
asking sites for prose their corpora could not yet cite.

A site's narrative is its **impact study** (`/network/<slug>/study/`). The study is site-generic
and **never locks**: every registered site builds all fifteen chapters from the day it has a
bundle, and a chapter with no record renders the gap *as a finding* — "a real impact study would
report X; the record needed to compute it has not been produced" — rather than a barren page. So
there is nothing to "bring live." The work is to land sources; the study reports what they say.

To deepen it, add a **study note**: `web/src/content/study/<slug>/<chapter>.mdx`, frontmatter
`chapter` / `live` / `updated`, body prose. A note *enriches* a chapter; it never creates one (the
spine is the `STUDY_CHAPTERS` registry in `@watermark/core/study`). Notes are optional per site and
per chapter — Lima carries a complete set, a new peer may carry none — and `_cover.mdx` is the
study's opening abstract. Cite with `<Cite record="…">` / `<Cite document="…">`; an unresolvable
citation fails `src/content/study.notes.test.ts` by name.

The **`inquiry`** readiness domain measures whether that study *answers*: a substantive chapter
count, plus at least one of the two corpus-keyed chapters (`assembly` / `governance`) substantive.
It rises when the site's own records land. It cannot be raised by writing prose, and it does not
gate the tier.

**The one surviving walk** is Lima's `project-bosc`
(`web/src/content/stories/lima/project-bosc/`), kept as the network's single worked example of
reading a record one document at a time — a teaching artifact, not a template every site fills in.
Fort Wayne's, Findlay's and Bowling Green's were absorbed into their studies by
[#1970](https://github.com/watermark-directory/the-watermark-directory/issues/1970).
