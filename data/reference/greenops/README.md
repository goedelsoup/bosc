# GreenOps — Anthropic Admin usage & cost

The model-provider slice of Watermark's own compute footprint (epic #1076, #1078): the
organization's Anthropic **Admin** usage and cost reports, reduced to token totals + USD cost
over a trailing window and attributed **by model** and **by workspace**.

Regenerate with `watermark greenops anthropic --write` (needs `ANTHROPIC_ADMIN_KEY`, an Admin
API key `sk-ant-admin01-…` distinct from the inference `ANTHROPIC_API_KEY`). Raw responses
cache under `data/cache/greenops/` (git-ignored); this committed YAML is regenerable.

## Source & discipline

- `anthropic-usage.yaml` — pulled from `/v1/organizations/usage_report/messages`
  (`group_by=model,workspace_id`) and `/v1/organizations/cost_report`
  (`group_by=workspace_id,description`), both at daily granularity, paginated.
- Every figure is `source: reference` — an authoritative usage/billing export, **not** a
  metered fact about our own consumption. Nothing here is `connector`-`verified`.
- **No inference count.** The Messages Usage Report exposes token aggregates and
  `web_search_requests` only — there is no per-request/message count. The `/about/sustainability`
  "AI inferences run" headline is therefore derived downstream (#4/#1083), never metered here.
