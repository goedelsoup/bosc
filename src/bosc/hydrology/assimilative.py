"""Low-flow assimilative-capacity screening.

For each WWTP discharge, compare it against its receiving water's cited 7Q10 design
low flow. The dilution ratio is ``7Q10 / discharge`` (how many parts of low-flow
stream per part of effluent). Below ~1, the effluent dominates the stream at design
low flow — effectively undiluted. This is a *screening band*, not a permit
determination; the real wasteload allocation is in the Ohio EPA fact sheets.
"""

from __future__ import annotations

from bosc.hydrology.lowflow import load_low_flows
from bosc.hydrology.model import (
    DILUTION_TIGHT,
    DILUTION_VIOLATION,
    AssimilativeCheck,
    Flag,
    HydroFinding,
    ProvenancedValue,
    WaterBalance,
)
from bosc.logging import get_logger

log = get_logger(__name__)


def dilution_flag(ratio: float) -> Flag:
    """Screening band for a 7Q10/discharge dilution ratio (violation < tight < ok)."""
    if ratio < DILUTION_VIOLATION:
        return "violation"
    if ratio < DILUTION_TIGHT:
        return "tight"
    return "ok"


def check_assimilative(
    balance: WaterBalance,
    low_flows: dict[str, ProvenancedValue] | None = None,
) -> list[AssimilativeCheck]:
    """One dilution check per WWTP discharge with a cited receiving-water 7Q10."""
    flows = load_low_flows() if low_flows is None else low_flows
    norm = {k.strip().lower(): v for k, v in flows.items()}
    checks: list[AssimilativeCheck] = []

    for wbn in balance.by_role("wwtp"):
        water = wbn.node.receiving_water
        discharge = wbn.return_flow
        if water is None or discharge is None:
            continue
        q7 = norm.get(water.strip().lower())
        if q7 is None:
            log.info("hydro.assim.skip", plant=wbn.node.name, reason="no cited 7Q10", water=water)
            continue
        ratio = q7.value / discharge.value if discharge.value else 0.0
        flag = dilution_flag(ratio)
        checks.append(
            AssimilativeCheck(
                receiving_water=water,
                discharger=wbn.node.name,
                design_low_flow=q7,
                discharge=discharge,
                dilution_ratio=ratio,
                flag=flag,
                detail=(
                    f"{water} 7Q10 {q7.value:.2f} cfs vs discharge {discharge.value:.2f} cfs "
                    f"-> {ratio:.2f}:1 dilution ({flag})"
                ),
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
