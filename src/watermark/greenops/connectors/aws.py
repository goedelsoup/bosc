"""AWS cost + carbon connector — the cloud-provider half of GreenOps (#1079).

Two cached pulls through the shared GreenOps fetch helper (``_fetch.greenops_cached_get``):

1. **Cost Explorer** (``ce:GetCostAndUsage``), monthly granularity, grouped by
   SERVICE + USAGE_TYPE — dollars (``UnblendedCost``) and usage quantities
   (``UsageQuantity``), reduced to an :class:`AwsCostReport` whose dollars are folded
   into the platform-function taxonomy (hosting / ingestion / search / ai_inference /
   storage; unmapped services land in ``other``, never dropped). Group values are read
   **by name** via the response's own ``GroupDefinitions``, never by index.
2. **The AWS Sustainability API** (``sustainability:GetEstimatedCarbonEmissions``) —
   the Customer Carbon Footprint Tool's successor (CCFT retired 2026-06-30, superseded
   by the Sustainability console/API). Market- and location-based-method emissions
   totals + the monthly series, reduced to an :class:`AwsCarbonReport`. AWS publishes
   **no electricity/kWh figure**: the derived electricity number is *calibrated* against
   the location-based emissions total via grid intensity in ``footprint.py``
   (#1082/#1083), never read from here. Emissions data lags roughly three months.

**Auth.** SigV4 over httpx (:func:`watermark.connectors._sigv4.sigv4_authorization` —
the same signer as the R2 object store; still no boto3). Credentials come from
``settings.aws_access_key_id`` / ``aws_secret_access_key`` (the SDK-convention env
names), are **excluded from the cache key** (a secret must never vary the key or land in
a committed fixture), and are read only inside the live ``fetch`` — same discipline as
``economics/connectors/eia.py``. Absent credentials on the live path raise
:class:`AwsCredentialsError` so the caller degrades the AWS source to a modeled
assumption rather than crashing. Both endpoints are us-east-1.

**Discipline.** Every figure is ``reference`` — an authoritative billing/emissions
export, not a metered fact about our own consumption
(:meth:`ProvenancedValue.from_reference`; ``verified`` is False). The function taxonomy
is our declared classification of AWS's service dimension; the dollars underneath stay
a billing export.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import httpx
import yaml

from watermark.config import Settings, get_settings
from watermark.connectors._sigv4 import sigv4_authorization
from watermark.greenops.model import (
    AwsCarbonMonth,
    AwsCarbonReport,
    AwsCostReport,
    AwsFunctionCost,
    AwsUsageLine,
    GreenopsPeriod,
    SourceBasis,
    period_from_window,
)
from watermark.hydrology.model import ProvenancedValue
from watermark.logging import get_logger

from ._fetch import greenops_cached_get
from ._readme import write_reference_yaml

log = get_logger(__name__)

_CE_TARGET = "AWSInsightsIndexService.GetCostAndUsage"
_CE_METRICS = ["UnblendedCost", "UsageQuantity"]
_CE_GROUP_KEYS = ["SERVICE", "USAGE_TYPE"]
_CARBON_PATH = "/v1/estimated-carbon-emissions"
_MBM = "TOTAL_MBM_CARBON_EMISSIONS"
_LBM = "TOTAL_LBM_CARBON_EMISSIONS"

# The platform-function taxonomy (#1076): how Cost Explorer's SERVICE dimension folds into
# the by-function breakdown the sustainability page renders. A mapping is a modeling
# classification, not a billing fact — the dollars stay `reference`; anything unmapped goes
# to `other` (listed, never dropped). Keys are CE SERVICE values verbatim.
_FUNCTION_LABELS: dict[str, str] = {
    "hosting": "Hosting",
    "ingestion": "Ingestion",
    "search": "Search",
    "ai_inference": "AI inference",
    "storage": "Storage",
    "other": "Other",
}
_FUNCTION_BY_SERVICE: dict[str, str] = {
    # hosting — serving the site + running the platform
    "Amazon Elastic Compute Cloud - Compute": "hosting",
    "EC2 - Other": "hosting",
    "AWS Lambda": "hosting",
    "Amazon CloudFront": "hosting",
    "Elastic Load Balancing": "hosting",
    "Amazon API Gateway": "hosting",
    "Amazon Route 53": "hosting",
    "Amazon Lightsail": "hosting",
    # ingestion — moving/deconstructing source documents into the corpus
    "Amazon Textract": "ingestion",
    "AWS Glue": "ingestion",
    "Amazon Kinesis": "ingestion",
    "AWS Transfer Family": "ingestion",
    "Amazon Simple Queue Service": "ingestion",
    "Amazon Simple Notification Service": "ingestion",
    # search — the retrieval layer
    "Amazon OpenSearch Service": "search",
    "Amazon CloudSearch": "search",
    "Amazon Kendra": "search",
    # ai_inference — model calls
    "Amazon Bedrock": "ai_inference",
    "Amazon SageMaker": "ai_inference",
    "Amazon Comprehend": "ai_inference",
    "Amazon Rekognition": "ai_inference",
    "Amazon Transcribe": "ai_inference",
    "Amazon Translate": "ai_inference",
    # storage — the corpus + structured data at rest
    "Amazon Simple Storage Service": "storage",
    "Amazon S3 Glacier Deep Archive": "storage",
    "Amazon Glacier": "storage",
    "Amazon Elastic Block Store": "storage",
    "Amazon Elastic File System": "storage",
    "Amazon DynamoDB": "storage",
    "Amazon Relational Database Service": "storage",
}


class AwsCredentialsError(RuntimeError):
    """AWS could not be queried live — most often missing access keys.

    Raised on the live path when ``settings.aws_access_key_id`` /
    ``aws_secret_access_key`` are empty (a bare live pull would fail auth), so the caller
    degrades the AWS source to a modeled assumption with a clear reason rather than a
    cryptic HTTP error.
    """


# --- SigV4-signed transport ------------------------------------------------------------


def _signed_post(
    service: str,
    path: str,
    body: dict[str, Any],
    settings: Settings,
    *,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """POST one SigV4-signed JSON request to ``https://<service>.<region>.amazonaws.com``."""
    if not (settings.aws_access_key_id and settings.aws_secret_access_key):
        raise AwsCredentialsError(
            "no AWS credentials set; the Cost Explorer / Sustainability pull needs "
            "AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY (ce:GetCostAndUsage, "
            "sustainability:GetEstimatedCarbonEmissions)"
        )
    host = f"{service}.{settings.aws_region}.amazonaws.com"
    payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
    now = datetime.now(UTC)
    amzdate = now.strftime("%Y%m%dT%H%M%SZ")
    content_type = (
        "application/x-amz-json-1.1"
        if extra_headers and "x-amz-target" in extra_headers
        else "application/json"
    )
    headers = {
        "content-type": content_type,
        "host": host,
        "x-amz-date": amzdate,
        **(extra_headers or {}),
    }
    headers["authorization"] = sigv4_authorization(
        method="POST",
        canonical_uri=path,
        canonical_querystring="",
        headers=headers,
        payload_hash=hashlib.sha256(payload).hexdigest(),
        access_key=settings.aws_access_key_id,
        secret_key=settings.aws_secret_access_key,
        amzdate=amzdate,
        datestamp=now.strftime("%Y%m%d"),
        region=settings.aws_region,
        service=service,
    )
    resp = httpx.post(
        f"https://{host}{path}",
        content=payload,
        headers=headers,
        timeout=settings.greenops_request_timeout_s,
    )
    resp.raise_for_status()
    return cast("dict[str, Any]", resp.json())


# --- Cost Explorer ----------------------------------------------------------------------


def _fetch_cost_and_usage(
    start: str, end: str, settings: Settings
) -> tuple[dict[str, Any], SourceBasis]:
    """Fetch ``ce:GetCostAndUsage`` over ``[start, end)`` (dates), merged across pages.

    Credentials are deliberately absent from the cache-key params and read only inside
    the live ``fetch``; the merged ``ResultsByTime`` + the response's ``GroupDefinitions``
    are what land in the cache/fixture.
    """
    key_params: dict[str, Any] = {
        "report": "cost_and_usage",
        "start": start,
        "end": end,
        "granularity": "MONTHLY",
        "metrics": _CE_METRICS,
        "group_by": _CE_GROUP_KEYS,
    }

    def fetch() -> Any:
        results: list[dict[str, Any]] = []
        group_definitions: list[dict[str, Any]] = []
        token: str | None = None
        while True:
            body: dict[str, Any] = {
                "TimePeriod": {"Start": start, "End": end},
                "Granularity": "MONTHLY",
                "Metrics": _CE_METRICS,
                "GroupBy": [{"Type": "DIMENSION", "Key": k} for k in _CE_GROUP_KEYS],
            }
            if token:
                body["NextPageToken"] = token
            resp = _signed_post(
                "ce", "/", body, settings, extra_headers={"x-amz-target": _CE_TARGET}
            )
            results.extend(resp.get("ResultsByTime") or [])
            group_definitions = group_definitions or (resp.get("GroupDefinitions") or [])
            token = resp.get("NextPageToken")
            if not token:
                break
        return {"ResultsByTime": results, "GroupDefinitions": group_definitions}

    return greenops_cached_get("aws", key_params, fetch, settings)


def build_cost_report(
    payload: dict[str, Any], period: GreenopsPeriod, *, basis: SourceBasis = "illustrative"
) -> AwsCostReport:
    """Reduce the raw ``GetCostAndUsage`` payload into an :class:`AwsCostReport`.

    Pure over the payload (no I/O) so the offline fixtures exercise the real reduction.
    Group values are resolved **by name** by zipping the response's own
    ``GroupDefinitions`` with each group's ``Keys`` — never by hardcoded position.
    ``basis`` is the caller's finding about the payload's origin (#1643/F3), defaulting to
    ``illustrative`` so an unattributed payload never reads as a real pull.
    """
    cite = f"AWS Cost Explorer GetCostAndUsage ({period.label})"
    group_names = [d.get("Key", "") for d in payload.get("GroupDefinitions") or []]

    # --- accumulate per (service, usage_type) across the monthly buckets ---
    acc: dict[tuple[str, str], dict[str, Any]] = {}
    for bucket in payload.get("ResultsByTime") or []:
        for group in bucket.get("Groups") or []:
            named = dict(zip(group_names, group.get("Keys") or [], strict=False))
            service = str(named.get("SERVICE", ""))
            usage_type = str(named.get("USAGE_TYPE", ""))
            metrics = group.get("Metrics") or {}
            cost = float((metrics.get("UnblendedCost") or {}).get("Amount") or 0)
            usage = float((metrics.get("UsageQuantity") or {}).get("Amount") or 0)
            unit = str((metrics.get("UsageQuantity") or {}).get("Unit") or "")
            slot = acc.setdefault((service, usage_type), {"cost": 0.0, "usage": 0.0, "unit": unit})
            slot["cost"] += cost
            slot["usage"] += usage

    def dollars(v: float) -> float:
        return round(v, 2)

    lines = [
        AwsUsageLine(
            service=service,
            usage_type=usage_type,
            function=_FUNCTION_BY_SERVICE.get(service, "other"),
            cost=ProvenancedValue.from_reference(
                dollars(slot["cost"]), "USD", cite, confidence="high"
            ),
            usage_amount=slot["usage"],
            usage_unit=slot["unit"],
        )
        for (service, usage_type), slot in sorted(
            acc.items(), key=lambda kv: kv[1]["cost"], reverse=True
        )
    ]

    # --- fold into the function taxonomy (unmapped services land in `other`) ---
    cost_by_function: dict[str, float] = {}
    cost_by_service: dict[str, float] = {}
    for (service, _), slot in acc.items():
        function = _FUNCTION_BY_SERVICE.get(service, "other")
        cost_by_function[function] = cost_by_function.get(function, 0.0) + slot["cost"]
        cost_by_service[service] = cost_by_service.get(service, 0.0) + slot["cost"]
    by_function = [
        AwsFunctionCost(
            function=function,
            label=_FUNCTION_LABELS[function],
            cost=ProvenancedValue.from_reference(dollars(total), "USD", cite, confidence="high"),
            services=sorted(
                {s for s in cost_by_service if _FUNCTION_BY_SERVICE.get(s, "other") == function},
                key=lambda s: cost_by_service[s],
                reverse=True,
            ),
        )
        for function, total in sorted(cost_by_function.items(), key=lambda kv: kv[1], reverse=True)
    ]

    return AwsCostReport(
        period=period,
        total_cost=ProvenancedValue.from_reference(
            dollars(sum(cost_by_function.values())), "USD", cite, confidence="high"
        ),
        by_function=by_function,
        lines=lines,
        basis=basis,
        note=(
            "AWS Cost Explorer GetCostAndUsage over the window, monthly granularity, grouped "
            "by SERVICE + USAGE_TYPE (values read by name via the response's "
            "GroupDefinitions). Dollars are `reference` (a billing export); the function "
            "taxonomy is our declared mapping of AWS services — unmapped services land in "
            "`other`, never dropped. Usage units vary per line and must not be summed "
            "across lines."
        ),
    )


def fetch_aws_costs(
    starting_at: str,
    ending_at: str,
    *,
    settings: Settings | None = None,
) -> AwsCostReport:
    """Pull + reduce Cost Explorer over ``[starting_at, ending_at)`` (cached).

    ``starting_at`` / ``ending_at`` are RFC 3339 timestamps (``ending_at`` exclusive),
    matching the other GreenOps connectors; Cost Explorer itself takes their date parts.
    An offline cache/fixture miss raises :class:`GreenopsOfflineError` naming the key.
    """
    settings = settings or get_settings()
    payload, basis = _fetch_cost_and_usage(starting_at[:10], ending_at[:10], settings)
    return build_cost_report(payload, period_from_window(starting_at, ending_at), basis=basis)


# --- Sustainability (the CCFT successor) ------------------------------------------------


def _fetch_carbon(
    starting_at: str, ending_at: str, settings: Settings
) -> tuple[dict[str, Any], SourceBasis]:
    """Fetch ``GetEstimatedCarbonEmissions`` over the window, merged across pages."""
    key_params: dict[str, Any] = {
        "report": "estimated_carbon_emissions",
        "starting_at": starting_at,
        "ending_at": ending_at,
        "granularity": "MONTHLY",
        "emissions_types": [_LBM, _MBM],
    }

    def fetch() -> Any:
        results: list[dict[str, Any]] = []
        token: str | None = None
        while True:
            body: dict[str, Any] = {
                "TimePeriod": {"Start": starting_at, "End": ending_at},
                "Granularity": "MONTHLY",
                "EmissionsTypes": [_LBM, _MBM],
                "MaxResults": 5000,
            }
            if token:
                body["NextToken"] = token
            resp = _signed_post("sustainability", _CARBON_PATH, body, settings)
            results.extend(resp.get("Results") or [])
            token = resp.get("NextToken")
            if not token:
                break
        return {"Results": results}

    return greenops_cached_get("aws", key_params, fetch, settings)


def build_carbon_report(
    payload: dict[str, Any], period: GreenopsPeriod, *, basis: SourceBasis = "illustrative"
) -> AwsCarbonReport:
    """Reduce the raw ``GetEstimatedCarbonEmissions`` payload into an :class:`AwsCarbonReport`.

    Pure over the payload. Emissions values are read **by name** from each result's
    ``EmissionsValues`` map; the unit comes from the payload (MTCO2e), not hardcoded.
    ``basis`` is the caller's finding about the payload's origin (#1643/F3).
    """
    cite = f"AWS Sustainability GetEstimatedCarbonEmissions ({period.label})"

    def emission(result: dict[str, Any], emissions_type: str) -> tuple[float, str]:
        entry = (result.get("EmissionsValues") or {}).get(emissions_type) or {}
        return float(entry.get("Value") or 0), str(entry.get("Unit") or "MTCO2e")

    def ref(value: float, unit: str) -> ProvenancedValue:
        return ProvenancedValue.from_reference(round(value, 6), unit, cite, confidence="high")

    months: list[AwsCarbonMonth] = []
    mbm_total = lbm_total = 0.0
    unit = "MTCO2e"
    versions: list[str] = []
    for result in sorted(
        payload.get("Results") or [], key=lambda r: str((r.get("TimePeriod") or {}).get("Start"))
    ):
        start = str((result.get("TimePeriod") or {}).get("Start") or "")
        mbm, unit = emission(result, _MBM)
        lbm, _ = emission(result, _LBM)
        mbm_total += mbm
        lbm_total += lbm
        version = str(result.get("ModelVersion") or "")
        if version and version not in versions:
            versions.append(version)
        months.append(
            AwsCarbonMonth(
                month=start[:7], mbm_emissions=ref(mbm, unit), lbm_emissions=ref(lbm, unit)
            )
        )

    return AwsCarbonReport(
        period=period,
        mbm_total=ref(mbm_total, unit),
        lbm_total=ref(lbm_total, unit),
        monthly=months,
        model_version="+".join(versions),
        basis=basis,
        note=(
            "AWS Sustainability GetEstimatedCarbonEmissions (the Customer Carbon Footprint "
            "Tool's successor; CCFT retired 2026-06-30) over the window, monthly granularity, "
            "market- + location-based methods. Figures are `reference` (AWS's own estimate), "
            "not metered. AWS publishes no electricity/kWh figure — the derived electricity "
            "number is calibrated against lbm_total via grid intensity in footprint.py "
            "(#1082/#1083). Emissions data lags ~3 months; the monthly series ends at AWS's "
            "latest published month."
        ),
    )


def fetch_aws_carbon(
    starting_at: str,
    ending_at: str,
    *,
    settings: Settings | None = None,
) -> AwsCarbonReport:
    """Pull + reduce the AWS emissions estimate over ``[starting_at, ending_at)`` (cached)."""
    settings = settings or get_settings()
    payload, basis = _fetch_carbon(starting_at, ending_at, settings)
    return build_carbon_report(payload, period_from_window(starting_at, ending_at), basis=basis)


# --- committed reference artifacts (data/reference/greenops/aws-*.yaml) -----------------

_COSTS_RELPATH = Path("reference") / "greenops" / "aws-costs.yaml"
_CARBON_RELPATH = Path("reference") / "greenops" / "aws-carbon.yaml"


def _write_yaml(out: Path, report: AwsCostReport | AwsCarbonReport) -> Path:
    return write_reference_yaml(out, report, log=log, event="greenops.aws.wrote")


def write_aws_costs(report: AwsCostReport, *, settings: Settings | None = None) -> Path:
    """Persist the cost report as committed reference YAML + the shared README."""
    settings = settings or get_settings()
    return _write_yaml(settings.data_dir / _COSTS_RELPATH, report)


def write_aws_carbon(report: AwsCarbonReport, *, settings: Settings | None = None) -> Path:
    """Persist the carbon report as committed reference YAML + the shared README."""
    settings = settings or get_settings()
    return _write_yaml(settings.data_dir / _CARBON_RELPATH, report)


def load_aws_costs(path: Path) -> AwsCostReport:
    """Load a committed :class:`AwsCostReport` YAML."""
    return AwsCostReport.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def load_aws_carbon(path: Path) -> AwsCarbonReport:
    """Load a committed :class:`AwsCarbonReport` YAML."""
    return AwsCarbonReport.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
