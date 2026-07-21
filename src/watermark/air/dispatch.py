"""Reliability dispatch-trigger model: grid stress signals → genset runtime-hours (#1176).

Maps the grid subsystem's already-computed interchange aggregates (:mod:`watermark.grid`,
**no new connector work**) onto a backup-fleet runtime-hours band. The framing is
**reliability + compliance stress-test only** — the emergency gensets are forced into
runtime when the grid cannot serve firm load (an EEA / capacity-shortfall event).
Economic peak-shaving / demand-response is explicitly out of scope for this epic.

The honest core: the EIA-930 signals we have (net-import-hours fraction, the coincident-peak
import need, whether the BA is import-dependent at peak) are **BA-wide window aggregates**.
They do not directly give reliability-event hours. So the mapping introduces one explicit,
labeled bridge — an *escalation fraction*: the share of import-dependent hours that, under
a reliability event, coincide with a firm-capacity shortfall forcing on-site backup. That
fraction is `[inference]` and stays so until the real event is captured (#1174). The
import-hours themselves are `[derived]` from real EIA-930 data. Every runtime figure keeps
its provenance and its caveats.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.grid.model import BAInterchange, CampusInterchangeComparison
from watermark.hydrology.model import ProvenancedValue
from watermark.logging import get_logger

log = get_logger(__name__)

HOURS_PER_YEAR = 8760.0


class DispatchAssumptions(BaseModel):
    """The `[inference]` bridge from grid stress to forced runtime (ungrounded pending #1174).

    ``escalation_fraction_*`` is the share of the BA's import-dependent hours assumed to
    coincide with a reliability event that forces the emergency fleet into runtime. These
    are stated modeling inputs, not observations — a low/central/high band, deliberately
    conservative and fully overridable.
    """

    model_config = ConfigDict(extra="forbid")

    escalation_fraction_low: float = 0.01
    escalation_fraction_central: float = 0.05
    escalation_fraction_high: float = 0.20
    rationale: str = (
        "share of net-import (import-dependent) hours assumed to coincide with a "
        "firm-capacity-shortfall reliability event forcing on-site backup — [inference], "
        "ungrounded until the real dispatch event is captured (#1174)"
    )


class RuntimeEstimate(BaseModel):
    """A backup fleet's forced runtime-hours band under grid reliability stress (#1176).

    ``runtime_hours_*`` are per-engine hours per year (the fleet runs together in a
    reliability event). ``import_hours_per_year`` and ``peak_import_need_mw`` are the
    real grid signals the band is built from; the band itself is `[inference]` through
    :class:`DispatchAssumptions`.
    """

    model_config = ConfigDict(extra="forbid")

    ba: str
    regime: str = "reliability_dispatch"
    import_hours_per_year: ProvenancedValue  # derived from EIA-930 net-import-hours fraction
    peak_import_need_mw: ProvenancedValue  # peak demand minus mean in-BA net generation (C2/#1638)
    import_dependent_at_peak: bool  # BA leans on imports/peaking at the window coincident peak
    runtime_hours_low: ProvenancedValue
    runtime_hours_central: ProvenancedValue
    runtime_hours_high: ProvenancedValue
    assumptions: DispatchAssumptions
    caveats: list[str] = []


def estimate_reliability_runtime(
    comparison: CampusInterchangeComparison,
    interchange: BAInterchange,
    *,
    assumptions: DispatchAssumptions | None = None,
) -> RuntimeEstimate:
    """Map grid interchange signals to a forced-runtime band (deterministic, documented).

    ``runtime = import_hours_per_year * escalation_fraction`` for each band point.
    Import-hours are derived from the real ``net_import_hours_fraction``; the escalation
    fractions are the `[inference]` bridge. When the BA covers its own coincident peak on
    average (``not import_dependent_at_peak``), the band is a lower bound — the residual
    risk is acute local / transmission-deliverability events the BA-wide aggregate does not
    resolve.
    """
    assumptions = assumptions or DispatchAssumptions()
    ba = interchange.ba
    import_frac = interchange.net_import_hours_fraction.value
    import_hours = import_frac * HOURS_PER_YEAR

    import_hours_pv = ProvenancedValue.derived(
        round(import_hours, 1),
        "hr/yr",
        citation=(
            f"{import_frac:g} net-import-hours fraction x {HOURS_PER_YEAR:g} hr/yr "
            f"(EIA-930 {ba}, {interchange.period_start}..{interchange.period_end})"
        ),
    )

    def _runtime(frac: float, label: str) -> ProvenancedValue:
        return ProvenancedValue.assume(
            round(import_hours * frac, 2),
            "hr/yr",
            why=(
                f"{round(import_hours, 1):g} import-dependent hr/yr x {frac:g} {label} "
                "escalation fraction — [inference], reliability-event bridge (#1174)"
            ),
        )

    import_dependent = comparison.import_dependent_at_peak
    caveats = [
        "Reliability / compliance stress-test only — economic peak-shaving and "
        "demand-response are out of scope for this epic.",
        "The escalation fraction is [inference], NOT an observed dispatch — it stays "
        "ungrounded until the real reliability-triggered event is captured (#1174).",
        "Built on BA-WIDE EIA-930 window aggregates; it does not resolve acute local or "
        "transmission-deliverability events at the campus bus (the #96 PJM-queue layer).",
    ]
    if not import_dependent:
        caveats.append(
            f"The BA covers its own coincident peak on average (peak import need "
            f"{comparison.peak_import_need_mw.value:,.0f} MW ≤ 0), so a BA-wide shortfall does not "
            "drive dispatch — this band is a lower bound anchored on the residual import hours."
        )

    est = RuntimeEstimate(
        ba=ba,
        import_hours_per_year=import_hours_pv,
        peak_import_need_mw=comparison.peak_import_need_mw,
        import_dependent_at_peak=import_dependent,
        runtime_hours_low=_runtime(assumptions.escalation_fraction_low, "low"),
        runtime_hours_central=_runtime(assumptions.escalation_fraction_central, "central"),
        runtime_hours_high=_runtime(assumptions.escalation_fraction_high, "high"),
        assumptions=assumptions,
        caveats=caveats,
    )
    log.info(
        "air.dispatch.runtime",
        ba=ba,
        import_hours_yr=round(import_hours, 1),
        central_hr=est.runtime_hours_central.value,
        import_dependent_at_peak=import_dependent,
    )
    return est


def derive_reliability_runtime(
    *,
    settings: Settings | None = None,
    assumptions: DispatchAssumptions | None = None,
) -> RuntimeEstimate | None:
    """Convenience: fetch the grid interchange comparison and map it to a runtime band.

    Returns ``None`` when the active site has no documented facility (the grid comparison
    requires a campus load). Kept thin — the grid fetch is offline/fixture-backed and does
    no new connector work.
    """
    from watermark.grid.interchange import derive_interchange_comparison, fetch_ba_interchange

    settings = settings or get_settings()
    interchange = fetch_ba_interchange(settings=settings)
    try:
        comparison = derive_interchange_comparison(interchange=interchange, settings=settings)
    except ValueError:
        log.info("air.dispatch.no_facility")
        return None
    return estimate_reliability_runtime(comparison, interchange, assumptions=assumptions)
