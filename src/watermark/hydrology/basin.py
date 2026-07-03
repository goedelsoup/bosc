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
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.hydrology.assimilative import dilution_flag
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

# Curated major network mainstems with a long-record USGS gage, grouped by basin.
# ``aliases`` are the exact ECHO ``receiving_water`` surface forms (comma-split) that
# mean a *direct* discharge to this mainstem — not a tributary "via"/"to" it. Each gage
# is verified to return a multi-decade daily-discharge record from NWIS, and is the
# lower/mouth-ward mainstem gage (the Maumee-at-Waterville convention): one
# medium-confidence screening proxy per mainstem, applied basin-wide by receiving-water
# name. (Little Auglaize is omitted: its only gage, 04191058, has <10 yr of record.)
# The derived table is a single shared file keyed by receiving-water name across basins;
# names don't collide between the Maumee and Great Miami, so one merged lookup is safe.
_MAINSTEM_GAGES: dict[str, dict[str, Any]] = {
    # Maumee basin (subregion 0410, Western Lake Erie).
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
    # Great Miami basin (subregion 0508, → Ohio River). Mad River uses the lower-reach
    # gage near Springfield (03269500, DA 490 mi²); the upper reach near Urbana
    # (03267000, DA ~160 mi², a smaller 7Q10) is the site abstraction gage, not the
    # basin-screen proxy. Great Miami River uses the mouth-ward gage at Hamilton.
    "Mad River": {"gage": "03269500", "aliases": ["mad river"]},
    "Great Miami River": {
        "gage": "03274000",
        "aliases": ["great miami river", "great miami r", "miami river"],
    },
    # Scioto basin (subregion 0506, → Ohio River). Scioto River uses the mouth-ward gage
    # at Higby (03234500, DA 5131 mi²). Big Walnut Creek (03229500) is the New Albany
    # Scioto-side receiving water; the Olentangy uses the near-Worthington gage (03227000
    # at Columbus has no discharge record in-window).
    "Scioto River": {"gage": "03234500", "aliases": ["scioto river", "scioto r"]},
    "Olentangy River": {"gage": "03226800", "aliases": ["olentangy river", "olentangy r"]},
    "Big Walnut Creek": {
        "gage": "03229500",
        "aliases": ["big walnut creek", "big walnut cr", "big walnut"],
    },
    "Big Darby Creek": {
        "gage": "03230500",
        "aliases": ["big darby creek", "big darby cr", "big darby"],
    },
    # Little Miami basin (subregion 0507, → Ohio River). The mainstem proxy is the
    # long-record Milford gage (03245500, DA 1664 mi²). Todd Fork (Wilmington's
    # receiving water) has no active USGS gage — the historical Greenfield gage
    # (03244000) was discontinued; Todd Fork dischargers stay unscreened (no_7q10)
    # rather than being proxied to a larger downstream river (that would overstate
    # dilution). Milford (downstream integrator, incl. Todd Fork) and the upstream
    # Xenia reach at Oldtown (03240000) BRACKET the ungaged Todd Fork above and below;
    # a drainage-area-ratio interpolation off these two brackets is the documented
    # at-site 7Q10 basis for the Wilmington Air Park / WWTP screen (#516; derivation +
    # cited drainage areas in data/extracted/wilmington/low-flow-screen.md), NOT an
    # auto-applied ECHO proxy. Oldtown uses a non-colliding alias so it does not
    # capture ECHO's bare "little miami river" (aliased to Milford above). Caesar
    # Creek (03242350, below Caesar Creek Lake) reflects a regulated low-flow regime.
    # NWIS currently returns no daily discharge values for this gage (possibly a
    # stage-only installation); it is skipped gracefully by the per-gage error guard
    # and Caesar Creek dischargers remain no_7q10.
    "Little Miami River": {
        "gage": "03245500",
        "aliases": ["little miami river", "little miami"],
    },
    "Little Miami River near Oldtown": {
        "gage": "03240000",
        "aliases": ["little miami river near oldtown", "little miami r near oldtown"],
    },
    "Caesar Creek": {
        "gage": "03242350",
        "aliases": ["caesar creek"],
    },
    # Ohio Brush Creek basin (subregion 0509, HUC-8 05090201 "Ohio Brush-Whiteoak", direct to the
    # Ohio River — the network's first non-Lake-Erie / non-glaciated Appalachian branch, West Union
    # #1117). The only substantive active gage on the creek is Ohio Brush Creek near West Union
    # (03237500, DA 387 mi², daily discharge since 1926); the West Fork gages (03237400 Lawshe,
    # 03237295 Peebles) are trivial/short-record and are omitted rather than proxied.
    # Non-colliding aliases only: a bare "brush creek" would capture ECHO's unrelated Maumee-basin
    # "BRUSH CREEK" receiving water (a different stream) and misroute it to this southern-Ohio gage.
    "Ohio Brush Creek": {
        "gage": "03237500",
        "aliases": ["ohio brush creek", "ohio brush ck"],
    },
    # Greenville (Darke Co.) receiving waters. Greenville Creek is the primary at-site
    # gage (Bradford gage 03264000, DA 193 mi²); Stillwater River at Pleasant Hill
    # (03265000, DA 503 mi²) is the downstream context after Greenville Creek enters the
    # Stillwater mainstem. These are the only actively gaged reaches on the site's
    # Stillwater/Greenville Creek corridor.
    "Greenville Creek": {
        "gage": "03264000",
        "aliases": ["greenville creek", "greenville ck"],
    },
    "Stillwater River": {
        "gage": "03265000",
        "aliases": ["stillwater river", "stillwater r"],
    },
    # Great Miami basin — Sidney reach. The mouth-ward Hamilton gage (03274000) above is the
    # basin-wide "GREAT MIAMI RIVER" ECHO screen proxy. These two entries serve the Sidney
    # site-level 7Q10 (the at-site upper reach) and the Loramie Creek tributary screen.
    # Great Miami at Sidney (03261500, DA 601 mi²) uses a non-colliding alias so it doesn't
    # capture ECHO's bare "GREAT MIAMI RIVER" (already aliased to Hamilton above).
    "Great Miami River at Sidney": {
        "gage": "03261500",
        "aliases": ["great miami river at sidney", "great miami r at sidney"],
    },
    "Loramie Creek": {
        "gage": "03262000",
        "aliases": ["loramie creek"],
    },
    # Great Miami basin — WPAFB / Dayton reaches (#464). The mouth-ward Hamilton gage (03274000)
    # is the basin-wide "GREAT MIAMI RIVER" ECHO proxy; these two serve the WPAFB site-level 7Q10
    # at the at-base reaches (the Mad River near Dayton is WPAFB's abstraction/supply gage; the
    # Great Miami at Dayton is the well-field mainstem). Both use non-colliding aliases so they
    # don't capture ECHO's bare "MAD RIVER" / "GREAT MIAMI RIVER" (aliased to Springfield/Hamilton
    # above). NB: values populate on the next connectivity-permitting `derive-low-flows` run —
    # this step hit a transient USGS 503 at WPAFB onboarding (2026-06-22); the derived table is
    # otherwise committed and unchanged.
    "Mad River at Dayton": {
        "gage": "03270000",  # Mad River near Dayton OH (WPAFB at-base reach; DA ~635 mi²)
        "aliases": ["mad river at dayton", "mad river near dayton", "mad river (dayton reach)"],
    },
    "Great Miami River at Dayton": {
        "gage": "03270500",  # Great Miami River at Dayton OH (well-field mainstem reach)
        "aliases": ["great miami river at dayton", "great miami r at dayton"],
    },
}

# Synthesized headwaters-confluence 7Q10s: a mainstem formed by the junction of two gaged
# tributaries, where no single LONG-record gage sits at the confluence itself (the Maumee
# mainstem gage at Fort Wayne, 04182900, has only ~13 yr — below ``_MIN_YEARS``). The
# confluence 7Q10 is the SUM of the component tributaries' 7Q10s — a CONSERVATIVE proxy:
# the two streams' annual 7-day minima need not coincide, so the true confluence 7Q10 is
# ``>=`` the sum (#358). Aliases are point-specific and deliberately EXCLUDE the bare
# "maumee river" (that is the lower-basin Waterville proxy, 114 cfs). They are screen-inert
# by design: the Fort Wayne WWTP (IN0032191) discharges to an ungaged ditch ("Baldwin Ditch,
# Maumee R …"), so it is screened only on that primary receiver (left unscreened, omit-don't-
# guess) — this entry is the documented at-mainstem denominator for the manual receiving-water
# characterization, not an auto-applied screen value.
_HEADWATERS_CONFLUENCES: dict[str, dict[str, Any]] = {
    "Maumee River (Fort Wayne headwaters)": {
        "components": [
            ("04180500", "St. Joseph River near Fort Wayne, IN"),
            ("04182000", "St. Marys River near Fort Wayne, IN"),
        ],
        "aliases": [
            "maumee river at fort wayne",
            "maumee river (fort wayne headwaters)",
            "maumee river headwaters",
        ],
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
        try:
            lff = compute_low_flow_frequency(
                site_no=spec["gage"], receiving_water=river, settings=settings
            )
        except Exception as exc:
            # NWIS returned no data (e.g. a stage-only gage, or a gap in the
            # record window) — omit-don't-guess, same discipline as min_years.
            log.warning(
                "basin.lowflow.gage_error",
                river=river,
                gage=spec["gage"],
                error=str(exc).splitlines()[0],
            )
            continue
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
    for name, spec in _HEADWATERS_CONFLUENCES.items():
        parts: list[dict[str, Any]] = []
        for gage, label in spec["components"]:
            try:
                lff = compute_low_flow_frequency(
                    site_no=gage, receiving_water=name, settings=settings
                )
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
            "aliases": spec["aliases"],
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
