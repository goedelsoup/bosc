"""GreenOps connectors — per-source billing/usage pulls (#1078-#1082).

Pure-sync ``fn(..., settings) -> pydantic`` pulls (AWS Cost Explorer + Customer Carbon
Footprint Tool, Anthropic Admin usage, GitHub Actions, EPA eGRID) that reuse the neutral
``watermark.connectors`` cache/offline/fixture machinery (``cached_get``) pointed at
``settings.greenops_cache_dir`` — so tests stay hermetic and an offline miss raises an
actionable :class:`GreenopsOfflineError` naming the key to record. Credentials come from
``settings`` (AWS SDK names, ``anthropic_admin_key``), excluded from the cache key and added
only in the live fetch, mirroring the EIA connector template.

Landed: the Anthropic Admin usage/cost connector (#1078), the AWS Cost Explorer +
Sustainability (CCFT successor) connector (#1079), and the EPA eGRID subregion-factor +
WUE benchmark connector (#1082 — the derivation's ``reference`` factor tables). GitHub follows.
"""

from __future__ import annotations

from watermark.connectors import OfflineError


class GreenopsOfflineError(OfflineError):
    """Offline mode needs a GreenOps connector cache/fixture entry that is missing.

    The subsystem-flavored :class:`~watermark.connectors.OfflineError` so callers can catch a
    GreenOps offline miss precisely (mirrors ``HydroOfflineError`` / ``ImageryOfflineError``).
    """


from watermark.greenops.connectors.anthropic import (  # noqa: E402  (after the error class)
    AnthropicAdminError,
    AnthropicUsageByModel,
    AnthropicUsageByWorkspace,
    AnthropicUsageReport,
    build_usage_report,
    fetch_anthropic_usage,
    load_anthropic_usage,
    write_anthropic_usage,
)
from watermark.greenops.connectors.aws import (  # noqa: E402  (after the error class)
    AwsCredentialsError,
    build_carbon_report,
    build_cost_report,
    fetch_aws_carbon,
    fetch_aws_costs,
    load_aws_carbon,
    load_aws_costs,
    write_aws_carbon,
    write_aws_costs,
)
from watermark.greenops.connectors.egrid import (  # noqa: E402  (after the error class)
    EgridFormatError,
    build_egrid_factors,
    build_wue_table,
    fetch_egrid_factors,
    load_egrid_factors,
    load_wue_table,
    write_egrid_factors,
    write_wue_table,
)
from watermark.greenops.connectors.github import (  # noqa: E402  (after the error class)
    GithubBillingError,
    build_github_usage_report,
    fetch_github_usage,
    load_github_usage,
    write_github_usage,
)

__all__ = [
    "AnthropicAdminError",
    "AnthropicUsageByModel",
    "AnthropicUsageByWorkspace",
    "AnthropicUsageReport",
    "AwsCredentialsError",
    "EgridFormatError",
    "GithubBillingError",
    "GreenopsOfflineError",
    "build_carbon_report",
    "build_cost_report",
    "build_egrid_factors",
    "build_github_usage_report",
    "build_usage_report",
    "build_wue_table",
    "fetch_anthropic_usage",
    "fetch_aws_carbon",
    "fetch_aws_costs",
    "fetch_egrid_factors",
    "fetch_github_usage",
    "load_anthropic_usage",
    "load_aws_carbon",
    "load_aws_costs",
    "load_egrid_factors",
    "load_github_usage",
    "load_wue_table",
    "write_anthropic_usage",
    "write_aws_carbon",
    "write_aws_costs",
    "write_egrid_factors",
    "write_github_usage",
    "write_wue_table",
]
