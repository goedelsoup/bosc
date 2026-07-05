# GreenOps — provider usage, cost & carbon exports

The raw-source slice of Watermark's own compute footprint (epic #1076): per-provider
usage/billing/carbon exports, reduced to provenanced totals over a trailing window. Raw
API responses cache under `data/cache/greenops/` (git-ignored); every committed YAML here
is regenerable via its `watermark greenops <source> --write` subcommand.

Every figure in every artifact is `source: reference` — an authoritative provider export,
**not** a metered fact about our own consumption. Nothing here is `connector`-`verified`;
the modeled derivation (kWh, water) happens downstream in `footprint.py` (#1083).

## Anthropic (`anthropic-usage.yaml`, #1078)

- Pulled from `/v1/organizations/usage_report/messages` (`group_by=model,workspace_id`)
  and `/v1/organizations/cost_report` (`group_by=workspace_id,description`), both at
  daily granularity, paginated. Regenerate with `watermark greenops anthropic --write`
  (needs `ANTHROPIC_ADMIN_KEY`, an Admin API key `sk-ant-admin01-…` distinct from the
  inference `ANTHROPIC_API_KEY`).
- **No inference count.** The Messages Usage Report exposes token aggregates and
  `web_search_requests` only — there is no per-request/message count. The
  `/about/sustainability` "AI inferences run" headline is therefore derived downstream
  (#4/#1083), never metered here.

### Per-task workspaces (usage attribution, #1080)

The Admin usage report groups `by_workspace`. To turn that into the "AI · by task type"
donut (upgrading it from a modeled `assumption` to a `connector` figure, #1083), route each
pipeline stage through a **distinct Anthropic API key bound to its own workspace**, so a
workspace maps 1:1 to a task. The task taxonomy is `watermark.tasks.PipelineTask`.

Provisioning (one-time, in the [Anthropic Console](https://console.anthropic.com/) →
**Workspaces**):

1. Create one workspace per task — suggested names **Extraction**, **Corroboration**,
   **Ask**, **Drafting** — and mint a workspace-scoped API key in each.
2. Set the backend keys in the deploy environment (resolver:
   `Settings.anthropic_key_for`, fallback: `ANTHROPIC_API_KEY`):
   - `WATERMARK_ANTHROPIC_KEY_EXTRACT` → Extraction (`watermark.agent.extractor`, the
     `watermark extract` / civic-summarize reads)
   - `WATERMARK_ANTHROPIC_KEY_DRAFT` → Drafting (the research-run distill pass)
   - `WATERMARK_ANTHROPIC_KEY_ASK` → Ask (the in-process `ResearchAgent`: `sweep`,
     `research`, the analyze `research_question`)
   - `WATERMARK_ANTHROPIC_KEY_CORROBORATE` → Corroboration (reserved for the live
     self-correcting reconcile/repair pass, #40 — no live caller yet)
3. Set the **public Search & Ask** key on the Cloudflare Worker, not here: the
   `/api/ask` call runs in `web/functions/api/ask.ts`, so bind the **Ask** workspace key
   as the Worker's `ANTHROPIC_API_KEY` secret (`wrangler secret put ANTHROPIC_API_KEY`).

Any key left unset falls back to `ANTHROPIC_API_KEY`, so a single-key deploy keeps working —
the by-task split just collapses onto the default workspace until the keys are provisioned.
Keys are handed to the SDK explicitly (the extractor's client, the Agent SDK subprocess
`env`); they are never logged and never part of a cache key.

## AWS (`aws-costs.yaml` + `aws-carbon.yaml`, #1079)

Regenerate both with `watermark greenops aws --write` (needs `AWS_ACCESS_KEY_ID` /
`AWS_SECRET_ACCESS_KEY` with `ce:GetCostAndUsage` +
`sustainability:GetEstimatedCarbonEmissions`; both endpoints are us-east-1).

- `aws-costs.yaml` — Cost Explorer (`ce:GetCostAndUsage`), monthly granularity, grouped
  by SERVICE + USAGE_TYPE, `UnblendedCost` + `UsageQuantity`, paginated. Dollars are
  folded into the platform-function taxonomy (hosting / ingestion / search /
  ai_inference / storage) by a declared service map; unmapped services land in `other`,
  never dropped. Group values are read by name via the response's own
  `GroupDefinitions`, never by index.
- `aws-carbon.yaml` — the AWS Sustainability API
  (`sustainability:GetEstimatedCarbonEmissions`), the Customer Carbon Footprint Tool's
  successor (CCFT retired 2026-06-30). Market- and location-based-method totals plus the
  monthly series, in MTCO2e.
- **Gaps:** AWS publishes **no electricity/kWh figure** — the derived electricity number
  is calibrated against the location-based emissions total via grid intensity in
  `footprint.py` (#1082/#1083), never read from this export. Emissions data lags roughly
  **three months** behind the calendar (the CCFT's documented lag, carried over), so the
  monthly series ends at AWS's latest published month, not the request window's end.
