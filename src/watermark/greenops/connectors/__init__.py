"""GreenOps connectors — per-source billing/usage pulls (#1078-#1082).

Pure-sync ``fn(..., settings) -> pydantic`` pulls (AWS Cost Explorer + Customer Carbon
Footprint Tool, Anthropic Admin usage, GitHub Actions, EPA eGRID) that reuse the neutral
``watermark.connectors`` cache/offline/fixture machinery (``cached_get``) pointed at
``settings.greenops_cache_dir`` — so tests stay hermetic and an offline miss raises an
actionable :class:`GreenopsOfflineError` naming the key to record. Credentials come from
``settings`` (AWS SDK names, ``anthropic_admin_key``), excluded from the cache key and added
only in the live fetch, mirroring the EIA connector template.

Landed: the Anthropic Admin usage/cost connector (#1078) and the AWS Cost Explorer +
Sustainability (CCFT successor) connector (#1079). GitHub/eGRID follow.
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

__all__ = [
    "AnthropicAdminError",
    "AnthropicUsageByModel",
    "AnthropicUsageByWorkspace",
    "AnthropicUsageReport",
    "AwsCredentialsError",
    "GreenopsOfflineError",
    "build_carbon_report",
    "build_cost_report",
    "build_usage_report",
    "fetch_anthropic_usage",
    "fetch_aws_carbon",
    "fetch_aws_costs",
    "load_anthropic_usage",
    "load_aws_carbon",
    "load_aws_costs",
    "write_anthropic_usage",
    "write_aws_carbon",
    "write_aws_costs",
]
