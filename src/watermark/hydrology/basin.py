"""Basin-wide low-flow assimilative screen + derived receiving-water 7Q10s.

The cited 7Q10 table (:mod:`watermark.hydrology.lowflow`) covers only the three Lima-loop
streams read off Ohio EPA fact sheets in our corpus. This module extends the
assimilative screen to the basin-wide POTW inventory (EPA ECHO dischargers per basin,
e.g. ``data/reference/echo/maumee-wwtp.potw.yaml``) by **deriving** a 7Q10 for the major
USGS-gaged mainstems via log-Pearson III (:mod:`watermark.hydrology.lowflow_frequency`) —
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
from pydantic import BaseModel, ConfigDict, Field

from watermark.config import Settings, get_settings
from watermark.hydrology.assimilative import dilution_flag
from watermark.hydrology.connectors import HydroOfflineError
from watermark.hydrology.lowflow import load_low_flows
from watermark.hydrology.lowflow_frequency import compute_low_flow_frequency
from watermark.hydrology.model import AssimilativeCheck, ProvenancedValue
from watermark.hydrology.units import mgd_to_cfs
from watermark.logging import get_logger

log = get_logger(__name__)

_DERIVED_FILE = "low-flow-7q10.derived.yaml"
# The basin POTW inventory the screen reads is selected by the active site's basin
# (``SiteProfile.basin``); a basin with no committed inventory yet screens against an
# empty set rather than borrowing another basin's dischargers.
_BASIN_POTW_INVENTORY: dict[str, tuple[str, str]] = {
    "maumee": ("echo", "maumee-wwtp.potw.yaml"),
    "great-miami": ("echo", "great-miami-wwtp.potw.yaml"),
    "scioto": ("echo", "scioto-wwtp.potw.yaml"),
    "little-miami": ("echo", "little-miami-wwtp.potw.yaml"),
}
_MIN_YEARS = 20  # climatic years of record needed for a defensible LP3 7Q10

# Curated major-network mainstem gages + synthesized headwaters confluences live as
# auditable reference DATA, not code: the committed ``mainstem-gages.yaml`` (gage IDs,
# aliases, and the drainage-area rationale). Loaded + schema-validated here (so a typo or a
# missing key in the reference table fails fast with a clear error, not a KeyError deep in
# the derivation) and fed to the LP3 derivation.
_MAINSTEM_GAGES_FILE = "mainstem-gages.yaml"


class MainstemGage(BaseModel):
    """One curated mainstem screening gage: USGS id + the ECHO receiving-water aliases."""

    model_config = ConfigDict(extra="forbid")

    gage: str
    aliases: list[str] = Field(min_length=1)  # a gage with no alias could never be matched
    note: str | None = None


class ConfluenceComponent(BaseModel):
    """One gaged tributary summed into a synthesized headwaters-confluence 7Q10."""

    model_config = ConfigDict(extra="forbid")

    gage: str
    label: str


class HeadwatersConfluence(BaseModel):
    """A mainstem formed by two gaged tributaries, with no long-record gage at the junction."""

    model_config = ConfigDict(extra="forbid")

    # Exactly the two tributaries whose 7Q10s sum to the confluence denominator: a single-
    # tributary "confluence" is meaningless (it would just be that gage), so the schema
    # forbids YAML edits that drop one.
    components: list[ConfluenceComponent] = Field(min_length=2, max_length=2)
    aliases: list[str] = Field(min_length=1)
    note: str | None = None


class _GageTable(BaseModel):
    """The whole committed ``mainstem-gages.yaml``, structure-validated in one pass.

    Both sections are required *and non-empty*: a missing/renamed top-level key or a
    truncated (empty) section is a reference-file error, not a silently-partial screen. The
    ``meta`` block (and any future annotation keys) is ignored, but every gage/confluence
    entry is validated by its nested model.
    """

    model_config = ConfigDict(extra="ignore")

    mainstems: dict[str, MainstemGage] = Field(min_length=1)
    headwaters_confluences: dict[str, HeadwatersConfluence] = Field(min_length=1)


def _mainstem_gages_path(settings: Settings) -> Path:
    return settings.reference_dir / "hydrology" / _MAINSTEM_GAGES_FILE


def _load_gage_table(settings: Settings) -> _GageTable:
    """Read + schema-validate the committed curated gage table.

    Raises ``FileNotFoundError`` if the reference input is absent, and a Pydantic
    ``ValidationError`` if its top-level shape (or any gage/confluence entry) is malformed —
    never a silently-empty screen from a wrong-shaped or truncated file.
    """
    path = _mainstem_gages_path(settings)
    if not path.is_file():
        raise FileNotFoundError(
            f"curated mainstem-gage table missing: {path} "
            "(committed reference input for the basin low-flow screen)"
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _GageTable.model_validate(raw)


def load_mainstem_gages(*, settings: Settings) -> dict[str, MainstemGage]:
    """``{river name -> MainstemGage}`` validated from the committed reference table."""
    return _load_gage_table(settings).mainstems


def load_headwaters_confluences(*, settings: Settings) -> dict[str, HeadwatersConfluence]:
    """``{confluence name -> HeadwatersConfluence}`` validated from the committed table."""
    return _load_gage_table(settings).headwaters_confluences


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
    for river, spec in load_mainstem_gages(settings=settings).items():
        try:
            lff = compute_low_flow_frequency(
                site_no=spec.gage, receiving_water=river, settings=settings
            )
        except HydroOfflineError:
            # A missing offline fixture is an infra gap, not a real data absence — surface it
            # loudly (the connector names the key to record) instead of silently omitting the
            # gage into a wrong "no 7Q10" result.
            raise
        except Exception as exc:
            # NWIS returned no data (e.g. a stage-only gage, or a gap in the
            # record window) — omit-don't-guess, same discipline as min_years.
            log.warning(
                "basin.lowflow.gage_error",
                river=river,
                gage=spec.gage,
                error=str(exc).splitlines()[0],
            )
            continue
        stat = lff.stat("7Q10")
        q7 = stat.lp3_cfs.value if stat is not None else math.nan
        if lff.complete_years < min_years or math.isnan(q7) or q7 <= 0.0:
            log.warning(
                "basin.lowflow.omit",
                river=river,
                gage=spec.gage,
                years=lff.complete_years,
                q7=q7,
            )
            continue
        streams[river.lower()] = {
            "seven_q10_cfs": round(q7, 2),
            "source": "derived",
            "gage": spec.gage,
            "gage_name": lff.site_name,
            "period": f"{lff.period_start}..{lff.period_end}",
            "complete_years": lff.complete_years,
            "aliases": spec.aliases,
            "citation": (
                f"LP3 7Q10 from USGS {spec.gage} ({lff.site_name}), "
                f"{lff.complete_years} climatic years {lff.period_start[:4]}-{lff.period_end[:4]} "
                f"(gage value; screening proxy for the discharge reach)"
            ),
            "confidence": "medium",
        }
    streams.update(_derive_confluences(settings=settings, min_years=min_years))
    log.info("basin.lowflow.derived", rivers=sorted(streams))
    return streams


def _derive_confluences(*, settings: Settings, min_years: int) -> dict[str, dict[str, Any]]:
    """Derive each synthesized headwaters-confluence 7Q10 (sum of its component gages).

    Same omit-don't-guess floor as the mainstem gages: a confluence is emitted only when
    *every* component gage clears ``min_years`` with a positive 7Q10. The sum is a
    conservative denominator (the tributaries' annual minima need not coincide); the entry
    records its components and is tagged ``confidence: low`` accordingly.
    """
    out: dict[str, dict[str, Any]] = {}
    for name, spec in load_headwaters_confluences(settings=settings).items():
        parts: list[dict[str, Any]] = []
        for component in spec.components:
            gage, label = component.gage, component.label
            try:
                lff = compute_low_flow_frequency(
                    site_no=gage, receiving_water=name, settings=settings
                )
            except HydroOfflineError:
                # Offline fixture gap — fail loud, don't silently drop the confluence.
                raise
            except Exception as exc:
                log.warning(
                    "basin.lowflow.confluence_gage_error",
                    confluence=name,
                    gage=gage,
                    error=str(exc).splitlines()[0],
                )
                parts = []
                break
            stat = lff.stat("7Q10")
            q7 = stat.lp3_cfs.value if stat is not None else math.nan
            if lff.complete_years < min_years or math.isnan(q7) or q7 <= 0.0:
                log.warning(
                    "basin.lowflow.confluence_omit",
                    confluence=name,
                    gage=gage,
                    years=lff.complete_years,
                    q7=q7,
                )
                parts = []
                break
            parts.append(
                {
                    "gage": gage,
                    "gage_name": label,
                    "seven_q10_cfs": round(q7, 2),
                    "complete_years": lff.complete_years,
                    "period_start": lff.period_start,
                    "period_end": lff.period_end,
                }
            )
        if not parts:
            continue
        total = round(sum(p["seven_q10_cfs"] for p in parts), 2)
        terms = " + ".join(f"USGS {p['gage']} {p['seven_q10_cfs']} cfs" for p in parts)
        out[name.lower()] = {
            "seven_q10_cfs": total,
            "source": "derived",
            "gage": "+".join(p["gage"] for p in parts),
            "gage_name": " + ".join(p["gage_name"] for p in parts),
            "period": f"{min(p['period_start'] for p in parts)}..{max(p['period_end'] for p in parts)}",
            "complete_years": min(p["complete_years"] for p in parts),
            "components": [
                {
                    "gage": p["gage"],
                    "gage_name": p["gage_name"],
                    "seven_q10_cfs": p["seven_q10_cfs"],
                }
                for p in parts
            ],
            "aliases": spec.aliases,
            "citation": (
                f"sum of LP3 7Q10s ({terms}) — the St. Joseph + St. Marys junction that forms "
                "the Maumee at Fort Wayne; conservative (component annual minima need not "
                "coincide, so the true confluence 7Q10 is >= this sum)"
            ),
            "confidence": "low",
        }
    return out


def _derived_path(settings: Settings) -> Path:
    return settings.reference_dir / "hydrology" / _DERIVED_FILE


def write_derived_low_flows(
    streams: dict[str, dict[str, Any]], *, settings: Settings | None = None
) -> Path:
    """Merge *streams* into the shared derived 7Q10 file and return the path.

    The file is shared across all basin onboard runs; keys are river names and
    don't collide between basins. Merging (not overwriting) ensures that a Sidney
    onboard run doesn't erase Maumee entries written by a Lima/Fort-Wayne run.
    """
    settings = settings or get_settings()
    path = _derived_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)

    existing: dict[str, Any] = {}
    if path.is_file():
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        existing = doc.get("streams") or {}

    merged = {**existing, **streams}
    doc = {
        "meta": {
            "subject": "DERIVED receiving-stream 7Q10s for the major mainstems of the network's river basins",
            "source": "USGS NWIS daily discharge -> log-Pearson III (watermark.hydrology.lowflow_frequency)",
            "discipline": (
                "DERIVED screening denominators (source=derived), NOT cited regulatory "
                "7Q10s — those live in low-flow-7q10.yaml. Each value is the 7Q10 AT THE "
                "GAGE, a proxy for a direct-discharge reach on that mainstem; a discharger "
                "on a tributary is screened only against that tributary's own cited/derived "
                "7Q10, never this one. Regenerate with `watermark derive-low-flows`."
            ),
        },
        "streams": merged,
    }
    path.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
    )
    log.info("basin.lowflow.wrote", path=str(path), rivers=len(merged), added=len(streams))
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


def _inventory_path(settings: Settings) -> Path:
    """The POTW inventory file for the active site's basin (``maumee-wwtp.potw.yaml`` etc.).

    Selected by ``SiteProfile.basin`` so a Great Miami site screens against the Great
    Miami inventory, never the Maumee one. An unregistered basin maps to the conventional
    ``<basin>-wwtp.potw.yaml`` name (absent file -> empty screen, never a wrong-basin one).
    """
    from watermark.sites import active_profile

    basin = active_profile(settings).basin
    rel = _BASIN_POTW_INVENTORY.get(basin, ("echo", f"{basin}-wwtp.potw.yaml"))
    return settings.reference_dir / Path(*rel)


def _load_dischargers(settings: Settings) -> list[dict[str, Any]]:
    path = _inventory_path(settings)
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


def load_dischargers(*, settings: Settings | None = None) -> list[dict[str, Any]]:
    """The basin POTW inventory (EPA ECHO Maumee dischargers), or ``[]`` if absent."""
    return _load_dischargers(settings or get_settings())


def build_low_flow_lookup(*, settings: Settings | None = None) -> dict[str, ProvenancedValue]:
    """Merged ``{normalized receiver -> 7Q10}``: cited (document) overrides derived on overlap."""
    settings = settings or get_settings()
    return {**load_derived_low_flows(settings=settings), **load_low_flows(settings=settings)}


def screen_facility(
    fac: dict[str, Any], lookup: dict[str, ProvenancedValue]
) -> tuple[AssimilativeCheck | None, str]:
    """Screen one POTW record against its primary receiver's 7Q10 (omit, don't guess).

    Returns ``(check, "screened")`` with a populated :class:`AssimilativeCheck`, or
    ``(None, reason)`` where ``reason`` is one of ``no_receiving_water`` / ``no_7q10`` /
    ``no_design_flow``. Shared by the basin-wide screen and the cross-site network synthesis.
    """
    water = fac.get("receiving_water")
    if not water or not str(water).strip():
        return None, "no_receiving_water"
    q7 = _match_low_flow(str(water), lookup)
    if q7 is None:
        return None, "no_7q10"
    mgd = fac.get("design_flow_mgd")
    if mgd is None:
        return None, "no_design_flow"
    discharge_cfs = mgd_to_cfs(float(mgd))
    ratio = q7.value / discharge_cfs if discharge_cfs else 0.0
    flag = dilution_flag(ratio)
    name = str(water).split(",")[0].strip().title()
    check = AssimilativeCheck(
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
    return check, "screened"


def check_basin_assimilative(*, settings: Settings | None = None) -> BasinScreen:
    """Screen every basin POTW against its receiving water's cited or derived 7Q10.

    Cited 7Q10s (Lima-loop, ``source=document``) take precedence over derived mainstem
    7Q10s. Dischargers with no receiving water, no matchable 7Q10, or no design flow are
    counted in the coverage but not screened (omit, don't guess).
    """
    settings = settings or get_settings()
    lookup = build_low_flow_lookup(settings=settings)

    checks: list[AssimilativeCheck] = []
    total = screened = no_rw = no_q7 = no_flow = 0
    bands = {"violation": 0, "tight": 0, "ok": 0}

    for fac in load_dischargers(settings=settings):
        total += 1
        check, status = screen_facility(fac, lookup)
        if status == "no_receiving_water":
            no_rw += 1
            continue
        if status == "no_7q10":
            no_q7 += 1
            continue
        if status == "no_design_flow":
            no_flow += 1
            continue
        assert check is not None  # status == "screened"
        bands[check.flag] += 1
        screened += 1
        checks.append(check)

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
