"""EPA ECHO discharge-monitoring-report (DMR) / effluent-chart connector.

Where :mod:`watermark.hydrology.connectors.echo` pulls the *inventory* of CWA-permitted
facilities (one row per facility, from ``cwa_rest_services``), this connector pulls the
**reported effluent record** for a single NPDES permit from ECHO's effluent-chart service
(``eff_rest_services.get_effluent_chart``): every permitted feature (outfall), every
monitored parameter, and the monthly Discharge Monitoring Report (DMR) values the
permittee submitted, with their limits.

It exists to answer the two questions the inventory cannot: what does the plant
*actually* discharge (vs. its permitted design flow), and which parameter — if any — is
behind an effluent compliance flag. Both come straight from the permittee's own DMRs.

Call pattern (mirrors the documented ECHO flow, one request per permit + window):

* ``get_effluent_chart`` (``p_id``, ``start_date``, ``end_date``) returns the permit's
  features → parameters → DMR rows as JSON.

Every response is recorded through :func:`_cache.cached_get` so a rerun never re-fetches
and tests stay offline. Figures and identifiers are taken verbatim from the API; this
module never fabricates or infers a value the API did not return — a ``None`` DMR value
stays ``None`` (ECHO uses a no-data-indicator code, ``NODICode``, for a period with no
discharge / no monitoring), and a parameter is flagged as exceeding its limit only where
ECHO itself reports a positive ``ExceedencePct`` — never computed by comparing value to
limit here.

Synchronous (``httpx.Client``) to match BOSC's otherwise-sync pipeline layer.
"""

from __future__ import annotations

import time
from datetime import date
from typing import Any, cast

import httpx
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.hydrology.connectors._cache import cached_get
from watermark.hydrology.units import mgd_to_cfs
from watermark.logging import get_logger

log = get_logger(__name__)

# NPDES parameter codes we care about for a receiving-water characterization.
FLOW_PARAM = "50050"  # "Flow, in conduit or thru treatment plant" (the effluent flow, MGD)
OVERFLOW_PARAM = "74063"  # "Overflow volume [SSO volume, CSO volume]" (a CSO/bypass outfall)
# ECHO returns multiple stat-base rows per period (e.g. "MO AVG" and "DAILY MX"). Only the
# monthly-average series is meaningful for the mean-flow / utilisation computation; mixing in
# daily-max rows inflates both the mean and n_flow_months.
_MONTHLY_AVG_STAT = "MO AVG"

_EFF_SERVICE = "eff_rest_services"
# Three-letter month tokens ECHO returns in MonitoringPeriodEndDate ("31-JAN-23").
_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}  # fmt: skip


class EchoDmrError(RuntimeError):
    """ECHO returned an Error object or an unparseable effluent chart."""


def _s(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _f(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _iso_period(token: str | None) -> str | None:
    """Convert ECHO's ``DD-MON-YY`` monitoring-period end to an ISO ``YYYY-MM-DD``.

    ECHO emits a two-digit year; the DMR record is recent, so ``YY`` maps to ``20YY``
    (the service has no pre-2000 effluent charts). Returns ``None`` if unparseable.
    """
    if not token:
        return None
    parts = token.strip().upper().split("-")
    if len(parts) != 3 or parts[1] not in _MONTHS:
        return None
    try:
        day = int(parts[0])
        year = 2000 + int(parts[2])
        return date(year, _MONTHS[parts[1]], day).isoformat()
    except ValueError:
        return None


# ----------------------------------------------------------------------- models


class DmrRow(BaseModel):
    """One reported Discharge Monitoring Report value for a parameter + monitoring period.

    Values are passed through verbatim. ``value`` is ``None`` when ECHO carries a
    no-data-indicator (``nodi``) instead of a number (e.g. a period with no discharge).
    ``exceedance_pct`` is populated only when ECHO itself reports an exceedance.
    """

    model_config = ConfigDict(extra="forbid")

    period_end: str | None  # ISO date (converted from ECHO's DD-MON-YY)
    value: float | None
    unit: str | None
    qualifier: str | None  # "=", "<", ...
    stat_base: str | None  # ECHO StatisticalBaseShortDesc/Desc (e.g. "Monthly Average")
    limit: float | None
    limit_type: str | None  # ECHO LimitValueTypeDesc (Quantity1, Concentration1, ...)
    exceedance_pct: float | None
    nodi: str | None  # no-data-indicator code (non-null => no value reported)


class DmrParameter(BaseModel):
    """A monitored parameter at one permitted feature (outfall), with its DMR series."""

    model_config = ConfigDict(extra="forbid")

    outfall: str  # PermFeatureNmbr, e.g. "001"
    outfall_type: str | None  # PermFeatureTypeDesc, e.g. "External Outfall"
    parameter_code: str  # NPDES parameter code, e.g. "50050"
    parameter_desc: str | None
    monitoring_location: str | None  # e.g. "Effluent Gross"
    rows: list[DmrRow]


class EffluentChart(BaseModel):
    """A permit's reported effluent record over a window (ECHO ``get_effluent_chart``)."""

    model_config = ConfigDict(extra="forbid")

    npdes_id: str
    name: str | None
    permit_type: str | None
    permit_status: str | None  # CWPPermitStatusDesc, e.g. "Admin Continued"
    major_minor: str | None  # "M" / "N"
    snc_status: str | None  # CWPCurrentSNCStatus — the facility compliance label
    start_date: str  # ISO
    end_date: str  # ISO
    parameters: list[DmrParameter]

    def series(self, parameter_code: str) -> list[DmrParameter]:
        """Every (outfall) parameter matching ``parameter_code``."""
        return [p for p in self.parameters if p.parameter_code == parameter_code]


class DischargeSummary(BaseModel):
    """The computed receiving-water read on a permit's effluent record.

    ``actual_flow_*`` reduce the primary outfall's reported monthly flow (parameter
    50050). ``exceedances`` are only the DMR rows ECHO flagged (``ExceedencePct`` or an
    attached violation) — an empty list means the reported record shows no exceedance in
    the window, which is itself a finding, never silently treated as "unknown".
    """

    model_config = ConfigDict(extra="forbid")

    npdes_id: str
    name: str | None
    window: str  # "YYYY-MM-DD..YYYY-MM-DD"
    design_flow_mgd: float | None
    primary_outfall: str | None
    n_flow_months: int
    actual_flow_mean_mgd: float | None
    actual_flow_min_mgd: float | None
    actual_flow_max_mgd: float | None
    flow_pct_of_design: float | None  # mean actual / design, %
    cso_outfalls: int  # count of features carrying an overflow-volume parameter
    snc_status: str | None
    exceedances: list[DmrRow]


# --------------------------------------------------------------------- fetch + parse


def _get(settings: Settings, service: str, params: dict[str, Any]) -> dict[str, Any]:
    """Perform (or replay from cache) one ECHO ``eff_rest_services`` request; return Results."""
    query = {"output": "JSON", **params}

    def fetch() -> Any:
        url = f"{settings.echo_base_url}/{_EFF_SERVICE}.{service}"
        for attempt in range(settings.echo_max_retries):
            resp = httpx.get(url, params=query, timeout=settings.hydro_request_timeout_s)
            if resp.status_code == 429 and attempt < settings.echo_max_retries - 1:
                wait = settings.echo_retry_base_s * (2**attempt)
                log.info("echo_dmr.throttled", service=service, attempt=attempt, wait_s=wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        return None  # unreachable

    # Namespace the cache key by service so distinct eff services never collide.
    payload = cached_get("echo_dmr", {"_service": service, **query}, fetch, settings=settings)
    results = cast("dict[str, Any]", payload).get("Results", payload)
    if isinstance(results, dict) and "Error" in results:
        raise EchoDmrError(f"ECHO {service} error: {results['Error']}")
    return cast("dict[str, Any]", results)


def _parse_rows(dmrs: list[dict[str, Any]]) -> list[DmrRow]:
    rows: list[DmrRow] = []
    for dm in dmrs:
        rows.append(
            DmrRow(
                period_end=_iso_period(_s(dm.get("MonitoringPeriodEndDate"))),
                value=_f(dm.get("DMRValueNmbr")),
                unit=_s(dm.get("DMRUnitDesc")),
                qualifier=_s(dm.get("DMRValueQualifierCode")),
                stat_base=_s(dm.get("StatisticalBaseShortDesc") or dm.get("StatisticalBaseDesc")),
                limit=_f(dm.get("LimitValueNmbr")),
                limit_type=_s(dm.get("LimitValueTypeDesc")),
                exceedance_pct=_f(dm.get("ExceedencePct")),
                nodi=_s(dm.get("NODICode")),
            )
        )
    return rows


def fetch_effluent_chart(
    npdes_id: str,
    *,
    start_date: str,
    end_date: str,
    settings: Settings | None = None,
) -> EffluentChart:
    """Fetch the reported effluent record for one NPDES permit over an ISO date window.

    ``start_date`` / ``end_date`` are ISO ``YYYY-MM-DD``; ECHO wants ``MM/DD/YYYY``, so
    they are converted here. Raises :class:`EchoDmrError` if ECHO returns no permit.
    """
    settings = settings or get_settings()
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    res = _get(
        settings,
        "get_effluent_chart",
        {
            "p_id": npdes_id,
            "start_date": start.strftime("%m/%d/%Y"),
            "end_date": end.strftime("%m/%d/%Y"),
        },
    )
    if not res.get("CWPName") and not res.get("PermFeatures"):
        raise EchoDmrError(
            f"ECHO returned no effluent chart for {npdes_id} {start_date}..{end_date}"
        )

    parameters: list[DmrParameter] = []
    for feat in res.get("PermFeatures") or []:
        outfall = _s(feat.get("PermFeatureNmbr")) or "?"
        outfall_type = _s(feat.get("PermFeatureTypeDesc"))
        for param in feat.get("Parameters") or []:
            parameters.append(
                DmrParameter(
                    outfall=outfall,
                    outfall_type=outfall_type,
                    parameter_code=_s(param.get("ParameterCode")) or "?",
                    parameter_desc=_s(param.get("ParameterDesc")),
                    monitoring_location=_s(param.get("MonitoringLocationDesc")),
                    rows=_parse_rows(param.get("DischargeMonitoringReports") or []),
                )
            )

    chart = EffluentChart(
        npdes_id=_s(res.get("SourceId")) or npdes_id,
        name=_s(res.get("CWPName")),
        permit_type=_s(res.get("CWPPermitTypeDesc")),
        permit_status=_s(res.get("CWPPermitStatusDesc")),
        major_minor=_s(res.get("CWPMajorMinorStatusFlag")),
        snc_status=_s(res.get("CWPCurrentSNCStatus")),
        start_date=start_date,
        end_date=end_date,
        parameters=parameters,
    )
    log.info(
        "echo_dmr.chart",
        npdes=chart.npdes_id,
        outfalls=len({p.outfall for p in parameters}),
        params=len(parameters),
    )
    return chart


def summarize_discharge(
    chart: EffluentChart, *, design_flow_mgd: float | None = None
) -> DischargeSummary:
    """Reduce a chart to the receiving-water read: actual flow vs. design + exceedances.

    The primary effluent outfall is the one whose flow series (parameter 50050) carries
    the most reported (non-null) monthly values — i.e. the continuous discharge, not a
    CSO/bypass outfall that only flows in wet weather. Flow stats are computed over the
    reported monthly values; ``None`` (no-discharge) periods are excluded, never zero-filled.
    """
    flow_params = chart.series(FLOW_PARAM)
    # Pick the outfall with the most reported monthly-average flow values as the continuous
    # effluent point. Limit to MO AVG rows so DAILY MX rows don't inflate the count.
    primary = max(
        flow_params,
        key=lambda p: sum(
            1 for r in p.rows if r.value is not None and r.stat_base == _MONTHLY_AVG_STAT
        ),
        default=None,
    )
    flows = [
        r.value
        for r in (primary.rows if primary else [])
        if r.value is not None and r.stat_base == _MONTHLY_AVG_STAT
    ]
    mean = round(sum(flows) / len(flows), 3) if flows else None
    pct = round(100.0 * mean / design_flow_mgd, 1) if (mean and design_flow_mgd) else None

    # CSO/bypass outfalls: features carrying the overflow-volume parameter.
    cso = len({p.outfall for p in chart.series(OVERFLOW_PARAM)})

    # Exceedances: only rows ECHO itself flagged (a positive exceedance % or a violation).
    exceedances = [
        r
        for p in chart.parameters
        for r in p.rows
        if r.exceedance_pct is not None and r.exceedance_pct > 0.0
    ]

    return DischargeSummary(
        npdes_id=chart.npdes_id,
        name=chart.name,
        window=f"{chart.start_date}..{chart.end_date}",
        design_flow_mgd=design_flow_mgd,
        primary_outfall=primary.outfall if primary else None,
        n_flow_months=len(flows),
        actual_flow_mean_mgd=mean,
        actual_flow_min_mgd=round(min(flows), 3) if flows else None,
        actual_flow_max_mgd=round(max(flows), 3) if flows else None,
        flow_pct_of_design=pct,
        cso_outfalls=cso,
        snc_status=chart.snc_status,
        exceedances=exceedances,
    )


def dmr_document(chart: EffluentChart, summary: DischargeSummary) -> dict[str, Any]:
    """A YAML-ready, deterministic document of a permit's effluent record + the read.

    Carries full provenance (ECHO source + the regen command) so the committed artifact
    is regenerable, and the primary outfall's monthly flow series verbatim so a reviewer
    can recompute the mean. ``exceedances`` is the (possibly empty) list of ECHO-flagged
    DMR rows — an empty list is the finding "no reported exceedance in the window".
    """
    primary = next(
        (p for p in chart.series(FLOW_PARAM) if p.outfall == summary.primary_outfall), None
    )
    mean_cfs = (
        round(mgd_to_cfs(summary.actual_flow_mean_mgd), 2)
        if summary.actual_flow_mean_mgd is not None
        else None
    )
    design_cfs = (
        round(mgd_to_cfs(summary.design_flow_mgd), 2)
        if summary.design_flow_mgd is not None
        else None
    )
    return {
        "meta": {
            "subject": f"{chart.name or chart.npdes_id} (NPDES {chart.npdes_id}) — "
            "reported effluent record (EPA ECHO DMR)",
            "source": "EPA ECHO eff_rest_services.get_effluent_chart",
            "regenerate": (
                f"watermark dmr {chart.npdes_id} --start {chart.start_date} --end {chart.end_date}"
                + (f" --design-flow {summary.design_flow_mgd}" if summary.design_flow_mgd else "")
            ),
            "discipline": (
                "Reported DMR values are verbatim from the permittee's submissions via ECHO; "
                "a no-discharge/no-data period is null (never zero-filled), and an exceedance is "
                "listed only where ECHO reports one. Design flow is the permitted maximum, not a "
                "metered value."
            ),
        },
        "permit": {
            "npdes_id": chart.npdes_id,
            "name": chart.name,
            "permit_type": chart.permit_type,
            "permit_status": chart.permit_status,
            "major_minor": chart.major_minor,
            "snc_status": chart.snc_status,
            "window": summary.window,
        },
        "discharge_summary": {
            "design_flow_mgd": summary.design_flow_mgd,
            "design_flow_cfs": design_cfs,
            "primary_outfall": summary.primary_outfall,
            "n_flow_months": summary.n_flow_months,
            "actual_flow_mean_mgd": summary.actual_flow_mean_mgd,
            "actual_flow_mean_cfs": mean_cfs,
            "actual_flow_min_mgd": summary.actual_flow_min_mgd,
            "actual_flow_max_mgd": summary.actual_flow_max_mgd,
            "flow_pct_of_design": summary.flow_pct_of_design,
            "cso_outfalls": summary.cso_outfalls,
            "reported_exceedances": len(summary.exceedances),
        },
        "flow_monthly": [
            {"period_end": r.period_end, "value_mgd": r.value, "stat_base": r.stat_base}
            for r in (primary.rows if primary else [])
        ],
        "exceedances": [
            {
                "period_end": r.period_end,
                "value": r.value,
                "unit": r.unit,
                "limit": r.limit,
                "exceedance_pct": r.exceedance_pct,
            }
            for r in summary.exceedances
        ],
    }
