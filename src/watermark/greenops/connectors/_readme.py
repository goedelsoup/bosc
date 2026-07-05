"""The one README for ``data/reference/greenops/`` — covering every connector's artifact.

Each connector's ``write_*`` regenerates its own YAML **and** this shared README, so the
folder's documentation stays whole no matter which ``--write`` ran last (a per-connector
README would clobber its siblings'). Add a section here when a new GreenOps connector
lands (#1078-#1082).
"""

from __future__ import annotations

from pathlib import Path

REFERENCE_README = """\
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

## GitHub (`github-usage.yaml`, #1081)

- Pulled from the enhanced billing platform
  `/organizations/{org}/settings/billing/usage`, one calendar month per request
  (`?year=&month=`) across the trailing window, merged. Regenerate with
  `watermark greenops github --write` (needs `GITHUB_TOKEN` with organization billing
  access — an org owner/billing manager, or a fine-grained token with "Administration" org
  permissions read; the org login is `WATERMARK_GITHUB_BILLING_ORG`).
- **Actions minutes** are the metered CI-compute input the footprint derivation (#1083)
  turns into vCPU-hrs — the runner SKU (Linux / Windows / macOS, and the multi-core
  variants) sets the core count, so minutes are split by runner. **Git LFS / Packages /
  shared storage** GB-hours are the corpus-at-rest input.
- Line items are summed by `(product, sku, unit_type)` and folded into a small category
  taxonomy (`ci_compute` = Actions minutes, `storage` = any GB-hours/GB line, `other` =
  Copilot / Codespaces / …); unmapped products land in `other`, never dropped. Quantity
  units vary per line and must not be summed across lines of differing units.
"""


def write_reference_readme(reference_dir: Path) -> Path:
    """(Re)write the shared ``data/reference/greenops/README.md``; return its path."""
    reference_dir.mkdir(parents=True, exist_ok=True)
    path = reference_dir / "README.md"
    path.write_text(REFERENCE_README, encoding="utf-8")
    return path
