"""Low-flow assimilative-capacity screening.

For each WWTP discharge, compare it against its receiving water's cited 7Q10 design
low flow. The dilution ratio is ``7Q10 / discharge`` (how many parts of low-flow
stream per part of effluent). Below ~1, the effluent dominates the stream at design
low flow — effectively undiluted. This is a *screening band*, not a permit
determination; the real wasteload allocation is in the Ohio EPA fact sheets.

**This is a HYDRAULIC dilution ratio, not per-parameter assimilative capacity.** A
municipal WWTP is characterized here only by its design *flow* (cfs) — the corpus holds no
per-parameter effluent chemistry for these plants. So, unlike the industrial toxic screen
(:mod:`watermark.hydrology.toxics`, WS-07 / #1607), which now reads each RSEI discharger's
per-chemical water load against its own Ohio water-quality criterion (loading capacity =
Q·criterion), this check cannot yet screen ammonia / CBOD / total residual chlorine / metals
against their WQBEL-driving criteria. Doing so needs the plants' reported effluent
*concentrations* (the Ohio EPA NPDES DMR record); until that is ingested, the dilution ratio is
the honest ceiling of what the flow-only data supports — no fabricated per-parameter rigor. The
gap is tracked as an open lead (``WWTP-PARAM-ASSIM`` in ``data/site/leads.yaml``).
"""

from __future__ import annotations

from watermark.config import Settings
from watermark.hydrology.lowflow import _normalize, load_low_flows
from watermark.hydrology.model import (
    AssimilativeCheck,
    Flag,
    HydroFinding,
    ProvenancedValue,
    WaterBalance,
)
from watermark.hydrology.solver.parameters import dilution_bands
from watermark.logging import get_logger

log = get_logger(__name__)


def dilution_flag(
    ratio: float,
    *,
    bands: tuple[float, float] | None = None,
    settings: Settings | None = None,
) -> Flag:
    """Screening band for a 7Q10/discharge dilution ratio (violation < tight < ok).

    The ``(violation, tight)`` bands default to the cited ``tier0-parameters.yaml`` values
    (1.0 / 10.0 — coarse screening, not a permit determination); pass ``bands=`` to override.
    """
    violation, tight = bands if bands is not None else dilution_bands(settings=settings)
    if ratio < violation:
        return "violation"
    if ratio < tight:
        return "tight"
    return "ok"


def check_assimilative(
    balance: WaterBalance,
    low_flows: dict[str, ProvenancedValue] | None = None,
) -> list[AssimilativeCheck]:
    """One dilution check per WWTP discharge with a cited receiving-water 7Q10.

    Each check carries **two** dilution ratios (WS-15, #1615): the conservative
    ``dilution_ratio`` (cited 7Q10 / discharge, crediting no effluent) and an
    ``effluent_credited_ratio`` that credits the permitted effluent already in the reach —
    the summed design discharge of the *other* WWTPs sharing this receiving water — into the
    denominator. The credit is a co-reach sum keyed by receiving water, not a
    longitudinal-position-resolved routing term (that is :class:`RoutedNetwork`'s job); a
    plant alone on its stream has nothing to credit and stays at the conservative default.
    """
    flows = load_low_flows() if low_flows is None else low_flows
    # Key and look up through the SAME normalizer the table was built with, so a
    # receiving water carrying a river-mile / place suffix ("Ottawa River at Lima")
    # still resolves its cited 7Q10 ("ottawa river"). `_normalize` is idempotent, so
    # this is safe whether `flows` arrives pre-normalized or not.
    norm = {_normalize(k): v for k, v in flows.items()}

    # First pass: the WWTP discharges that have a cited receiving-water 7Q10, grouped by the
    # normalized receiving water. The group is the "reach" whose standing permitted effluent a
    # co-discharger's credited denominator draws on.
    screened: list[tuple[str, str, ProvenancedValue, ProvenancedValue]] = []
    for wbn in balance.by_role("wwtp"):
        water = wbn.node.receiving_water
        discharge = wbn.return_flow
        if water is None or discharge is None:
            continue
        q7 = norm.get(_normalize(water))
        if q7 is None:
            log.info("hydro.assim.skip", plant=wbn.node.name, reason="no cited 7Q10", water=water)
            continue
        screened.append((water, wbn.node.name, discharge, q7))

    reach_effluent: dict[str, float] = {}
    reach_plants: dict[str, list[str]] = {}
    for water, name, discharge, _q7 in screened:
        key = _normalize(water)
        reach_effluent[key] = reach_effluent.get(key, 0.0) + discharge.value
        reach_plants.setdefault(key, []).append(name)

    checks: list[AssimilativeCheck] = []
    for water, name, discharge, q7 in screened:
        ratio = q7.value / discharge.value if discharge.value else 0.0
        flag = dilution_flag(ratio)

        # Co-reach permitted effluent already in the reach = Σ(other WWTPs on this receiving
        # water). None when this plant is the only permitted discharger on its stream.
        key = _normalize(water)
        others = [p for p in reach_plants[key] if p != name]
        credited = reach_effluent[key] - discharge.value
        upstream_returns: ProvenancedValue | None = None
        eff_ratio: float | None = None
        eff_flag: Flag | None = None
        detail = (
            f"{water} 7Q10 {q7.value:.2f} cfs vs discharge {discharge.value:.2f} cfs "
            f"-> {ratio:.2f}:1 dilution ({flag})"
        )
        if credited > 0.0 and others:
            upstream_returns = ProvenancedValue.derived(
                credited,
                "cfs",
                citation=(
                    f"Σ permitted design discharge of {len(others)} other WWTP(s) on {water} "
                    f"({', '.join(sorted(others))}) — effluent already in the reach, credited "
                    "into the low-flow denominator (co-reach sum, not longitudinal-position "
                    "resolved; see the routed network for the accumulated picture)"
                ),
                confidence="medium",
            )
            eff_ratio = (q7.value + credited) / discharge.value if discharge.value else 0.0
            eff_flag = dilution_flag(eff_ratio)
            detail += (
                f"; effluent-credited {q7.value:.2f}+{credited:.2f} cfs -> "
                f"{eff_ratio:.2f}:1 ({eff_flag})"
            )

        checks.append(
            AssimilativeCheck(
                receiving_water=water,
                discharger=name,
                design_low_flow=q7,
                discharge=discharge,
                upstream_returns=upstream_returns,
                dilution_ratio=ratio,
                flag=flag,
                effluent_credited_ratio=eff_ratio,
                effluent_credited_flag=eff_flag,
                detail=detail,
            )
        )
    return checks


def assimilative_findings(checks: list[AssimilativeCheck]) -> list[HydroFinding]:
    """Render checks as :class:`HydroFinding`s (ok unless the band is a violation)."""
    findings: list[HydroFinding] = []
    for c in checks:
        findings.append(
            HydroFinding(
                subject=f"{c.discharger} -> {c.receiving_water}",
                check="low-flow-dilution",
                ok=c.flag != "violation",
                detail=c.detail,
            )
        )
    failures = sum(1 for f in findings if not f.ok)
    log.info("hydro.assimilative", checks=len(findings), violations=failures)
    return findings
