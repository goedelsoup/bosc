"""GitHub Actions/storage billing connector — the CI-compute half of GreenOps (#1081).

Pulls the organization's **enhanced billing** usage report —
``/organizations/{org}/settings/billing/usage`` — through the shared
``watermark.connectors.cached_get`` cache/offline/fixture machinery, and reduces it to a
:class:`GithubUsageReport`: the metered **Actions minutes** (CI compute → feeds the
ingestion/CI vCPU-hrs derivation, #1083) split by runner SKU, plus **Git LFS / Packages /
shared storage** GB-hours, plus net USD — over a trailing window.

**The window.** The enhanced-billing endpoint reports one calendar month at a time
(``?year=&month=``), so the live fetch walks every month in ``[starting_at, ending_at)``
and merges the ``usageItems`` into one payload — the merged blob is what lands in the
cache/fixture (the same "merge across pages, cache the whole window" shape as the AWS and
Anthropic connectors).

**Auth.** The existing ``settings.github_token`` (``GITHUB_TOKEN`` — a token with
organization billing access: an org owner/billing manager, or a fine-grained token with
"Administration" org permissions read), **excluded from the cache key** (a secret must never
vary the key or land in a committed fixture) and sent only on the live request. A missing
token or a non-2xx billing response (e.g. a 403 from insufficient permissions) ⇒
:class:`GithubBillingError`; the caller (the greenops assembly) degrades the GitHub source
to a modeled assumption rather than crashing. The org login comes from
``settings.github_billing_org``.

**Discipline.** Every figure is ``reference`` — an authoritative billing/usage export, not
a metered fact about our own consumption (:meth:`ProvenancedValue.from_reference`;
``verified`` is False). The category taxonomy (ci_compute / storage / other) is our declared
classification of GitHub's product dimension; the dollars and minutes underneath stay a
billing export.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, cast

import httpx
import yaml

from watermark.config import Settings, get_settings
from watermark.connectors import cached_get
from watermark.greenops.model import (
    GithubRunnerMinutes,
    GithubStorageProduct,
    GithubUsageLine,
    GithubUsageReport,
    GreenopsPeriod,
    period_from_window,
)
from watermark.hydrology.model import ProvenancedValue
from watermark.logging import get_logger

from . import GreenopsOfflineError
from ._readme import write_reference_readme

log = get_logger(__name__)

_GH_ACCEPT = "application/vnd.github+json"
_GH_API_VERSION = "2022-11-28"


class GithubBillingError(RuntimeError):
    """The GitHub billing API could not be queried live — most often a missing token.

    Raised on the live path when ``settings.github_token`` is empty (a bare live pull would
    401), so the caller degrades the GitHub source to a modeled assumption with a clear
    reason rather than a cryptic HTTP error.
    """


def _months_in_window(starting_at: str, ending_at: str) -> list[tuple[int, int]]:
    """The ``(year, month)`` pairs the window spans (``ending_at`` exclusive).

    Matches the trailing-12-months window the other GreenOps connectors use: for
    ``[2025-07-01, 2026-07-01)`` this is Jul 2025 … Jun 2026, twelve months.
    """
    start = datetime.fromisoformat(starting_at.replace("Z", "+00:00"))
    end = datetime.fromisoformat(ending_at.replace("Z", "+00:00"))
    months: list[tuple[int, int]] = []
    year, month = start.year, start.month
    while (year, month) < (end.year, end.month):
        months.append((year, month))
        month += 1
        if month > 12:
            month, year = 1, year + 1
    return months


def _fetch_usage(starting_at: str, ending_at: str, settings: Settings) -> dict[str, Any]:
    """Fetch the enhanced-billing usage report over the window, merged month-by-month.

    The token is deliberately absent from ``key_params`` (the cache key) and added only
    inside the live ``fetch``; the merged multi-month ``usageItems`` is what lands in the
    cache/fixture.
    """
    org = settings.github_billing_org
    key_params: dict[str, Any] = {
        "report": "usage",
        "org": org,
        "starting_at": starting_at,
        "ending_at": ending_at,
    }

    def fetch() -> Any:
        if not settings.github_token:
            raise GithubBillingError(
                "no GITHUB_TOKEN set; the enhanced-billing usage report "
                "(/organizations/{org}/settings/billing/usage) needs a token with "
                "organization billing access — an org owner or billing manager, or a "
                "fine-grained token with 'Administration' organization permissions (read)"
            )
        headers = {
            "Accept": _GH_ACCEPT,
            "Authorization": f"Bearer {settings.github_token}",
            "X-GitHub-Api-Version": _GH_API_VERSION,
        }
        url = f"{settings.github_base_url}/organizations/{org}/settings/billing/usage"
        items: list[dict[str, Any]] = []
        for year, month in _months_in_window(starting_at, ending_at):
            resp = httpx.get(
                url,
                params={"year": year, "month": month},
                headers=headers,
                timeout=settings.greenops_request_timeout_s,
            )
            # Wrap a non-2xx as GithubBillingError so an auth/permission failure degrades the
            # source to a modeled assumption (the docstring's promise) instead of surfacing a
            # raw httpx.HTTPStatusError the greenops assembly won't catch.
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise GithubBillingError(
                    f"GitHub billing usage request failed ({exc.response.status_code}) for "
                    f"{year}-{month:02d}: {exc.response.text[:200]}"
                ) from exc
            items.extend(resp.json().get("usageItems") or [])
        return {"usageItems": items}

    return cast(
        "dict[str, Any]",
        cached_get(
            "github",
            key_params,
            fetch,
            cache_dir=settings.greenops_cache_dir,
            offline=settings.greenops_offline,
            fixtures_dir=settings.greenops_fixtures_dir,
            ttl_hours=settings.greenops_cache_ttl_hours,
            offline_error=GreenopsOfflineError,
        ),
    )


def _norm_unit(unit_type: str) -> str:
    """Fold a unit label to a comparison key (case/space/hyphen-insensitive)."""
    return re.sub(r"[\s_-]", "", unit_type.strip().lower())


def _categorize(product: str, unit_type: str) -> Literal["ci_compute", "storage", "other"]:
    """Our declared taxonomy bucket for a billing line.

    ``ci_compute`` = Actions minutes (the metered CI-compute input); ``storage`` = any
    GB-hours/GB line (Git LFS, Packages, Actions artifacts, shared storage); everything else
    (Copilot, Codespaces compute, …) lands in ``other`` — listed, never dropped.
    """
    product_key = product.strip().lower()
    unit_key = _norm_unit(unit_type)
    if product_key == "actions" and "minute" in unit_key:
        return "ci_compute"
    if "gigabyte" in unit_key:
        return "storage"
    return "other"


def build_github_usage_report(payload: dict[str, Any], period: GreenopsPeriod) -> GithubUsageReport:
    """Reduce the raw ``usageItems`` payload into a :class:`GithubUsageReport`.

    Pure over the payload (no I/O) so the offline fixtures exercise the real aggregation,
    categorization, and dollar sums — not a pre-reduced blob. Line items are summed by
    (product, sku, unit_type); the ci_compute minutes are re-split by runner SKU and the
    storage GB-hours by (product, unit_type).
    """
    cite = f"GitHub enhanced-billing usage ({period.label})"

    # --- accumulate per (product, sku, unit_type) across the daily line items ---
    acc: dict[tuple[str, str, str], dict[str, float]] = {}
    for item in payload.get("usageItems") or []:
        product = str(item.get("product") or "")
        sku = str(item.get("sku") or "")
        unit_type = str(item.get("unitType") or "")
        slot = acc.setdefault((product, sku, unit_type), {"qty": 0.0, "cost": 0.0})
        slot["qty"] += float(item.get("quantity") or 0)
        slot["cost"] += float(item.get("netAmount") or 0)

    def ref(value: float, unit: str) -> ProvenancedValue:
        return ProvenancedValue.from_reference(round(value, 4), unit, cite, confidence="high")

    lines = [
        GithubUsageLine(
            product=product,
            sku=sku,
            unit_type=unit_type,
            category=_categorize(product, unit_type),
            quantity=round(slot["qty"], 4),
            cost=ref(slot["cost"], "USD"),
        )
        for (product, sku, unit_type), slot in sorted(
            acc.items(), key=lambda kv: kv[1]["cost"], reverse=True
        )
    ]

    # --- Actions minutes, split by runner SKU (ci_compute lines) ---
    runner_acc: dict[str, dict[str, float]] = {}
    for line in lines:
        if line.category != "ci_compute":
            continue
        slot = runner_acc.setdefault(line.sku, {"minutes": 0.0, "cost": 0.0})
        slot["minutes"] += line.quantity
        slot["cost"] += line.cost.value
    by_runner = [
        GithubRunnerMinutes(
            sku=sku,
            label=sku,
            minutes=ref(slot["minutes"], "minutes"),
            cost=ref(slot["cost"], "USD"),
        )
        for sku, slot in sorted(runner_acc.items(), key=lambda kv: kv[1]["minutes"], reverse=True)
    ]

    # --- storage, grouped by (product, unit_type) so units are never mixed ---
    storage_acc: dict[tuple[str, str], dict[str, float]] = {}
    for line in lines:
        if line.category != "storage":
            continue
        slot = storage_acc.setdefault((line.product, line.unit_type), {"qty": 0.0, "cost": 0.0})
        slot["qty"] += line.quantity
        slot["cost"] += line.cost.value
    storage = [
        GithubStorageProduct(
            product=product,
            label=product,
            unit_type=unit_type,
            quantity=ref(slot["qty"], unit_type),
            cost=ref(slot["cost"], "USD"),
        )
        for (product, unit_type), slot in sorted(
            storage_acc.items(), key=lambda kv: kv[1]["cost"], reverse=True
        )
    ]

    total_minutes = sum(r.minutes.value for r in by_runner)
    total_cost = sum(line.cost.value for line in lines)

    return GithubUsageReport(
        period=period,
        total_minutes=ref(total_minutes, "minutes"),
        total_cost=ref(total_cost, "USD"),
        by_runner=by_runner,
        storage=storage,
        lines=lines,
        note=(
            "GitHub enhanced-billing usage (/organizations/{org}/settings/billing/usage) "
            "over the window, one calendar month per request, merged. Figures are "
            "`reference` (a billing export), not metered facts. Categories (ci_compute = "
            "Actions minutes, storage = Git LFS / Packages / shared storage GB-hours, other) "
            "are our declared classification of GitHub's product dimension — unmapped "
            "products land in `other`, never dropped. Quantity units vary per line and must "
            "not be summed across lines of differing units."
        ),
    )


def fetch_github_usage(
    starting_at: str,
    ending_at: str,
    *,
    settings: Settings | None = None,
) -> GithubUsageReport:
    """Pull + reduce the enhanced-billing usage report over ``[starting_at, ending_at)`` (cached).

    ``starting_at`` / ``ending_at`` are RFC 3339 timestamps (``ending_at`` exclusive),
    matching the other GreenOps connectors; the fetch walks the whole-month grid the API
    exposes. An offline cache/fixture miss raises :class:`GreenopsOfflineError` naming the key.
    """
    settings = settings or get_settings()
    payload = _fetch_usage(starting_at, ending_at, settings)
    return build_github_usage_report(payload, period_from_window(starting_at, ending_at))


# --- committed reference artifact (data/reference/greenops/github-usage.yaml) ---------------

_REFERENCE_RELPATH = Path("reference") / "greenops" / "github-usage.yaml"


def write_github_usage(report: GithubUsageReport, *, settings: Settings | None = None) -> Path:
    """Persist the report as committed reference YAML + the shared README; return the YAML path."""
    settings = settings or get_settings()
    out = settings.data_dir / _REFERENCE_RELPATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    write_reference_readme(out.parent)
    log.info("greenops.github.wrote", path=str(out))
    return out


def load_github_usage(path: Path) -> GithubUsageReport:
    """Load a committed :class:`GithubUsageReport` YAML."""
    return GithubUsageReport.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
