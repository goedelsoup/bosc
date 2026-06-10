# `data/research/` — automated-research runs

Output of `bosc research run --topic "<topic>"` (and, later, the research GitHub
App — Epic [#57](https://github.com/goedelsoup/bosc/issues/57)). Each run is one
investigation over the corpus by the open-ended `ResearchAgent`
(`bosc.agent`), distilled into a reviewable **issue-proposal manifest**.

## Layout

```
data/research/<topic-slug>-<YYYY-MM-DD>/
  findings.md     # the agent's prose report (provenance header + citation-grounded findings)
  manifest.yaml   # meta/provenance + cost, and the structured issue proposals
```

`manifest.yaml` proposals carry the process labels `agent-proposed` + `needs-triage`
(inert until a maintainer triages them) and a stable `dedupe_key` so a later run does
not re-propose the same follow-up.

## Discipline

- **Read-only on the corpus.** A run reads `data/documents/**` through the read-only
  agent tools and **never alters a source byte**; it writes only here. `write_run`
  refuses to write under `data/documents/`.
- **Reviewed, not authoritative.** These artifacts are *agent-proposed*. They land on
  a branch / PR that a human (`goedelsoup`) verifies before anything is acted on — the
  App cannot approve or merge its own PR.
- **Regenerable.** A run is reproducible from its `topic` + corpus state; the prose
  may vary, but the provenance records the model, turns, tools, and cost.
