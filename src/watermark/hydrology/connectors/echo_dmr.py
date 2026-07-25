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

import math
import time
from datetime import date
from typing import Any, cast

import httpx
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.connectors import to_float, to_str
from watermark.hydrology.connectors._cache import cached_get
from watermark.hydrology.units import CFS_TO_MGD, mgd_to_cfs
from watermark.logging import get_logger
from watermark.provenance import Confidence, SourceKind

log = get_logger(__name__)

# NPDES parameter codes we care about for a receiving-water characterization.
FLOW_PARAM = "50050"  # "Flow, in conduit or thru treatment plant" (the effluent flow)
# "Overflow volume" — ICIS 74063 covers BOTH sanitary (SSO) and combined (CSO) sewer overflows;
# the code does not distinguish them, so a count of features carrying it is "overflow outfalls",
# not specifically CSO (WS-25 / #1625).
OVERFLOW_PARAM = "74063"

# ECHO returns multiple stat-base rows per period (e.g. a monthly average and a daily
# maximum). Only the monthly-average series is meaningful for the mean-flow / utilisation
# computation; mixing in daily-max rows inflates both the mean and n_flow_months. Match it on
# the stable ICIS ``StatisticalBaseCode`` ("MK"), and, when ECHO omits the code, on the short
# ("MO AVG") or long ("Monthly Average") descriptor case-insensitively — an exact "MO AVG"
# string match silently collapsed the whole flow series to n_flow_months=0 / mean=None
# whenever ECHO returned only the long "Monthly Average" label (#1601).
_MONTHLY_AVG_CODE = "MK"
_MONTHLY_AVG_LABELS = frozenset({"MO AVG", "MONTHLY AVERAGE", "MONTHLY AVG"})

# Flow (parameter 50050) is *usually* reported in MGD but not guaranteed — a permit may report
# GPD or CFS — so the value is converted by its reported unit, never assumed MGD (#1601). A
# unit absent from this table is unrecognized: the row is dropped (with a warning), never
# averaged as if it were already MGD. Each factor reduces one unit to MGD; because the table is
# only ever applied to 50050 flow rows, "MGD"/"MG/D" are unambiguously volumetric flow.
_FLOW_UNIT_TO_MGD: dict[str, float] = {
    "MGD": 1.0,  # million gallons/day — ECHO's standard flow unit for 50050
    "MG/D": 1.0,
    "GPD": 1e-6,  # gallons/day
    "GAL/D": 1e-6,
    "GPM": 1_440e-6,  # gallons/minute -> MGD (1,440 min/day)
    "CFS": CFS_TO_MGD,  # cubic feet/second
}

_EFF_SERVICE = "eff_rest_services"
# Three-letter month tokens ECHO returns in MonitoringPeriodEndDate ("31-JAN-23").
_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}  # fmt: skip
_MONTH_NAMES = {v: k.title() for k, v in _MONTHS.items()}  # 1 -> "Jan", for readable output

# Warm-season window for the discharge-seasonality diagnostic (#1678, closed-loop cycling epic
# #1676). Months (May-Oct) match the network-wide Ohio EPA regulatory summer window
# (``watermark.hydrology.lowflow.OEPA_SUMMER_MONTHS``, NPDES permit 2PH00006 Part II) — reused
# here as the warm-season proxy for a temperature-driven evaporative signature, not as the
# regulatory low-flow selector. Kept as month *numbers* (and overridable) so this connector stays
# decoupled from the profile-aware ``lowflow`` module; a site whose cooling season differs passes
# its own set. The resulting metric is a shape indicator ([inference]), never a [verified] figure.
_WARM_SEASON_MONTHS: frozenset[int] = frozenset({5, 6, 7, 8, 9, 10})


class EchoDmrError(RuntimeError):
    """ECHO returned an Error object or an unparseable effluent chart."""


def _pct_to_float(value: Any) -> float | None:
    """Parse ECHO's ``ExceedencePct`` to a float percentage.

    ECHO's effluent-chart service returns the exceedance percentage as a *string with a
    trailing percent sign* (e.g. ``"13%"``, ``"2%"``) — not a bare number. A plain
    :func:`to_float` chokes on the ``%`` and returns ``None``, which silently drops every
    ECHO-flagged numeric exceedance (the bug this fixes). Strip a single trailing ``%``
    and coerce; a value ECHO did not report stays ``None``.
    """
    if value is None:
        return None
    text = str(value).strip()
    if text.endswith("%"):
        text = text[:-1].strip()
    return to_float(text)


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


class DmrViolation(BaseModel):
    """One ECHO-reported NPDES violation attached to a DMR row.

    Passed through verbatim from ECHO's ``NPDESViolations`` array — ECHO's *own*
    determination, never derived here by comparing a value to a limit. The severity
    code distinguishes a minor numeric exceedance (``2`` = Non-Reportable Noncompliance)
    from a reportable/significant one, which matters for reading a facility's SNC flag.
    """

    model_config = ConfigDict(extra="forbid")

    code: str | None  # ViolationCode, e.g. "E90"
    desc: str | None  # ViolationDesc, e.g. "DMR, Limited - Numeric Violation"
    severity: str | None  # ViolationSeverity, e.g. "2"
    severity_desc: str | None  # ViolationSeverityDesc, e.g. "Non-Reportable Noncompliance ..."


class DmrRow(BaseModel):
    """One reported Discharge Monitoring Report value for a parameter + monitoring period.

    Values are passed through verbatim. ``value`` is ``None`` when ECHO carries a
    no-data-indicator (``nodi``) instead of a number (e.g. a period with no discharge).
    ``exceedance_pct`` is populated only when ECHO itself reports an exceedance, and
    ``violations`` mirrors ECHO's ``NPDESViolations`` for the row (empty when none).
    """

    model_config = ConfigDict(extra="forbid")

    period_end: str | None  # ISO date (converted from ECHO's DD-MON-YY)
    value: float | None  # DMRValueNmbr, in `unit`
    unit: str | None  # DMRUnitDesc — the permittee's reported unit (e.g. "MGD", "GPD")
    # ECHO also standardizes the value to a canonical unit; carried so a flow row can be read
    # in MGD without trusting `unit` (both default None — ECHO omits them for some permits).
    std_value: float | None = None  # DMRValueStdUnits — the value in the standard unit
    std_unit: str | None = None  # StdUnitDesc — the standard unit (MGD for flow 50050)
    qualifier: str | None  # "=", "<", ...
    stat_base: str | None  # ECHO StatisticalBaseShortDesc/Desc (e.g. "Monthly Average")
    stat_base_code: str | None = None  # ECHO StatisticalBaseCode (stable; "MK" = monthly avg)
    limit: float | None
    limit_type: str | None  # ECHO LimitValueTypeDesc (Quantity1, Concentration1, ...)
    exceedance_pct: float | None
    nodi: str | None  # no-data-indicator code (non-null => no value reported)
    violations: list[DmrViolation]  # ECHO-reported NPDESViolations (empty when none)


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


class DmrExceedance(BaseModel):
    """One ECHO-flagged effluent exceedance, with its parameter + outfall context.

    Built by :func:`summarize_discharge` from a :class:`DmrRow` ECHO flagged (a positive
    ``exceedance_pct`` or an attached ``NPDESViolations`` entry), enriched with the
    parameter/outfall the row belongs to so the summary says *which* pollutant exceeded
    *where* — a bare :class:`DmrRow` loses that link once flattened across parameters.
    """

    model_config = ConfigDict(extra="forbid")

    outfall: str
    parameter_code: str
    parameter_desc: str | None
    monitoring_location: str | None
    period_end: str | None
    value: float | None
    unit: str | None
    stat_base: str | None
    limit: float | None
    limit_type: str | None
    exceedance_pct: float | None
    violations: list[DmrViolation]


class FlowSeasonality(BaseModel):
    """The seasonality shape of a flow outfall's reported monthly discharge (#1678).

    Built by :func:`flow_seasonality` from the primary outfall's monthly-average flow series,
    aggregated by calendar month (so a multi-year window folds together). It is the diagnostic
    the closed-loop cycling epic (#1676) needs: an **evaporative** heat-rejection tower blows
    down on a temperature-driven cycle (a summer peak, ``warm_ratio`` well above 1), while a
    genuinely dry/sealed loop discharges flat (``warm_ratio`` ~ 1, ``cv`` ~ 0). The shape is
    itself the finding and feeds the A3 reconciliation harness.

    Every figure here is derived from the permittee's own [verified] DMR values, but the
    *signature* it computes is an [inference] — a shape indicator, never a headline discharge.
    ``warm_ratio`` is ``None`` unless the window carries both a warm-month and a cool-month
    observation (a single season cannot show a ratio); ``cv`` needs >= 2 distinct months.
    """

    model_config = ConfigDict(extra="forbid")

    n_months: int  # distinct calendar months with a reported monthly-average flow value
    warm_months: list[int]  # the warm-season window used (1-12), carried for provenance
    warm_mean_mgd: float | None  # mean monthly-average flow across warm-season months
    cool_mean_mgd: float | None  # mean monthly-average flow across the remaining months
    warm_ratio: float | None  # warm_mean / cool_mean — the temperature-driven-cycle diagnostic
    peak_month: int | None  # calendar month (1-12) with the highest mean monthly-average flow
    peak_mean_mgd: float | None
    cv: float | None  # coefficient of variation across the per-month means (flat loop -> ~0)
    # Provenance (the hydrology `ProvenancedValue` convention): the metric is `derived` from the
    # permittee's [verified] monthly-average DMR values, so it is a `medium`-confidence [inference]
    # shape — never a document-verbatim figure. `asof` is the latest month the series covers, so a
    # consumer (A3) sees the data currency; `citation` records what it was computed over.
    source: SourceKind
    citation: str | None
    confidence: Confidence
    asof: str | None  # latest ISO period the series covers (data currency), None if unknown


class DischargeSummary(BaseModel):
    """The computed receiving-water read on a permit's effluent record.

    ``actual_flow_*`` reduce the primary outfall's reported monthly flow (parameter
    50050). ``exceedances`` are only the DMR rows ECHO flagged (a positive
    ``ExceedencePct`` or an attached ``NPDESViolations`` entry) — an empty list means the
    reported record shows no exceedance in the window, which is itself a finding, never
    silently treated as "unknown".
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
    # Overflow (CSO + SSO) outfalls — param 74063 covers both, so this is not CSO-specific; renamed
    # from `cso_outfalls` (WS-25 / #1625). `overflow_outfalls` counts every permitted feature
    # carrying the parameter; `active_overflow_outfalls` narrows to those that actually reported a
    # non-null overflow volume (i.e. flowed), distinguishing a live overflow point from a
    # permitted-but-inactive one.
    overflow_outfalls: int
    active_overflow_outfalls: int
    snc_status: str | None
    exceedances: list[DmrExceedance]
    # Seasonality shape of the primary outfall's monthly flow (#1678) — the closed-loop
    # evaporative-vs-dry diagnostic. ``None`` when the primary outfall has no usable monthly series.
    seasonality: FlowSeasonality | None = None


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


def _parse_violations(raw: Any) -> list[DmrViolation]:
    """Parse ECHO's ``NPDESViolations`` array (may be absent/empty) verbatim."""
    violations: list[DmrViolation] = []
    for v in raw or []:
        if not isinstance(v, dict):
            continue
        violations.append(
            DmrViolation(
                code=to_str(v.get("ViolationCode")),
                desc=to_str(v.get("ViolationDesc")),
                severity=to_str(v.get("ViolationSeverity")),
                severity_desc=to_str(v.get("ViolationSeverityDesc")),
            )
        )
    return violations


def _is_effluent_violation(v: DmrViolation) -> bool:
    """True if ECHO classifies this as an effluent-limit violation (not a reporting lapse).

    ECHO/ICIS-NPDES ``ViolationCode`` prefixes: **E** = effluent violation (``E90`` = a DMR
    value exceeding a numeric limit); **D** = DMR reporting / non-receipt (``D80`` "Monitor
    Only - Overdue", ``D90`` overdue); **C** = compliance-schedule. Only an effluent violation
    is a receiving-water *exceedance* — a "Monitor Only - Overdue" is a paperwork lapse, not an
    over-limit discharge, and must not inflate the exceedance list.
    """
    return v.code is not None and v.code.upper().startswith("E")


def _parse_rows(dmrs: list[dict[str, Any]]) -> list[DmrRow]:
    rows: list[DmrRow] = []
    for dm in dmrs:
        rows.append(
            DmrRow(
                period_end=_iso_period(to_str(dm.get("MonitoringPeriodEndDate"))),
                value=to_float(dm.get("DMRValueNmbr")),
                unit=to_str(dm.get("DMRUnitDesc")),
                std_value=to_float(dm.get("DMRValueStdUnits")),
                std_unit=to_str(dm.get("StdUnitDesc")),
                qualifier=to_str(dm.get("DMRValueQualifierCode")),
                stat_base=to_str(
                    dm.get("StatisticalBaseShortDesc") or dm.get("StatisticalBaseDesc")
                ),
                stat_base_code=to_str(dm.get("StatisticalBaseCode")),
                limit=to_float(dm.get("LimitValueNmbr")),
                limit_type=to_str(dm.get("LimitValueTypeDesc")),
                exceedance_pct=_pct_to_float(dm.get("ExceedencePct")),
                nodi=to_str(dm.get("NODICode")),
                violations=_parse_violations(dm.get("NPDESViolations")),
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
        outfall = to_str(feat.get("PermFeatureNmbr")) or "?"
        outfall_type = to_str(feat.get("PermFeatureTypeDesc"))
        for param in feat.get("Parameters") or []:
            parameters.append(
                DmrParameter(
                    outfall=outfall,
                    outfall_type=outfall_type,
                    parameter_code=to_str(param.get("ParameterCode")) or "?",
                    parameter_desc=to_str(param.get("ParameterDesc")),
                    monitoring_location=to_str(param.get("MonitoringLocationDesc")),
                    rows=_parse_rows(param.get("DischargeMonitoringReports") or []),
                )
            )

    chart = EffluentChart(
        npdes_id=to_str(res.get("SourceId")) or npdes_id,
        name=to_str(res.get("CWPName")),
        permit_type=to_str(res.get("CWPPermitTypeDesc")),
        permit_status=to_str(res.get("CWPPermitStatusDesc")),
        major_minor=to_str(res.get("CWPMajorMinorStatusFlag")),
        snc_status=to_str(res.get("CWPCurrentSNCStatus")),
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


def _norm(token: str | None) -> str:
    """Upper-cased, stripped token for case-insensitive matching ("" when absent)."""
    return (token or "").strip().upper()


def _is_monthly_avg(row: DmrRow) -> bool:
    """True for a monthly-average DMR row, robust to ECHO's stat-base representation (#1601).

    Prefers the stable ICIS ``StatisticalBaseCode`` ("MK"); when ECHO omits the code it
    accepts the short ("MO AVG") or long ("Monthly Average") descriptor case-insensitively.
    The exact ``stat_base == "MO AVG"`` match this replaces collapsed the whole flow series to
    ``n_flow_months=0`` / ``mean=None`` whenever ECHO returned only the long label.
    """
    if row.stat_base_code:
        return _norm(row.stat_base_code) == _MONTHLY_AVG_CODE
    return _norm(row.stat_base) in _MONTHLY_AVG_LABELS


def _flow_mgd(row: DmrRow) -> float | None:
    """Reduce one flow (50050) DMR row to MGD, honoring the reported unit (#1601).

    Preference order, so a non-MGD permit is converted rather than misread as MGD:

    1. ECHO's own standardized value when it standardized to MGD (``DMRValueStdUnits`` in
       ``StdUnitDesc``) — ECHO already did the conversion.
    2. the reported value converted by its reported unit (``DMRUnitDesc``).
    3. an absent unit taken as MGD — 50050 is definitionally a flow and ECHO reports it in
       MGD; the historical assumption, kept only when there is *no* unit signal at all.

    Returns ``None`` for a no-value row and for a row whose unit is present but not a
    recognized flow unit — the caller drops the latter (with a warning) rather than
    averaging a non-MGD number as if it were MGD.
    """
    if _norm(row.std_unit) == "MGD" and row.std_value is not None:
        return row.std_value
    if row.value is None:
        return None
    unit = _norm(row.unit)
    if not unit:
        return row.value  # no unit signal; 50050 is MGD by ECHO convention
    factor = _FLOW_UNIT_TO_MGD.get(unit)
    return row.value * factor if factor is not None else None


def _month_of(period_end: str | None) -> int | None:
    """Calendar month (1-12) from an ISO ``YYYY-MM-DD`` period end, else ``None``."""
    if not period_end or len(period_end) < 7:
        return None
    try:
        month = int(period_end[5:7])
    except ValueError:
        return None
    return month if 1 <= month <= 12 else None


def flow_seasonality(
    param: DmrParameter | None,
    *,
    warm_months: frozenset[int] = _WARM_SEASON_MONTHS,
) -> FlowSeasonality | None:
    """Summer-peak diagnostic on a flow outfall's monthly-average series (#1678).

    Reduces the outfall's monthly-average flow rows to MGD (daily-max and unrecognized-unit
    rows out, exactly as :func:`summarize_discharge`), groups them by calendar month so a
    multi-year window folds together, and computes the warm/cool ratio and dispersion that
    distinguish a temperature-driven evaporative blowdown (a summer peak) from a flat, dry
    loop. Returns ``None`` for a missing outfall or a series with no usable monthly value —
    never a fabricated shape. ``warm_ratio`` needs both a warm- and a cool-month observation;
    ``cv`` needs at least two distinct months.

    Warm/cool means are computed over the **folded per-calendar-month means**, not the raw rows,
    so a month with more observations (a multi-year window) contributes equal weight — the same
    basis ``peak_month`` and ``cv`` already use; pooling the raw rows would let a heavily-reported
    month dominate the season mean.
    """
    if param is None:
        return None
    pairs: list[tuple[int, float]] = [
        (m, v)
        for r in param.rows
        if _is_monthly_avg(r)
        and (m := _month_of(r.period_end)) is not None
        and (v := _flow_mgd(r)) is not None
    ]
    if not pairs:
        return None

    by_month: dict[int, list[float]] = {}
    for m, v in pairs:
        by_month.setdefault(m, []).append(v)
    month_means = {m: sum(vs) / len(vs) for m, vs in by_month.items()}

    # Partition the folded month means (each calendar month once), not the raw pairs.
    warm_means = [mean for m, mean in month_means.items() if m in warm_months]
    cool_means = [mean for m, mean in month_means.items() if m not in warm_months]
    warm_mean = sum(warm_means) / len(warm_means) if warm_means else None
    cool_mean = sum(cool_means) / len(cool_means) if cool_means else None
    warm_ratio = (
        round(warm_mean / cool_mean, 3)
        if warm_mean is not None and cool_mean is not None and cool_mean > 0.0
        else None
    )

    peak_month, peak_mean = max(month_means.items(), key=lambda kv: kv[1])
    means = list(month_means.values())
    overall = sum(means) / len(means)
    cv: float | None = None
    if len(means) >= 2 and overall > 0.0:
        variance = sum((x - overall) ** 2 for x in means) / len(means)  # population variance
        cv = round(math.sqrt(variance) / overall, 3)

    latest_period = max((r.period_end for r in param.rows if r.period_end), default=None)
    return FlowSeasonality(
        n_months=len(by_month),
        warm_months=sorted(warm_months),
        warm_mean_mgd=round(warm_mean, 4) if warm_mean is not None else None,
        cool_mean_mgd=round(cool_mean, 4) if cool_mean is not None else None,
        warm_ratio=warm_ratio,
        peak_month=peak_month,
        peak_mean_mgd=round(peak_mean, 4),
        cv=cv,
        source="derived",
        citation=(
            f"warm/cool ratio + CV over outfall {param.outfall}'s reported monthly-average flow "
            "(ECHO DMR, parameter 50050)"
        ),
        confidence="medium",
        asof=latest_period,
    )


def summarize_discharge(
    chart: EffluentChart, *, design_flow_mgd: float | None = None
) -> DischargeSummary:
    """Reduce a chart to the receiving-water read: actual flow vs. design + exceedances.

    The primary effluent outfall is the one whose flow series (parameter 50050) carries
    the most reported (non-null) monthly values — i.e. the continuous discharge, not a
    CSO/bypass outfall that only flows in wet weather. Flow stats are computed over the
    reported monthly values, each reduced to MGD by its reported unit (never assumed —
    #1601); ``None`` (no-discharge) periods are excluded, never zero-filled.
    """
    flow_params = chart.series(FLOW_PARAM)

    def monthly_mgd(param: DmrParameter) -> list[float]:
        """Monthly-average flow values reduced to MGD (daily-max + unrecognized-unit rows out)."""
        return [v for r in param.rows if _is_monthly_avg(r) and (v := _flow_mgd(r)) is not None]

    # Pick the outfall with the most reported monthly-average flow values as the continuous
    # effluent point (a CSO/bypass outfall flows only in wet weather); the values are MGD.
    primary = max(flow_params, key=lambda p: len(monthly_mgd(p)), default=None)
    flows = monthly_mgd(primary) if primary else []

    # Loud on a silent unit mismatch: a monthly-average flow row ECHO reported in a unit we
    # can't reduce to MGD is dropped, never averaged as MGD — warn so the gap isn't invisible.
    if primary is not None:
        unconvertible = sorted(
            {
                r.unit
                for r in primary.rows
                if r.unit is not None
                and r.value is not None
                and _is_monthly_avg(r)
                and _flow_mgd(r) is None
            }
        )
        if unconvertible:
            log.warning(
                "echo_dmr.flow_unit_unconvertible",
                npdes=chart.npdes_id,
                outfall=primary.outfall,
                units=unconvertible,
            )

    mean = round(sum(flows) / len(flows), 3) if flows else None
    pct = round(100.0 * mean / design_flow_mgd, 1) if (mean and design_flow_mgd) else None

    # Overflow outfalls (CSO + SSO — param 74063 covers both). `overflow` counts every permitted
    # feature carrying the parameter; `active_overflow` narrows to those with >= 1 reported
    # non-null overflow volume, so a live overflow point is distinguished from a permitted-but-
    # inactive one (a permit can list an outfall that never actually overflowed in the window).
    overflow_params = chart.series(OVERFLOW_PARAM)
    overflow = len({p.outfall for p in overflow_params})
    active_overflow = len(
        {p.outfall for p in overflow_params if any(r.value is not None for r in p.rows)}
    )

    # Exceedances: only rows ECHO itself flagged as an *effluent* over-limit — a positive
    # ExceedencePct, or an attached NPDESViolations entry ECHO classifies as an effluent
    # violation (code E…). Both are ECHO's own determination; nothing here is computed by
    # comparing a value to its limit, and reporting/non-receipt violations (D-codes) are
    # excluded so a "Monitor Only - Overdue" never masquerades as a discharge exceedance.
    # Enriched with the parameter/outfall so the summary records which pollutant exceeded where.
    exceedances = [
        DmrExceedance(
            outfall=p.outfall,
            parameter_code=p.parameter_code,
            parameter_desc=p.parameter_desc,
            monitoring_location=p.monitoring_location,
            period_end=r.period_end,
            value=r.value,
            unit=r.unit,
            stat_base=r.stat_base,
            limit=r.limit,
            limit_type=r.limit_type,
            exceedance_pct=r.exceedance_pct,
            violations=r.violations,
        )
        for p in chart.parameters
        for r in p.rows
        if (r.exceedance_pct is not None and r.exceedance_pct > 0.0)
        or any(_is_effluent_violation(v) for v in r.violations)
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
        overflow_outfalls=overflow,
        active_overflow_outfalls=active_overflow,
        snc_status=chart.snc_status,
        exceedances=exceedances,
        seasonality=flow_seasonality(primary),
    )


def _seasonality_doc(s: FlowSeasonality | None) -> dict[str, Any] | None:
    """Render a :class:`FlowSeasonality` to a YAML-ready dict (``None`` stays ``None``).

    Emits the provenance quad (``source``/``citation``/``confidence``/``asof``) so a present
    seasonality block always carries its tag, plus a human-readable ``peak_month_name`` and a
    one-line ``discipline`` restating that the warm/cool ratio is an [inference] shape indicator,
    not a [verified] discharge figure.
    """
    if s is None:
        return None
    return {
        "n_months": s.n_months,
        "warm_months": s.warm_months,
        "warm_mean_mgd": s.warm_mean_mgd,
        "cool_mean_mgd": s.cool_mean_mgd,
        "warm_ratio": s.warm_ratio,
        "peak_month": s.peak_month,
        "peak_month_name": _MONTH_NAMES.get(s.peak_month) if s.peak_month else None,
        "peak_mean_mgd": s.peak_mean_mgd,
        "cv": s.cv,
        "source": s.source,
        "citation": s.citation,
        "confidence": s.confidence,
        "asof": s.asof,
        "discipline": (
            "Warm/cool ratio and CV are a seasonality *shape* indicator ([inference]) over the "
            "permittee's [verified] monthly-average flow — a warm_ratio well above 1 is the "
            "temperature-driven signature of an evaporative heat-rejection tower; ~1 (flat, low "
            "CV) is consistent with a dry/sealed loop. Not a discharge magnitude."
        ),
    }


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
            "overflow_outfalls": summary.overflow_outfalls,
            "active_overflow_outfalls": summary.active_overflow_outfalls,
            "reported_exceedances": len(summary.exceedances),
        },
        "seasonality": _seasonality_doc(summary.seasonality),
        "flow_monthly": [
            {"period_end": r.period_end, "value_mgd": _flow_mgd(r), "stat_base": r.stat_base}
            for r in (primary.rows if primary else [])
        ],
        "exceedances": [
            {
                "period_end": r.period_end,
                "outfall": r.outfall,
                "parameter_code": r.parameter_code,
                "parameter": r.parameter_desc,
                "stat_base": r.stat_base,
                "value": r.value,
                "unit": r.unit,
                "limit": r.limit,
                "limit_type": r.limit_type,
                "exceedance_pct": r.exceedance_pct,
                "violations": [
                    {
                        "code": v.code,
                        "desc": v.desc,
                        "severity": v.severity,
                        "severity_desc": v.severity_desc,
                    }
                    for v in r.violations
                ],
            }
            for r in summary.exceedances
        ],
    }
