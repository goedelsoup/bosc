# LimaOhio.com / The Lima News — Q2–Q3 2026 construction & community-reaction wave

This collection captures the April–July 2026 wave of *The Lima News* (LimaOhio.com)
coverage of the Google / Project BOSC data-center build-out that was not yet in the
corpus (issue #1477, sub-issue of #1261 `readiness(lima)`). The last prior web-capture
set was the AEDG "Data Center Updates" articles under
`data/documents/aedg/data-center-updates/` (through 2026-04-27). All claims sourced
from this collection are secondary news reporting, tagged `[reference]`, never
`[verified]`.

## Chain of custody — how these were retrieved

`limaohio.com` is behind a bot-protection service and returned **HTTP 403 / a
"Performing security verification" CAPTCHA interstitial** to every automated fetch
attempted (direct `curl` with browser headers, WebFetch, and a reader proxy), and
**no Wayback Machine snapshot exists** for any of these URLs (the `archive.org` availability
and CDX APIs both returned empty, checked 2026-07-13). The canonical publisher bytes are
therefore not retrievable by this environment.

The three `*.yahoo-mirror.html` files are the **verbatim response bytes of the Yahoo
News syndication mirror** of the same wire article (Yahoo hosts *The Lima News* content
under `provider: "The Lima News, Ohio"` with the canonical `limaohio.com` URL, original
byline, and ISO publish date preserved in the page's JSON-LD). They were fetched with
`curl` on 2026-07-13 and are committed **unaltered** (exact bytes; `-text` per
`.gitattributes`) — the syndication carries the full article body verbatim, so it is the
best faithful capture available given the 403. Provenance is recorded per row below:
the canonical source is LimaOhio.com; the captured-from source is the Yahoo mirror.

Three articles (the 2026-06-22 Wendel op-ed, the 2026-07-09 commissioners item, and the
2026-07-14 resident-transparency item) are in the `news`/`top-stories` sections that Yahoo did
not syndicate (confirmed: not on Yahoo, AOL, MSN, or hometownstations — the 2026-07-14 item
re-checked 2026-07-14). Their headline, date, URL, and substance are confirmed at the
search-snippet level and extracted as `[reference]` (the 2026-07-14 byline is not yet
confirmed); a full raw byte capture remains **owed** (manual browser pull), matching the
issue's own fetch-block caveat.

## Articles

| Date | Title | Byline | Capture |
| --- | --- | --- | --- |
| 2026-04-24 | Data centers promoted at Chamber event | Craig Kelly | captured (Yahoo mirror) |
| 2026-05-11 | Ohio EPA monitoring lime dust at data center construction site | Craig Kelly | captured (Yahoo mirror) |
| 2026-05-15 | Temporary Google construction traffic among resident concerns | Peter Bonasso | captured (Yahoo mirror) |
| 2026-06-22 | Brad Wendel: Allen County's biggest investment is putting our members to work | Brad Wendel (op-ed) | owed (not syndicated) |
| 2026-07-09 | Allen commissioners approve construction projects | (staff) | owed (not syndicated) |
| 2026-07-14 | Residents question transparency with Allen County data center | (unconfirmed) | owed (not syndicated) |

### Canonical URLs

- 2026-04-24 — <https://www.limaohio.com/top-stories/2026/04/24/data-centers-promoted-at-chamber-event/>
- 2026-05-11 — <https://www.limaohio.com/top-stories/2026/05/11/ohio-epa-monitoring-lime-dust-at-data-center-construction-site/>
- 2026-05-15 — <https://www.limaohio.com/top-stories/2026/05/15/temporary-google-construction-traffic-among-resident-concerns/>
- 2026-06-22 — <https://www.limaohio.com/top-stories/2026/06/22/brad-wendel-allen-countys-biggest-investment-is-putting-our-members-to-work/>
- 2026-07-09 — <https://www.limaohio.com/news/2026/07/09/allen-commissioners-approve-construction-projects/>
- 2026-07-14 — <https://www.limaohio.com/top-stories/2026/07/14/residents-question-transparency-with-allen-county-data-center/>

### Captured-from (Yahoo syndication mirror) URLs

- 2026-04-24 — <https://www.yahoo.com/news/articles/data-centers-promoted-chamber-event-233300105.html>
- 2026-05-11 — <https://www.yahoo.com/news/articles/ohio-epa-monitoring-lime-dust-233200504.html>
- 2026-05-15 — <https://www.yahoo.com/news/articles/temporary-google-construction-traffic-among-143100491.html>

The extraction of this collection is `data/extracted/limaohio/lima-news-construction-wave.news.yaml`.
