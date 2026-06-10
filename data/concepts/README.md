# `data/concepts/` — the wiki concept-glossary store

Curated term/method definitions for the site's **Wiki** section (Project BOSC
two-tier refactor, issue [#68](../../README.md)). The lightweight peer of the
per-individual profile store under [`data/people/`](../people/): one markdown
file per concept, opened by a YAML **frontmatter** header.

Each `data/concepts/<slug>.md`:

```markdown
---
title: 7Q10
kind: term                 # concept | term | method
aliases: [7Q10 low flow]
tags: [hydrology, permitting]
summary: The design low-flow statistic used to size effluent dilution.
related: [assimilative-capacity, consumptive-cooling]   # sibling concept slugs
---

Body markdown. Inline `[[wiki links]]` resolve against concepts, entities,
and people — e.g. [[assimilative capacity]] or [[Cynthia Leis]].
```

- **Loaded + exported** by [`bosc.site.concepts`](../../src/bosc/site/concepts.py)
  into the `concepts` bundle feed (`bosc export`); the frontend renders one page
  per concept and resolves the `[[wiki links]]`.
- `slug` defaults to the file stem. `kind` is `concept` | `term` | `method`.
- Keep definitions **accurate and non-fabricated** — these are glossary entries,
  not corpus claims. Cite specifics to a source where relevant.
- A malformed file is logged and skipped, never aborting the build.
