# `data/extracted/limaohio/` — The Lima News (LimaOhio.com) coverage

Extractions of secondary *Lima News* news coverage of the Google / Project BOSC data
center, mirroring the `data/documents/limaohio/` collection. All claims here are
secondary news reporting, tagged `[reference]`, never `[verified]`.

## Contents

- `lima-news-construction-wave.news.yaml` — the Q2–Q3 2026 construction &
  community-reaction wave (issue #1477): the corpus's first construction-phase coverage
  — Ohio EPA lime-dust monitoring (2026-05-11), the North Cole Street roundabout open
  house and resident concerns (2026-05-15, which also corroborates the Peterson CMAR and
  dates completion to ~Jan–Mar 2028), the Chamber proponent pitch (2026-04-24), the
  commissioners' Brightspeed fiber RUMA + roadwork (2026-07-09), and the building-trades
  op-ed (2026-06-22).

## Source & retrieval

`limaohio.com` is bot/CAPTCHA-gated (HTTP 403 to automated fetch) with no Wayback
snapshot, so the three captured articles are committed as verbatim **Yahoo News
syndication-mirror** bytes under `data/documents/limaohio/` (provider "The Lima News,
Ohio"; canonical URL, byline, and ISO date preserved in the page JSON-LD). Two
un-syndicated articles are snippet-confirmed with a raw byte capture still owed. Full
chain of custody is in [`data/documents/limaohio/SOURCES.md`](../../documents/limaohio/SOURCES.md).
