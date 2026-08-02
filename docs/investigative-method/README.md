# Investigative method — agent skills, system prompt, and enrichment

This directory holds the **methodology layer** of Project BOSC: the standing
instructions and domain expertise that govern how an agent (and the humans
working alongside it) reason about the public record, assemble evidence, and
write defensible prose.

It was ported from the original *Project BOSC* Claude Project bundle (a system
prompt + a set of skills + a project-specific enrichment layer) and reconciled to
the artifacts that actually exist in this repository. The raw bundle was an
abstract, reusable methodology; this layer keeps the abstraction in the skills and
binds the specifics here.

## Layout

```
.claude/skills/                       # the agent-discoverable skills (tracked; see .gitignore)
  evidentiary-discipline/SKILL.md       # the master constraint; everything else defers to it
  public-records-and-legal-strategy/
  gis-and-siting-analysis/
  entity-and-document-deconstruction/
  investigative-writing-and-editorial/
  document-production-and-ocr/
docs/investigative-method/
  README.md          # this file
  SYSTEM_PROMPT.md   # candidate standing instructions for the in-app research agent
  ENRICHMENT.md      # binds the abstract skills to this repo's facts, formats, and identifiers
  STYLE-STE.md       # the impact study's writing register (Simplified Technical English)
```

## How the pieces relate

- **Skills are abstract.** Each `SKILL.md` holds reusable *methodology* only — no
  entities, no statute numbers, no format values — with YAML frontmatter (`name`,
  `description`) whose `description` is written as *when to trigger*. They live
  under `.claude/skills/` so Claude Code discovers them natively, and so the
  in-process Agent SDK research agent (`watermark.agent`) can load them via
  `setting_sources` when that wiring lands.
- **The enrichment layer is concrete.** [`ENRICHMENT.md`](ENRICHMENT.md) supplies
  the repo specifics each skill defers to — the `Provenanced` value model, the
  `EntityGraph`, the corpus-completeness audit, the `[verified]` / `[inference]`
  tag vocabulary, the legal posture. Each skill closes with a "Project enrichment"
  note pointing back here.
- **Evidentiary discipline is the spine.** Every other skill is explicitly
  subordinate to [`evidentiary-discipline`](../../.claude/skills/evidentiary-discipline/SKILL.md).
  If a writing or "make it punchier" request conflicts with it, the discipline
  wins.
- **The system prompt** ([`SYSTEM_PROMPT.md`](SYSTEM_PROMPT.md)) is the standing
  posture the skills assume. It is the candidate replacement for the terse
  `DEFAULT_SYSTEM_PROMPT` in `watermark.agent.client` — see "In-app integration" below.

## How this maps onto the repo

The skills are abstract, but the repo already implements most of what they
describe. The enrichment layer documents the mapping in full; the short version:

| Skill | Lives in this repo as |
|---|---|
| evidentiary-discipline | the `[verified]` / `[inference]` / `[reference]` / `[open]` tag vocabulary (`web/packages/core/src/evidence.ts`, `CLAUDE.md`, surfaced on the network `/methodology` hub) |
| public-records-and-legal-strategy | `docs/legal/` (`mandamus-analysis.md`, `proponent-analysis.md`) |
| gis-and-siting-analysis | `watermark.gis` + the `ProvenancedValue` model in `watermark.hydrology.model` |
| entity-and-document-deconstruction | `watermark.pipeline.entities` (`EntityGraph`) + `watermark.pipeline.timeline`; gap audit at `data/extracted/legal/corpus-completeness-audit.md` |
| investigative-writing-and-editorial | the narrative draft under `docs/` and the Astro site under `web/` |
| document-production-and-ocr | the vision-based `watermark.pipeline.extract` read path (the generic tesseract/docx recipes are fallbacks) |

## In-app integration (deferred)

The `.claude/skills/` home is deliberately the one place that serves both
audiences:

1. **Claude Code** agents working in the repo discover the skills automatically.
2. The **in-process research agent** (`watermark.agent.ResearchAgent`, an Agent SDK
   wrapper) can load the same skills via `ClaudeAgentOptions(setting_sources=[...])`
   and adopt `SYSTEM_PROMPT.md` in place of its current terse default.

That second wiring is intentionally **not** done here — it changes the agent's
runtime behavior and wants its own change, tests, and an SDK-capability check. It
is tracked under epic #323 (re-homed from the closed #247). This directory lands the
expertise; the app picks up "some skills" later.

## Adding a skill or a new investigation

- **New skill:** match the existing pattern — frontmatter `name` + a `description`
  written as *when to trigger*, methodology only in the body, and a closing
  "Project enrichment" paragraph naming what the enrichment layer must supply. Do
  not let project facts leak into a skill file.
- **New investigation:** the skills and `SYSTEM_PROMPT.md` stay put; replace
  `ENRICHMENT.md` wholesale to point the same methodology at different facts.
