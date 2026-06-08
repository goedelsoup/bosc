# Allen County political-subdivision meeting-records registry

The canonical roster of Allen County's meeting-holding bodies — the 12 townships,
the cities and villages, and the meeting-holding special districts in the BOSC
thread — and **where each one publishes its minutes and agendas online**. This is
the registry the subdivision-records connectors (`src/bosc/civic/`) read: discovery
fills the `publishing:` block, and per-platform fetchers then pull each body's
documents into `data/documents/<slug>/` for the existing OCR/index → timeline path.

Regenerate the discovered fields with `bosc subdivisions discover`; list the
registry with `bosc subdivisions list`.

## What is grounded vs. discovered

Two kinds of fact live here, held to different standards:

- **Grounded** (`name`, `type`, `governing_body`, `meeting_schedule`, `office`) is
  transcribed **verbatim** from a committed county-published roster (see
  `meta.grounded_sources`) — never from outside knowledge. Each entry names the
  roster it came from in `grounded_from`. These are immutable source facts.
- **Discovered** (`publishing.website`, `publishing.records_url`,
  `publishing.platform`) is a **live-web finding**. Each carries a
  `publishing.discovered:` block with the date and method. A body that has not been
  through discovery has `platform: unknown` / `records_url: null` — which means
  *"not yet looked"*, **never** *"publishes nothing."*

## The publishing landscape (why this isn't one connector)

There is no county-wide meetings API. Each body publishes however it likes, so the
connector layer is a small set of platform adapters keyed off `publishing.platform`,
not one fetcher. After the 2026-06-08 sweep of all 24 bodies:

| platform | meaning | example bodies |
|----------|---------|----------------|
| `civicplus` | CivicPlus / CivicEngage "Agenda Center" (structured agendas+minutes) | City of Lima (`limaohio.gov/AgendaCenter`), LACRPC |
| `wordpress` | WordPress site, links on a "minutes" page | Bath, Shawnee, Perry, Amanda Twps; Cairo, Elida |
| `revize` | Revize municipal CMS | Beaverdam |
| `wix` | Wix site builder | American Twp |
| `unknown` | a site was found but the CMS wasn't fingerprinted, or the site blocked the fetch | Auglaize (.gov), Bluffton (Duda CDN), Spencerville (static), Lafayette (JS shell), Delphos & AEDG (403 WAF) |
| `facebook` | the only web presence is a Facebook page | Richland, Sugar Creek Twps; Harrod |
| `request_only` | no online posting found; obtain by public-records request | Jackson, Marion, Monroe, Spencer Twps |

## Known gaps & caveats (read before using)

1. **Coverage = all 24 bodies looked at once (2026-06-08).** 11 publish online (a
   classifiable site or a found records page), 4 are Facebook-only, 4 are
   records-request-only, and 2 (Delphos, AEDG) front a WAF that blocks the fetch.
   A `discovered:` block means *looked*; `platform: unknown` next to one means
   *CMS unfingerprinted / site blocked*, **not** *publishes nothing*.
2. **WAF-blocked bodies need another route.** Delphos and the AEDG/Port Authority
   return HTTP 403 to the connector even with a browser User-Agent (JS/WAF
   challenge). Their homepages are confirmed; a future fetcher needs a headless
   browser or a records request. The AEDG posts **no** board minutes on its site at
   all — request-only for the econ-dev body central to the BOSC thread.
3. **Meeting cadence is the standing schedule, not attendance.** A printed "2nd &
   4th Monday" does not assert a meeting occurred on any given date; resolve actual
   sittings (and cancellations/special meetings) against the posted records.
3. **Sites move.** Shawnee Township already migrated `shawneetownship.com` →
   `shawneetownshipohio.gov`. The `discovered.asof` date bounds each finding.
4. **County line straddles.** Bluffton (Allen/Hancock) and Delphos (Allen/Van Wert)
   are listed as Allen County seats of record.
5. **The county itself is elsewhere.** The Board of County Commissioners' minutes
   are not in this registry — they are the already-ingested corpus under
   `data/extracted/commissioners/`. This registry is the *sub*divisions.
