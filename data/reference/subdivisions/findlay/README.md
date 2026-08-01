# Findlay (findlay) — subdivision meeting-records registry

Per-site registry of Hancock County's 32 meeting-holding bodies — the 17 townships, the
11 incorporated villages, the two cities, the Board of County Commissioners and the
Regional Planning Commission — and **where each publishes its minutes and agendas
online**. Read per active site by `watermark.civic` (`registry_path`). This peer
slug-scopes under `subdivisions/findlay/`; Lima (the reference build) keeps the flat
legacy path.

Scaffolded empty by `watermark onboard findlay` (#1524), then enumerated and swept for
the cross-site civic-loader pilot (#1839, epic #1520). List it with
`watermark --site findlay subdivisions list`.

## Source

Hand-curated, not connector-generated.

- **Grounded** (`name`, `type`, `governing_body`, `meeting_schedule`, `office`) is
  transcribed **verbatim** from the committed
  [Hancock County Directory of Officials 2026](../../../documents/findlay/reference/) —
  never from outside knowledge. Hancock publishes one consolidated roster where Allen
  County publishes three separate sheets, so a single document grounds every body here;
  `meta.grounded_sources` records which page grounds what, and every entry names it in
  `grounded_from`. The roster's own phrasing is kept ("Third Monday of the Month, 7:00
  pm"), deliberately un-normalized to Lima's "3rd Monday, 7:00 PM" house style.
- **Discovered** (`publishing.website`, `publishing.records_url`, `publishing.platform`)
  is a **live-web finding**, folded in BY HAND from
  `watermark --site findlay subdivisions discover` (read-only; it never rewrites this
  file). Each carries a `publishing.discovered:` block with the date and method.

## The publishing landscape

There is no county-wide meetings API, so the connector layer is a set of platform
adapters keyed off `publishing.platform`. After the 2026-08-01 sweep of **all 32 bodies**
— every one has a `discovered:` block; none is left at "not yet looked":

| platform | meaning | bodies |
|---|---|---|
| `wordpress` | WordPress site, dated document links on a records page | Allen, Marion, Liberty, Delaware Twps; Arcadia, Arlington, Mt. Blanchard |
| `civicplus` | CivicPlus / CivicEngage "Agenda Center" (structured agendas+minutes) | Hancock County Commissioners, City of Fostoria |
| `squarespace` | Squarespace site | Hancock Regional Planning Commission |
| `unknown` | a site was found but the CMS wasn't fingerprinted, or the site blocked the fetch | Bluffton (Duda CDN), Rawson, Vanlue, Van Buren village (503), City of Findlay (403 WAF), McComb (403 WAF) |
| `facebook` | the only web presence found is a Facebook page | Amanda Twp, Jenera |
| `request_only` | no online posting found; obtain by public-records request | Biglick, Blanchard, Cass, Eagle, Jackson, Madison, Orange, Pleasant, Portage, Union, Van Buren, Washington Twps; Benton Ridge, Mt. Cory |

12 bodies have a records URL on record. The Hancock County Commissioners' Agenda Center
has the same `/AgendaCenter/ViewFile/{Agenda,Minutes}/_MMDDYYYY-<id>` shape as Lima's and
LACRPC's, so the existing `civicplus` fetcher reads it unchanged — the first peer to
exercise it. Hancock RPC is the network's **first** `squarespace` body: the platform was
already in the generic scraper's dispatch set but had never been matched by a real body.

## Known gaps & caveats (read before using)

1. **`unknown` and `request_only` are not "publishes nothing."** `unknown` next to a
   `discovered:` block means *looked at, CMS unfingerprinted or fetch blocked*;
   `request_only` means *no online posting located*. Neither is evidence a body withholds
   records, and a null `records_url` never is either. Two bodies (City of Findlay,
   McComb) WAF-block the connector with HTTP 403 — the same wall the Findlay governance
   watch hit on the city's ordinance pages (#1463) — and one (Van Buren village, on a
   free Wix subdomain) returned 503. Those three need a headless route or a records
   request.
2. **The same-name trap is worse here than at Lima.** Ohio has an Allen, an Amanda, a
   Jackson, a Liberty, a Madison, a Marion, an Orange, a Pleasant, a Portage, a Union, a
   Van Buren and a Washington Township in several other counties, and pattern-guessing a
   domain finds them: `eagletownship.org` redirects to a **Michigan** township,
   `jacksontwp.org` is Franklin County's, `portagetwp.org` is Wood County's,
   `washingtontwp.org` is Montgomery County's — and Madison Township exists in Hancock
   County **Iowa**. Every `request_only` entry's note records the decoys ruled out. Do not
   add a website here without tying it to Hancock County from the site's own content.
3. **The roster is grounded source for the body, not for its URL.** Mt. Blanchard's
   printed `mtblanchardoh.com/villagesite/` 404s (the site root serves); Allen Township's
   `allentownship.com` and Marion Township's `mariontwphancock.com` 301-redirect to their
   `.gov` domains. Roster-printed URLs are recorded in each body's `note`, and what
   actually resolves is in `publishing.website`.
4. **Meeting cadence is the standing schedule, not attendance.** A printed "First Tuesday
   of the Month" does not assert a meeting occurred on any given date. Several boards
   recess in January; Allen Township's roster line says so outright
   ("February-December").
5. **Two bodies are shared with other registries.** Bluffton (Allen/Hancock) is in Lima's
   registry too, grounded there from Allen County's mayors roster — the same village,
   grounded twice from two counties. Fostoria (Seneca/Hancock/Wood) is seated in Seneca
   County and is carried here only because the Hancock roster carries it. Three township
   names (Amanda, Jackson, Marion) are also Allen County township slugs in Lima's
   registry; the registries are separate files read per active site and their meeting
   trees nest separately, so the slugs cannot collide (#1520/#1522).
6. **The county board IS enumerated here**, unlike Lima's registry, which excludes Allen
   County's because that record is a separately ingested corpus under
   `data/extracted/commissioners/`. Hancock's has no such corpus.
7. **Not enumerated:** the county's other appointed boards (Board of Elections, Park
   District, Soil & Water, Solid Waste, Public Health, Library), the school districts, and
   the fire/EMS districts. The roster names them but grounds no governing body or cadence
   for them. Add one when it holds a record this project needs, with its own grounding.
8. **A records URL is an index, not an archive.** Both fetchers read what the page
   surfaces now — the CivicPlus Agenda Center index view, and whatever a WordPress
   records page currently links. Liberty Township publishes several parallel per-year
   minutes pages at once (`/minutes/`, `/2024minutes/`, `/2025-2/`, plus `-copy`
   duplicates) with no single index; an ingest there must walk them all.

## Ingested so far

Two bodies have been run end-to-end (`download → index → summarize`) into
`data/documents/findlay/<body>/meetings/` and `data/extracted/findlay/<body>/meetings/`:

| body | platform | documents | span |
|---|---|---|---|
| `allen-township` | wordpress | 39 minutes | 2024-01-02 → 2026-07-07 |
| `hancock-county-commissioners` | civicplus | 108 agendas + minutes | 2026-01-06 → 2026-07-30 |

The completeness audit reads Allen Township's monthly cadence (94% coverage, 2 dates to
request) and the commissioners' weekly "Tuesday & Thursday" one (92%, 5 dates). A missing date
is a candidate to verify, never proof of withholding.

Everything else in the registry is enumerated and swept but not ingested.

## Regenerate / extend

```sh
watermark --site findlay subdivisions list
watermark --site findlay subdivisions discover <slug> [--url <homepage>]   # read-only
watermark --site findlay subdivisions download <slug> [--since YYYY-MM-DD]
watermark --site findlay subdivisions index <slug> [--ocr]
watermark --site findlay subdivisions summarize <slug>
watermark --site findlay subdivisions audit [<slug>]
```

`discover` never writes here — fold its findings in by hand so the grounded/discovered
split stays intact. See `docs/onboarding.md` and `src/watermark/civic/CLAUDE.md`.
