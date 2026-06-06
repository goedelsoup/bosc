# People — the entity graph's detail store

One markdown file per **key individual**, `data/people/<slug>.md`, opened by a YAML
**frontmatter** header. This is the hand-authored detail layer of the
[entity graph](../../src/bosc/pipeline/entities.py): a profile links to a resolved
graph node by `entity_key` (the canonical normalized name), so the generated graph
and the human research deep-link to each other.

## The `expanded_research` gate

Track *meaningful* individuals here freely. Only profiles with
`expanded_research: true` are **published to the site** (`bosc site build` renders
them under `web/people/` and links them from the entity graph). Everyone else is
tracked privately and stays off the site until promoted.

## Frontmatter schema

```yaml
---
name: Scott J. Ziance            # required — display name
slug: scott-ziance               # optional — defaults to the file stem
entity_key: SCOTT ZIANCE         # optional — graph key; defaults to normalize_name(name)
aliases: [Scott Ziance]
roles: [organizer, permit contact]
affiliations: [Vorys, Sater, Seymour and Pease LLP]
summary: One-line description shown on the index and profile.
expanded_research: false         # the gate — true => rendered on the site
sources:                         # repo-relative paths or citations
  - data/extracted/permits/3789048.epa.yaml
tags: [counsel]
---

Markdown body — curated research prose. Roles/affiliations are read from cited
sources and are leads to verify, not accusations.
```

`extra` keys are rejected (a typo is a loud error). Verify every claim against the
cited source before quoting it in a filing.

## Commands

- `bosc people` — list tracked individuals, the expanded-research flag, and whether
  each resolves in the entity graph.
- `bosc site build` — render the expanded-research profiles into the site.
