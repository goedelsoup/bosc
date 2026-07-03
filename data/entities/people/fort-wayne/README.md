# People — Fort Wayne (Project Zodiac)

The Fort Wayne site's per-individual profile store. Same format and discipline as the
network root [`data/entities/people/`](../README.md) — one `data/entities/people/fort-wayne/<slug>.md` per key
individual, a YAML frontmatter header over a hand-written body.

This subdir exists because the content bundle is **per-site** (#762): `watermark --site fort-wayne
export` reads `data/entities/people/fort-wayne/` (not the flat Lima store), via
`watermark.sites.site_scoped_path`. It ships **empty** today — Fort Wayne's actors are not yet
curated — so the `people` feed is correctly absent for Fort Wayne until profiles land here.

## What goes here

Key individuals in the Project Zodiac record: the permit contacts, counsel, applicants, and
officials named in Fort Wayne's committed extractions (`data/extracted/fort-wayne/`,
`data/extracted/idem/fort-wayne/`). Anchor each profile to a resolved entity-graph node by
`entity_key`, and cite a committed source — **never fabricate a person or an affiliation**
(chain of custody; see the root CLAUDE.md).

## The publish gate

Only profiles with `expanded_research: true` are rendered on the site (`watermark export`). Track
others privately until promoted. See the [root README](../README.md) for the full frontmatter
schema.
