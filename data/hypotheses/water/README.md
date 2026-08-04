# H1 · Water & Coercion

The reference thesis: hyperscale compute lands where it can pull power and water, and a
data center's intake, discharge, and downstream effects are basin facts. Lima is the
live, fully-assembled reference.

The **directory hypothesis** is rendered from the site registry (`watermark.sites.SITES`) + the
basin network (`watermark.network`), grouped by drainage — two divides, nine basins. The
primary "assessment" is the assembled hydrology itself.

## Coercion sub-thesis (#903)

A second investigative thread under H1: the Clean Water Act as a locality-acceptance
mechanism. In municipalities with declining populations, the receiving WWTP may run lean on
influent — below the biological-treatment minimum that keeps it in NPDES compliance. A
datacenter's high-volume, consistent discharge provides the flow buffer the plant needs,
structurally compelling municipal acceptance. The CWA is the backstop that makes the need
non-negotiable.

Evidence cells for this sub-thesis are committed here as `data/hypotheses/water/<site>.yaml`
with `sub_thesis: coercion`, `group: coercion`, and fields:

- `wwtp` — the receiving sanitary district / treatment plant
- `gap` — the lean-flow deficit (design vs. actual influent, from ECHO DMR), once confirmed

Cells start `tag: open` and `signal: watch` until ECHO DMR data confirms the deficit.

Backing narrative: `docs/HYDROLOGY.md`, `docs/COURSE.md`.
