# CLAUDE.md — `bosc.site`

The static-site generator: `build.py` stages a markdown source tree under `web/`,
then `render.py` renders it to plain multipage HTML under `site/` (Python-Markdown
+ Jinja2 — no MkDocs, no theme). Defers to the root [`CLAUDE.md`](../../../CLAUDE.md).

- **`web/` and `site/` are git-ignored and fully regenerable — this package is the
  source of truth.** Never hand-edit the generated output; change the generator.
- `build.py` **wipes `web/`** then mirrors the curated `docs/` markdown + the whole
  `data/extracted/` tree at **repo-relative paths**, so existing cross-links resolve
  unchanged. Preserve that path mirroring when adding pages.
- Generated content is built **from committed corpus data** (`corpus`, `entities`,
  `timeline`, `people`, `candidates`, `exhibits`) — don't fabricate records or links.
- Exhibits are driven by [`data/site/exhibits.yaml`](../../../data/site/README.md)
  (page-range slices, never whole bundles). The sidebar nav + site metadata live
  in `nav.yaml` (`nav.py` loads it); the page shell is `templates/base.html`;
  static assets live in `assets/` (`site.css`, `extra.css`, `mermaid-init.js`).
- Deployment is **manual** (`workflow_dispatch`) — the site is an unlisted draft.
