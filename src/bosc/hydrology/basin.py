"""Basin-wide low-flow assimilative screen + derived receiving-water 7Q10s.

The cited 7Q10 table (:mod:`bosc.hydrology.lowflow`) covers only the three Lima-loop
streams read off Ohio EPA fact sheets in our corpus. This module extends the
assimilative screen to the basin-wide POTW inventory (the EPA ECHO Maumee dischargers,
``data/reference/echo/maumee-wwtp.potw.yaml``) by **deriving** a 7Q10 for the major
USGS-gaged mainstems via log-Pearson III (:mod:`bosc.hydrology.lowflow_frequency`) —
``source=derived``: a screening denominator, **not** a cited regulatory statistic.

Discipline (omit, don't guess): a discharger is screened only when its ECHO
``receiving_water`` names a gaged **mainstem directly** — an exact surface-form match in
the curated alias set. A POTW on an ungaged tributary/ditch, or with no receiving water
in ECHO, is reported "no 7Q10" and left unscreened. It is never screened against a
*downstream* river's larger 7Q10 (that would overstate dilution into a false "ok");
including a tributary needs that tributary's own gage or fact sheet. The derived 7Q10 is
the value **at the gage**, a screening proxy for the discharge reach (which differs by
drainage-area ratio) — hence ``confidence: medium``.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from bosc.config import Settings, get_settings
from bosc.hydrology.assimilative import dilution_flag
from bosc.hydrology.lowflow import load_low_flows
from bosc.hydrology.lowflow_frequency import compute_low_flow_frequency
from bosc.hydrology.model import AssimilativeCheck, ProvenancedValue
from bosc.hydrology.units import mgd_to_cfs
from bosc.logging import get_logger

log = get_logger(__name__)

_DERIVED_FILE = "low-flow-7q10.derived.yaml"
_POTW_INVENTORY = ("echo", "maumee-wwtp.potw.yaml")
_MIN_YEARS = 20  # climatic years of record needed for a defensible LP3 7Q10

# Curated major Maumee-basin mainstems with a long-record USGS gage. ``aliases`` are the
# exact ECHO ``receiving_water`` surface forms (comma-split) that mean a *direct*
# discharge to this mainstem — not a tributary "via"/"to" it. Verified to return a
# multi-decade daily-discharge record from NWIS. (Little Auglaize is omitted: its only
# gage, 04191058, has <10 yr of record — too short for a defensible 7Q10.)
_MAINSTEM_GAGES: dict[str, dict[str, Any]] = {
    "Maumee River": {"gage": "04193500", "aliases": ["maumee river"]},
    "Auglaize River": {"gage": "04186500", "aliases": ["auglaize river", "auglaze river"]},
    "St. Marys River": {
        "gage": "04182000",
        "aliases": ["st marys river", "st. marys river", "saint marys river"],
    },
    "St. Joseph River": {
        "gage": "04178000",
        "aliases": ["st joseph river", "st. joseph river", "saint joseph river", "st joseph r"],
    },
}


def _norm(name: str) -> str:
    """Normalize a receiving-water surface form for matching (lowercase, collapse ws)."""
    return " ".join((name or "").strip().lower().split())


# --------------------------------------------------------------------- derivation


def derive_basin_low_flows(
    *, settings: Settings | None = None, min_years: int = _MIN_YEARS
) -> dict[str, dict[str, Any]]:
    """Derive a 7Q10 per curated mainstem gage (LP3 over the NWIS daily record).

    Network-bound (USGS NWIS) — the regen step for the committed derived reference.
    Omits any gage with fewer than ``min_years`` complete climatic years or a
    non-positive/NaN 7Q10 (never commit an unreliable denominator).
    """
    settings = settings or get_settings()
    streams: dict[str, dict[str, Any]] = {}
    for river, spec in _MAINSTEM_GAGES.items():
        lff = compute_low_flow_frequency(
            site_no=spec["gage"], receiving_water=river, settings=settings
        )
        stat = lff.stat("7Q10")
        q7 = stat.lp3_cfs.value if stat is not None else math.nan
        if lff.complete_years < min_years or math.isnan(q7) or q7 <= 0.0:
            log.warning(
                "basin.lowflow.omit",
                river=river,
                gage=spec["gage"],
                years=lff.complete_years,
                q7=q7,
            )
            continue
        streams[river.lower()] = {
            "seven_q10_cfs": round(q7, 2),
            "source": "derived",
            "gage": spec["gage"],
            "gage_name": lff.site_name,
            "period": f"{lff.period_start}..{lff.period_end}",
            "complete_years": lff.complete_years,
            "aliases": spec["aliases"],
            "citation": (
                f"LP3 7Q10 from USGS {spec['gage']} ({lff.site_name}), "
                f"{lff.complete_years} climatic years {lff.period_start[:4]}-{lff.period_end[:4]} "
                f"(gage value; screening proxy for the discharge reach)"
            ),
            "confidence": "medium",
        }
    log.info("basin.lowflow.derived", rivers=sorted(streams))
    return streams


def _derived_path(settings: Settings) -> Path:
    return settings.reference_dir / "hydrology" / _DERIVED_FILE


def write_derived_low_flows(
    streams: dict[str, dict[str, Any]], *, settings: Settings | None = None
) -> Path:
    """Write the derived 7Q10 companion to committed reference YAML; return the path."""
    settings = settings or get_settings()
    path = _derived_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "meta": {
            "subject": "DERIVED receiving-stream 7Q10s for the major Maumee-basin mainstems",
            "source": "USGS NWIS daily discharge -> log-Pearson III (bosc.hydrology.lowflow_frequency)",
            "discipline": (
                "DERIVED screening denominators (source=derived), NOT cited regulatory "
                "7Q10s — those live in low-flow-7q10.yaml. Each value is the 7Q10 AT THE "
                "GAGE, a proxy for a direct-discharge reach on that mainstem; a discharger "
                "on a tributary is screened only against that tributary's own cited/derived "
                "7Q10, never this one. Regenerate with `bosc derive-low-flows`."
            ),
        },
        "streams": streams,
    }
    path.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
    )
    log.info("basin.lowflow.wrote", path=str(path), rivers=len(streams))
    return path


def load_derived_low_flows(*, settings: Settings | None = None) -> dict[str, ProvenancedValue]:
    """Return ``{normalized alias -> derived 7Q10 ProvenancedValue}`` (or ``{}`` if absent)."""
    settings = settings or get_settings()
    path = _derived_path(settings)
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, ProvenancedValue] = {}
    for name, entry in (data.get("streams") or {}).items():
        if not isinstance(entry, dict) or entry.get("seven_q10_cfs") is None:
            continue
        pv = ProvenancedValue(
            value=float(entry["seven_q10_cfs"]),
            unit="cfs",
            source="derived",
            citation=entry.get("citation"),
            confidence=str(entry.get("confidence", "medium")),
        )
        for alias in entry.get("aliases") or [name]:
            out[_norm(str(alias))] = pv
    return out


# --------------------------------------------------------------------- the screen


class BasinCoverage(BaseModel):
    """How much of the basin POTW inventory the screen could actually evaluate."""

    model_config = ConfigDict(extra="forbid")

    total: int
    screened: int
    violations: int
    tight: int
    ok: int
    no_receiving_water: int  # ECHO has no receiving_water for the facility
    no_7q10: int  # named receiver, but no cited/derived 7Q10 (ungaged tributary/ditch)
    no_design_flow: int  # matched a 7Q10 but ECHO has no design flow to screen


class BasinScreen(BaseModel):
    """The basin-wide assimilative screen result + its coverage."""

    model_config = ConfigDict(extra="forbid")

    coverage: BasinCoverage
    checks: list[AssimilativeCheck]


def _load_dischargers(settings: Settings) -> list[dict[str, Any]]:
    path = settings.reference_dir / Path(*_POTW_INVENTORY)
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(data.get("facilities") or [])


def _match_low_flow(
    receiving_water: str, lookup: dict[str, ProvenancedValue]
) -> ProvenancedValue | None:
    """A cited/derived 7Q10 iff the PRIMARY receiver names the mainstem exactly.

    Only the first comma-separated surface form (the primary receiving water) is matched:
    a compound like ``"Baldwin Ditch, Maumee River"`` discharges to the *ditch*, so it
    must not borrow the downstream Maumee's far larger 7Q10 (that would overstate
    dilution). Typo/synonym duplicates of one mainstem ("Auglaize River, Auglaze River")
    still match on their primary form.
    """
    primary = receiving_water.split(",")[0]
    return lookup.get(_norm(primary))


def check_basin_assimilative(*, settings: Settings | None = None) -> BasinScreen:
    """Screen every basin POTW against its receiving water's cited or derived 7Q10.

    Cited 7Q10s (Lima-loop, ``source=document``) take precedence over derived mainstem
    7Q10s. Dischargers with no receiving water, no matchable 7Q10, or no design flow are
    counted in the coverage but not screened (omit, don't guess).
    """
    settings = settings or get_settings()
    cited = load_low_flows(settings=settings)
    derived = load_derived_low_flows(settings=settings)
    lookup = {**derived, **cited}  # cited overrides a derived alias on overlap

    checks: list[AssimilativeCheck] = []
    total = screened = no_rw = no_q7 = no_flow = 0
    bands = {"violation": 0, "tight": 0, "ok": 0}

    for fac in _load_dischargers(settings):
        total += 1
        water = fac.get("receiving_water")
        if not water or not str(water).strip():
            no_rw += 1
            continue
        q7 = _match_low_flow(str(water), lookup)
        if q7 is None:
            no_q7 += 1
            continue
        mgd = fac.get("design_flow_mgd")
        if mgd is None:
            no_flow += 1
            continue
        discharge_cfs = mgd_to_cfs(float(mgd))
        ratio = q7.value / discharge_cfs if discharge_cfs else 0.0
        flag = dilution_flag(ratio)
        bands[flag] += 1
        screened += 1
        name = str(water).split(",")[0].strip().title()
        checks.append(
            AssimilativeCheck(
                receiving_water=name,
                discharger=str(fac.get("name") or fac.get("npdes_id") or "?"),
                design_low_flow=q7,
                discharge=ProvenancedValue.from_reference(
                    round(discharge_cfs, 3),
                    "cfs",
                    citation=f"ECHO design flow {mgd} MGD ({fac.get('npdes_id')})",
                    confidence="medium",
                ),
                dilution_ratio=round(ratio, 3),
                flag=flag,
                detail=(
                    f"{name} 7Q10 {q7.value:.2f} cfs ({q7.source}) vs discharge "
                    f"{discharge_cfs:.2f} cfs -> {ratio:.2f}:1 dilution ({flag})"
                ),
            )
        )

    coverage = BasinCoverage(
        total=total,
        screened=screened,
        violations=bands["violation"],
        tight=bands["tight"],
        ok=bands["ok"],
        no_receiving_water=no_rw,
        no_7q10=no_q7,
        no_design_flow=no_flow,
    )
    log.info(
        "basin.screen",
        total=total,
        screened=screened,
        violations=bands["violation"],
        no_7q10=no_q7,
        no_receiving_water=no_rw,
    )
    return BasinScreen(coverage=coverage, checks=sorted(checks, key=lambda c: c.dilution_ratio))
