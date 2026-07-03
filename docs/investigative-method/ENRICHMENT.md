# Project enrichment layer

This file binds the abstract skills under `.claude/skills/` to the specifics of
this repository. Skills hold reusable *methodology*; this layer holds the *facts,
formats, and identifiers* that specialize them. Skills must never hardcode anything
that belongs here.

It is a **binding map**, not a second copy of the record. Where a fact is the
investigation's content (who, what, when), this layer points to the canonical
in-repo source — `docs/DOSSIER.md`, `docs/COURSE.md`, the reviewed corpus under
`data/extracted/**`, and the audits under `data/extracted/legal/` — rather than
re-asserting it here, so there is one authoritative record and nothing drifts.

To point the same methodology at a different investigation, replace this file
wholesale and leave the skills and `SYSTEM_PROMPT.md` untouched.

---

## Investigation at a glance

**Subject.** A Google hyperscale data center under construction in American
Township, Allen County, Ohio, and its relationship — if any — to local defense
infrastructure (GDIT / General Dynamics; the JSMC Abrams plant in Shawnee
Township). The advocacy position is *pro–data center built transparently*, weighed
by the export ratio of benefits to the community — pro-standards and
pro-accountability, not opposed.

**Where the live state lives.** The confirmed facts, open questions, and retired
hypotheses are maintained in `docs/DOSSIER.md` and `docs/COURSE.md`, carried inline
with the tag vocabulary below. Treat those as authoritative; this file does not
duplicate them. The standing record-completeness audit is
`data/extracted/legal/corpus-completeness-audit.md` (plus per-body
`completeness-audit.yaml` files under `data/extracted/**/meetings/`).

**Chain of custody.** The corpus is litigation evidence. The source-byte and
filename rules in the root `CLAUDE.md` ("Data discipline") govern every skill here;
nothing in the methodology layer overrides them.

## evidentiary-discipline → the tag vocabulary

The two-register rule is encoded as published tags, applied at the sentence level
across `docs/` and the Astro site:

- `[verified]` — register 1; read from a cited extraction in `data/extracted/**`.
- `[inference]` — register 2; a labelled reading of the assembled record.
- `[open]` — register 2; an explicit open question, never stated as fact.
- `[reference]` — an outside-published spec (e.g. a vendor datasheet); cited, not
  a corpus finding.

Approximate transcribed figures keep the `~` marker (`watermark.models._coerce_number`);
never silently drop it. The "documented edge only" rule has a concrete instance in
`watermark.pipeline.entities`: Google is kept as an *annotation, off-graph* — a node is
added only when an instrument names it. Follow that pattern.

## entity-and-document-deconstruction → the pipeline

- **Graph:** `watermark.pipeline.entities` — `EntityGraph` built by `build_entity_graph`
  over the reviewed corpus; `Entity` / `Relationship` are documented edges only.
  Enrichers (`enrich_with_places`, `enrich_with_lei`, …) extend it from cited data.
- **Timeline:** `watermark.pipeline.timeline` — `TimelineEvent`s assembled from deeds,
  NPDES, EPA, plans, OPC, and commissioners records; sequence carries the argument.
- **Gap audits:** `data/extracted/legal/corpus-completeness-audit.md` is the master
  audit; the `web-vendor-audit/` and per-body `completeness-audit.yaml` files cover
  sub-corpora. When a hypothesis is retired, record it where the dossier records the
  refutation — do not silently resurrect it.

## public-records-and-legal-strategy → docs/legal

- **Governing law:** the Ohio Public Records Act; the §9.66(D) economic-development
  provision is treated as a *categorical exclusion* (removed from the definition),
  not a pleadable exemption.
- **Posture:** mandamus first, constitutional challenge second. The denial map and
  predicate analysis live in `docs/legal/mandamus-analysis.md`; the neutral read of
  the proponent submissions is `docs/legal/proponent-analysis.md`. `docs/legal/`
  is hand-written analysis — every claim cites a corpus source page.
- **Active tracks:** county commissioners, the townships, the soil-and-water
  district, and the Ohio EPA. Underlying records live under `data/documents/legal/`,
  reviewed reads under `data/extracted/legal/`.

## gis-and-siting-analysis → watermark.gis

- **Provenanced value:** the `ProvenancedValue` model in `watermark.hydrology.model` —
  every emitted figure carries `source` (`document` / `connector` / `reference` /
  `assumption` / `derived`), `citation`, `confidence`, `asof`. A figure without
  provenance does not ship.
- **Spatial layers:** `watermark.gis` — `sites` (AOI loader), `corridor` (spatial join
  to the frozen corridor geometry), `raster` / `imagery` (Planetary Computer STAC +
  GeoTIFF clip), `analysis` (NDVI/NDWI). These read **committed GeoJSON and a POI
  store**, not live ArcGIS REST; parcels come from `data/reference/`.
- The siting output is a candidate set deserving a closer look, never a prediction.

## investigative-writing-and-editorial → docs/ and web/

- **Published-series state:** a living draft, not discrete installments —
  `docs/COURSE.md`, `docs/bigger-picture.md`, `docs/DOSSIER.md`, and the topic docs
  (`HYDROLOGY.md`, `ECONOMICS.md`, `GRID.md`, `COMPUTE.md`). The reader-facing site
  is Astro + MDX under `web/`, built from the typed content bundle.
- **Register in prose:** the `[verified]` / `[inference]` / `[open]` / `[reference]`
  tags are carried inline rather than as footnoted superscripts.
- **Disclosure:** disclose, consistently and unsoftened, the author's
  civic-transparency platform and any local-IT business overlap as potential
  conflicts of interest, wherever published work warrants it. (Project BOSC was spun
  out of Periplus; see `docs/reference/periplus/`.)

## document-production-and-ocr → the extract pipeline

- **Live read path is vision-based, not tesseract.** `watermark.pipeline.extract`
  renders pages at 300 DPI with pypdfium2 and reads figures from the **image** via a
  forced-tool-use `Estimate` extraction (`watermark.agent.extractor`), validated against
  the Pydantic models in `watermark.models`. The OCR text layer is a hint only — its
  digits are unreliable (`$109,307.69` → `$108.307.89`). Profiles in `watermark.profiles`
  dispatch by format.
- **Publishing is Astro + MkDocs, not docx.** There is no in-repo docx/LibreOffice
  house-format pipeline; the generic OCR (pdftoppm/tesseract), docx-XML, and
  status-report-sheet recipes in the skill are fallbacks for sources the live
  pipeline does not cover.

## Platform

GitHub repo `watermark-directory/the-watermark-directory` — `watermark` Typer CLI; `ingest → extract → analyze`
pipeline; entity graph + timeline + dossier synthesis; the `watermark.hydrology`
water-balance subsystem; the Python data tier (`watermark.site`, `watermark export`) and the
Astro presentation tier (`web/`). See the root `CLAUDE.md` and `README.md`.
