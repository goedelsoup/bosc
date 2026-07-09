"""Air emissions scenario runner + synthetic-minor NSR cap-exceedance check (#1177).

Mirrors :mod:`watermark.hydrology.scenario`: a :class:`AirScenario` (inputs) →
:func:`evaluate` → :class:`AirScenarioResult` → :func:`write_scenario` (a committed,
self-auditing YAML). The investigable question is the epic's: when a reliability event
forces the "emergency" backup fleet into runtime, does the air burden breach the
**synthetic-minor NSR caps** the permit was engineered to stay under (NOx 235.62 / CO
96.06 tpy)?

Two scenarios: :func:`baseline_scenario` (permit maintenance/testing hours) and
:func:`reliability_dispatch_scenario` (the #1176 forced-runtime band). :func:`evaluate`
rolls runtime-hours x per-engine factors x fleet into annual tonnage per pollutant and
flags any cap crossing; :func:`diff` reports the net increase over baseline. The
standalone-shippable Tier-0 deliverable — defensible without AERMOD (Tier-1).
"""

from __future__ import annotations

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.air.emissions import load_emission_factors, load_nsr_caps
from watermark.air.model import (
    POLLUTANTS,
    FactorBasis,
    GensetEmissionFactors,
    LoadRegime,
    Pollutant,
)
from watermark.config import Settings, get_settings
from watermark.hydrology.model import ProvenancedValue
from watermark.logging import get_logger
from watermark.sites import active_profile

log = get_logger(__name__)

LB_PER_TON = 2000.0

# Standard emergency-engine maintenance & readiness-testing allowance (40 CFR 60.4211(f)
# / NFPA 110). The baseline runtime — what the fleet runs absent any reliability event.
_BASELINE_TEST_HOURS = 100.0


class AirScenario(BaseModel):
    """Inputs for one emissions scenario: how long the fleet runs, and on which factors.

    Defaults to the ``permit`` basis: it carries both engine-load points (idle testing vs
    a dispatch carrying load) and is the source the synthetic-minor cap is actually tracked
    against, so the cap-exceedance check is most faithful on it. AP-42 (``factors_basis=
    "ap42"``) is available as the conservative cross-check, at load only.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    runtime_hours: ProvenancedValue  # per-engine hr/yr
    factors_basis: FactorBasis = "permit"
    load_regime: LoadRegime = "load"


class PollutantTonnage(BaseModel):
    """One pollutant's annual fleet emissions and its standing against the NSR cap."""

    model_config = ConfigDict(extra="forbid")

    pollutant: str
    tpy: ProvenancedValue  # fleet annual tons: runtime x per-engine-hr x fleet / 2000
    cap_tpy: float | None = None  # synthetic-minor cap, if the pollutant is capped
    pct_of_cap: float | None = None
    exceeds_cap: bool = False


class AirScenarioResult(BaseModel):
    """An evaluated scenario: per-pollutant tonnage, cap check, and the breach summary."""

    model_config = ConfigDict(extra="forbid")

    scenario: AirScenario
    engine_mw: ProvenancedValue
    fleet_size: int  # gensets modeled (the site's disclosed count; smaller units not split out)
    fuel: str
    emissions: list[PollutantTonnage]
    any_cap_exceeded: bool
    breached_pollutants: list[str] = []
    note: str = ""


class PollutantDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pollutant: str
    baseline_tpy: float
    scenario_tpy: float
    increase_tpy: float


class AirScenarioDiff(BaseModel):
    """Net new annual burden of a scenario over the baseline, per pollutant."""

    model_config = ConfigDict(extra="forbid")

    baseline: str
    scenario: str
    deltas: list[PollutantDelta]
    caps_newly_breached: list[str] = []


def baseline_scenario(*, factors_basis: FactorBasis = "permit") -> AirScenario:
    """The permit-baseline: maintenance + readiness testing only, no reliability event.

    Runs at the **idle** load point — readiness testing is low/no-load, so full-load rates
    would badly overstate it (and the facility demonstrably complies at baseline). Needs
    the permit basis for the idle rate.
    """
    return AirScenario(
        name="baseline",
        description="Emergency fleet at the maintenance & readiness-testing allowance only.",
        runtime_hours=ProvenancedValue.assume(
            _BASELINE_TEST_HOURS,
            "hr/yr",
            why="emergency-engine maintenance & readiness-testing allowance "
            "(40 CFR 60.4211(f) / NFPA 110); per engine",
        ),
        factors_basis=factors_basis,
        load_regime="idle",
    )


def reliability_dispatch_scenario(
    runtime_hours: float,
    *,
    band: str = "central",
    citation: str | None = None,
    factors_basis: FactorBasis = "permit",
) -> AirScenario:
    """A forced-runtime scenario from the #1176 dispatch band (runtime is per engine).

    ``runtime_hours`` is the per-engine forced runtime (e.g. ``RuntimeEstimate``'s
    ``runtime_hours_central``); it is `[inference]` until the real event grounds it (#1174).
    A reliability dispatch carries real facility load, so it runs at the **load** point.
    """
    why = citation or (
        f"reliability dispatch-trigger {band} runtime band (#1176) — [inference] pending #1174"
    )
    return AirScenario(
        name=f"reliability_dispatch_{band}",
        description=f"Reliability-forced fleet runtime ({band} band): {runtime_hours:g} hr/yr per engine.",
        runtime_hours=ProvenancedValue.assume(round(runtime_hours, 2), "hr/yr", why=why),
        factors_basis=factors_basis,
        load_regime="load",
    )


def _fleet_size(settings: Settings) -> int:
    fac = active_profile(settings).facility
    if fac is None:
        raise ValueError(
            f"site {settings.site!r} has no documented facility — no genset fleet to model"
        )
    if fac.genset_count is None:
        raise ValueError(
            f"site {settings.site!r} has a documented facility but no disclosed gensets "
            "(a site-plan-grounded facility) — no genset fleet to model"
        )
    return fac.genset_count


def evaluate(
    scenario: AirScenario,
    *,
    settings: Settings | None = None,
    factors: GensetEmissionFactors | None = None,
) -> AirScenarioResult:
    """Roll the scenario into annual tonnage per pollutant and check the NSR caps.

    ``tpy = runtime_hours x per-engine-hour factor x fleet_size / 2000``. Caps are the
    site's synthetic-minor facility-wide limits; a pollutant crossing its cap is flagged.
    """
    settings = settings or get_settings()
    factors = factors or load_emission_factors(
        basis=scenario.factors_basis, load_regime=scenario.load_regime, settings=settings
    )
    if factors is None:
        raise ValueError(
            f"site {settings.site!r} has no documented facility — cannot evaluate air scenario"
        )
    fleet = _fleet_size(settings)
    caps = load_nsr_caps(settings=settings)
    runtime = scenario.runtime_hours.value

    emissions: list[PollutantTonnage] = []
    breached: list[str] = []
    for pol in POLLUTANTS:
        ef = factors.factor(pol)
        if ef is None:
            continue
        tpy = runtime * ef.per_engine_hour.value * fleet / LB_PER_TON
        cap = caps.get(pol)
        cap_val = cap.value if cap else None
        pct = round(tpy / cap_val * 100.0, 1) if cap_val else None
        exceeds = bool(cap_val and tpy > cap_val)
        if exceeds:
            breached.append(pol)
        emissions.append(
            PollutantTonnage(
                pollutant=pol,
                tpy=ProvenancedValue.derived(
                    round(tpy, 3),
                    "tpy",
                    citation=(
                        f"{runtime:g} hr/yr x {ef.per_engine_hour.value:g} lb/hr x {fleet} engines "
                        f"/ {LB_PER_TON:g} ({factors.basis} factors)"
                    ),
                ),
                cap_tpy=cap_val,
                pct_of_cap=pct,
                exceeds_cap=exceeds,
            )
        )

    result = AirScenarioResult(
        scenario=scenario,
        engine_mw=factors.engine_mw,
        fleet_size=fleet,
        fuel=factors.fuel,
        emissions=emissions,
        any_cap_exceeded=bool(breached),
        breached_pollutants=breached,
        note=(
            f"Fleet = {fleet} gensets at the standard-unit factor (the site's disclosed count); "
            "any separate smaller units are not modeled individually (conservative). Caps, where "
            "present, are the facility-wide synthetic-minor limits."
        ),
    )
    log.info(
        "air.scenario.evaluate",
        scenario=scenario.name,
        basis=factors.basis,
        runtime_hr=runtime,
        breached=breached,
    )
    return result


def cap_breach_runtime(
    pollutant: Pollutant,
    *,
    settings: Settings | None = None,
    factors: GensetEmissionFactors | None = None,
) -> float | None:
    """The per-engine runtime (hr/yr) at which the fleet crosses a pollutant's NSR cap.

    The epic's headline framing — "how much forced generation before this becomes a major
    NSR source." ``None`` if the pollutant is uncapped or ungrounded for this site.
    """
    settings = settings or get_settings()
    factors = factors or load_emission_factors(
        basis="permit", load_regime="load", settings=settings
    )
    if factors is None:
        return None
    ef = factors.factor(pollutant)
    cap = load_nsr_caps(settings=settings).get(pollutant)
    if ef is None or cap is None:
        return None
    fleet = _fleet_size(settings)
    denom = ef.per_engine_hour.value * fleet
    if denom <= 0:
        return None
    return round(cap.value * LB_PER_TON / denom, 1)


def diff(baseline: AirScenarioResult, scenario: AirScenarioResult) -> AirScenarioDiff:
    """Net new annual burden of ``scenario`` over ``baseline``, per pollutant."""
    base = {e.pollutant: e for e in baseline.emissions}
    newly: list[str] = []
    deltas: list[PollutantDelta] = []
    for e in scenario.emissions:
        b = base.get(e.pollutant)
        b_tpy = b.tpy.value if b else 0.0
        deltas.append(
            PollutantDelta(
                pollutant=e.pollutant,
                baseline_tpy=round(b_tpy, 3),
                scenario_tpy=round(e.tpy.value, 3),
                increase_tpy=round(e.tpy.value - b_tpy, 3),
            )
        )
        if e.exceeds_cap and not (b and b.exceeds_cap):
            newly.append(e.pollutant)
    return AirScenarioDiff(
        baseline=baseline.scenario.name,
        scenario=scenario.scenario.name,
        deltas=deltas,
        caps_newly_breached=newly,
    )


def write_scenario(result: AirScenarioResult, *, settings: Settings | None = None) -> str:
    """Persist a scenario result as a committed, slug-scoped, self-auditing YAML artifact."""
    settings = settings or get_settings()
    out_dir = settings.scenarios_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    # Slug-scoped so a second site never clobbers Lima's scenario artifacts (#325).
    path = out_dir / f"{settings.site}.air-{result.scenario.name}.scenario.yaml"
    path.write_text(
        yaml.safe_dump(result.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    log.info("air.scenario.wrote", path=str(path))
    return str(path)
