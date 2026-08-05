"""EPA ECHO (Enforcement and Compliance History Online) NPDES connector.

Pulls the inventory of CWA-permitted facilities in a watershed from ECHO's Clean
Water Act REST services (``cwa_rest_services``) at ``echodata.epa.gov``. Used to
build verified per-basin inventories of wastewater dischargers (the Maumee, Great
Miami, Little Miami, Scioto, and Ohio Brush Creek today; a basin is a :class:`Basin`
registry entry, never hardcoded).

A basin is a set of USGS HUC-8 subbasins (e.g. the Maumee's seven in
:data:`MAUMEE_HUC8S`, the Scioto's three in :data:`SCIOTO_HUC8S`). ECHO is queried one
HUC-8 at a time and the results are deduplicated to one row per physical facility by FRS
Registry ID (:func:`deduplicate`).

Call pattern, per HUC-8 (mirrors the documented ECHO flow):

1. ``get_facilities`` (``p_huc``, ``p_act=Y``) validates the query and returns a
   **QID** (query id, valid ~30 min) plus summary stats including a row count.
2. ``get_qid`` pages the result set as JSON, selecting columns by ID (``qcolumns``).

Every response is recorded through :func:`_cache.cached_get` so a rerun never
re-fetches — which also keeps us comfortably under ECHO's throttle (300 req/hr,
1,500/day). Figures and identifiers are taken verbatim from the API; this module
never fabricates or infers a facility, permit, or value the API did not return.

Synchronous (``httpx.Client``) to match BOSC's otherwise-sync pipeline layer.

Verified against ``cwa_rest_services`` metadata ``CWA v2017-10-13 1325``
(260 result columns). Notably **CWNS ID is NOT a column** in this service — see
the module note in :mod:`watermark.cli` / the inventory output for that gap.

The one thing that is *not* verbatim ECHO is the **curated receiving-water overlay**
(:mod:`watermark.hydrology.connectors.echo_curation`, #1698): a committed, cited set of
corrections re-applied on every pull, so refreshing a basin never clobbers reviewed data.
Corrections are declared there, never typed into the regenerated output by hand, and a
correction that stops reconciling against live ECHO refuses the write rather than
overriding it silently.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import httpx
import yaml
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.connectors import to_float, to_int, to_str
from watermark.hydrology.connectors import echo_curation
from watermark.hydrology.connectors._cache import cached_get
from watermark.hydrology.connectors.echo_curation import Curation
from watermark.logging import get_logger

log = get_logger(__name__)

# The seven HUC-8 subbasins that make up the Maumee River watershed (subregion
# 0410, Western Lake Erie). Adjacent WLE subbasins 04100001 (Ottawa-Stony),
# 04100002 (Raisin) and 04100010 (Cedar-Portage) are NOT Maumee drainage and are
# deliberately excluded.
MAUMEE_HUC8S: dict[str, str] = {
    "04100003": "St. Joseph",
    "04100004": "St. Marys",
    "04100005": "Upper Maumee",
    "04100006": "Tiffin",
    "04100007": "Auglaize",
    "04100008": "Blanchard",
    "04100009": "Lower Maumee",
}

# Subbasins flagged by the optional task requirement (Auglaize + Blanchard, the
# Lima / Allen County reach of the Ottawa River).
LIMA_AREA_HUC8S = frozenset({"04100007", "04100008"})

# The Great Miami River basin (subregion 0508, an Ohio River tributary): the two Ohio
# HUC-8 subbasins the network's Miami sites sit on (Urbana/Springfield → 05080001;
# WPAFB/Troy-Piqua/Hamilton-Middletown → 05080001/05080002). The Mad River is within
# Upper Great Miami (05080001). Whitewater (05080003) is predominantly Indiana drainage
# and is deliberately excluded, mirroring the Maumee's excluded non-basin WLE neighbors.
GREAT_MIAMI_HUC8S: dict[str, str] = {
    "05080001": "Upper Great Miami",
    "05080002": "Lower Great Miami",
}

# The Little Miami River basin (subregion 0509, an Ohio River tributary): a single HUC-8
# cataloging unit (05090202) that both network points sit on — Xenia (05090202, upstream
# near Oldtown) and Wilmington / Todd Fork (05090202, the Clinton County tributary). The
# Little Miami is a National & State Scenic River. Adjacent Mill Creek (05090203, the
# Cincinnati urban drainage) is NOT Little Miami drainage and is deliberately excluded,
# mirroring the Maumee's excluded WLE neighbors and the Great Miami's excluded Whitewater.
LITTLE_MIAMI_HUC8S: dict[str, str] = {
    "05090202": "Little Miami",
}

# The Scioto River basin (subregion 0506, an Ohio River tributary): three HUC-8 subbasins.
# The Columbus metro + the New Albany Scioto-side cluster (Big Walnut/Olentangy/Darby) sit in
# Upper Scioto (05060001). The New Albany epicenter also spills east across the divide into the
# Licking River (Muskingum basin, subregion 0504) — that side is NOT Scioto drainage and is
# tracked separately, not in this inventory.
SCIOTO_HUC8S: dict[str, str] = {
    "05060001": "Upper Scioto",
    "05060002": "Lower Scioto",
    "05060003": "Paint",
}

# The Ohio Brush Creek basin (subregion 0509): a single HUC-8 cataloging unit, 05090201
# "Ohio Brush-Whiteoak" — the network's first **direct-to-Ohio-River** branch (West Union /
# Adams County, #1117/#1120), draining straight to the Ohio with no Scioto or Miami loop.
#
# ⚠️ THIS HUC-8 IS NOT A WATERSHED, and the slug is a part naming a whole in a way no other
# registered basin's is. `maumee` covers the St. Joseph, St. Marys, Tiffin, Auglaize and
# Blanchard because those are all Maumee *drainage* — one river's tree. 05090201 is a WBD
# cataloging unit spanning BOTH banks of the Ohio River, and the pull says so on its own:
# facilities come back in Kentucky counties and Ohio ones, which face each other across the
# river. Several separate creeks reach the Ohio inside it; each is a SIBLING of Ohio Brush
# Creek, not a headwater of it. (The unit's HUC-12 composition and area are not in the corpus
# — no WBD extract for 05090201 is committed — so no figure for either is asserted anywhere
# this connector writes.)
#
# A HUC-8 is the finest unit ECHO's `p_huc` query accepts, so all of it comes with the pull
# and belongs in the inventory. What none of it may do is borrow Ohio Brush Creek's low flow.
# `basin._match_low_flow` is the guard — a discharger is screened only where its ECHO
# receiving water names one gaged water and nothing else, so only a receiver that names Ohio
# Brush Creek matches its gage — and `mainstem-gages.yaml` deliberately withholds a bare
# "brush creek" alias for the same reason (this pull contains a Campbell County KY "BRUSH CRK"
# on the far side of the river that such an alias would have misrouted to the West Union
# gage). The slug is retained because it names the NETWORK's basin group, which is the site's
# own drainage: it is what `SiteProfile.basin`, `data/sites.yaml`'s `basin_major` and the
# frontend `placement.ts` row already carry. The caveats on the Basin below carry the
# discrepancy into the emitted file, so a reader of the inventory is never left to infer the
# scope from the filename.
OHIO_BRUSH_CREEK_HUC8S: dict[str, str] = {
    "05090201": "Ohio Brush-Whiteoak",
}


@dataclass(frozen=True)
class Basin:
    """A watershed the ECHO inventory can be pulled for, selected by ``--basin`` slug.

    ``huc8s`` are the subbasins queried (one ECHO request each); ``area_huc8s`` is the
    optional sub-region flagged on each record (the Maumee's Lima reach) — empty for a
    basin with no such flag. Adding a basin is a registry entry here, never a new code
    path, keeping the connector basin-agnostic per the repo's site axis.

    ``caveats`` are stamped verbatim into every file this basin emits, on every pull, by
    :func:`_facilities_doc`. Two rules follow from that. **No observed counts**: a figure typed
    here is frozen at the pull that suggested it, and the next quarterly refresh republishes it
    as if current — dated headline counts belong in ``data/reference/echo/README.md``, under the
    pull date that produced them. **Nothing scoped to one emitted file**: the same tuple is
    written into the all-NPDES inventory and the POTW subset, so a caveat quantifying one of them
    is a false statement in the other (the curated-correction block beside it is scoped to the
    rows a file actually holds; caveats are not). State the standing properties of the basin and
    the discipline the screen applies to it, both of which survive a re-pull.
    """

    slug: str
    huc8s: dict[str, str]
    watershed: str
    subject: str
    file_stem: str
    area_huc8s: frozenset[str] = frozenset()
    caveats: tuple[str, ...] = ()


MAUMEE = Basin(
    slug="maumee",
    huc8s=MAUMEE_HUC8S,
    watershed="Maumee River — 7 HUC-8 subbasins, subregion 0410 (Western Lake Erie)",
    subject="Maumee-watershed NPDES wastewater dischargers",
    file_stem="maumee-wwtp",
    area_huc8s=LIMA_AREA_HUC8S,
    caveats=(
        "Four subbasins cross into IN/MI — cross-check Ohio EPA / IDEM / EGLE for completeness.",
        "ottawa_discharge keys on the sparse receiving_water field and undercounts.",
    ),
)
GREAT_MIAMI = Basin(
    slug="great-miami",
    huc8s=GREAT_MIAMI_HUC8S,
    watershed="Great Miami River — 2 HUC-8 subbasins, subregion 0508 (Ohio River tributary)",
    subject="Great Miami-watershed NPDES wastewater dischargers",
    file_stem="great-miami-wwtp",
    caveats=(
        "Whitewater (05080003) is predominantly Indiana drainage and is excluded; cross-check "
        "Ohio EPA / IDEM near the basin mouth for completeness.",
    ),
)
SCIOTO = Basin(
    slug="scioto",
    huc8s=SCIOTO_HUC8S,
    watershed="Scioto River — 3 HUC-8 subbasins, subregion 0506 (Ohio River tributary)",
    subject="Scioto-watershed NPDES wastewater dischargers",
    file_stem="scioto-wwtp",
    caveats=(
        "The New Albany cluster straddles the Scioto/Muskingum divide; its Licking River "
        "(Muskingum, subregion 0504) side is NOT in this Scioto inventory.",
    ),
)
LITTLE_MIAMI = Basin(
    slug="little-miami",
    huc8s=LITTLE_MIAMI_HUC8S,
    watershed="Little Miami River — 1 HUC-8 subbasin, subregion 0509 (Ohio River tributary, Scenic River)",
    subject="Little Miami-watershed NPDES wastewater dischargers",
    file_stem="little-miami-wwtp",
    caveats=(
        "Mill Creek (05090203, the Cincinnati urban drainage) is the adjacent 0509 basin and is "
        "excluded; cross-check Ohio EPA near the basin mouth for completeness.",
        "Todd Fork (the Wilmington / Clinton County tributary) is ungaged — the at-site dilution "
        "screen relies on the downstream Little Miami integrator at Milford.",
    ),
)
OHIO_BRUSH_CREEK = Basin(
    slug="ohio-brush-creek",
    huc8s=OHIO_BRUSH_CREEK_HUC8S,
    watershed=(
        "Ohio Brush Creek — 1 HUC-8 subbasin (05090201 Ohio Brush-Whiteoak), subregion 0509 "
        "(direct to the Ohio River)"
    ),
    subject="Ohio Brush Creek-basin NPDES wastewater dischargers",
    file_stem="ohio-brush-creek-wwtp",
    caveats=(
        "SCOPE IS WIDER THAN THE NAME. HUC-8 05090201 'Ohio Brush-Whiteoak' is a WBD cataloging "
        "unit spanning BOTH banks of the Ohio River, not one watershed — read each row's county: "
        "they fall on the Kentucky bank and the Ohio bank alike. Several separate creeks reach "
        "the Ohio inside it, and each is a SIBLING of Ohio Brush Creek rather than a headwater "
        "of it: a discharger on one is neither upstream nor downstream of one on Ohio Brush "
        "Creek, and must never borrow its 7Q10. Only a receiving water naming Ohio Brush Creek "
        "matches that gage; a bare 'Brush Creek' does not (this pull holds a Campbell County KY "
        "'BRUSH CRK' on the far side of the river).",
        "Because the unit spans both banks it is majority-Kentucky, and completeness therefore "
        "needs BOTH agencies: cross-check Ohio EPA for the Ohio side and Kentucky DOW for the "
        "Kentucky side. Neither agency's list is reflected here beyond what ECHO federalizes. "
        "ECHO also returns no county at all for part of the pull, so a county tally taken off "
        "this file under-counts rather than resolving to zero.",
        "Where receiving_water is null the row is unscreenable — including for every Adams "
        "County POTW that is not on the Ohio River mainstem (Peebles, Seaman, West Union "
        "OH0028088, Winchester), so the plants nearest the network's watershed point are exactly "
        "the ones ECHO cannot place. The assimilative screen keys on that field, so an unnamed "
        "receiver reports as unmatched, never as unaffected. The gap closes only through cited "
        "entries in the curated receiving-water overlay, never by inference from a facility's "
        "name or county.",
        "A row whose receiving_water names TWO different waters is refused too, not resolved to "
        "the larger one: ECHO's field is a permit-level aggregate over every outfall, so "
        "'OHIO RIVER, TWELVE MILE CREEK' does not say which water carries the design flow. Those "
        "rows report no_7q10 alongside the ungaged ones.",
        "Whiteoak, Eagle, Straight and Beasley Fork are ungaged for a defensible low-flow "
        "statistic (no NWIS daily-discharge record meeting the 20-climatic-year floor), so their "
        "dischargers stay unscreened rather than screening against a proxy.",
        "The Ohio River denominator these files' screened rows use is USGS 03216600 at Greenup "
        "Dam, upstream of every facility here and scoped in mainstem-gages.yaml to this basin "
        "alone — it is not a valid Ohio River 7Q10 for a basin that meets the river elsewhere.",
    ),
)
BASINS: dict[str, Basin] = {
    b.slug: b for b in (MAUMEE, GREAT_MIAMI, LITTLE_MIAMI, SCIOTO, OHIO_BRUSH_CREEK)
}

# Merged HUC-8 -> name map for the per-HUC fetch display label, DERIVED from the registry so
# registering a basin cannot leave it behind. A hand-maintained second copy failed silently:
# `fetch_huc_facilities` falls back to `_HUC8_NAMES.get(huc8, huc8)`, so an omitted subbasin
# would write the raw HUC code into the committed huc-counts.yaml `name:` field rather than
# raise. Adding a basin is one registry entry (`BASINS`), never two.
_HUC8_NAMES: dict[str, str] = {
    huc8: name for b in BASINS.values() for huc8, name in b.huc8s.items()
}

# Result columns to request, selected *by ObjectName* against the verified
# metadata and mapped to their ColumnID for the ``qcolumns`` parameter. get_qid
# returns rows keyed by ObjectName regardless, so downstream code reads by name.
_COLUMNS: dict[str, int] = {
    "CWPName": 1,  # facility name
    "RegistryID": 9,  # FRS Registry ID (the dedup key)
    "SourceID": 2,  # primary NPDES / permit (source) ID
    "NPDESIDs": 31,  # all NPDES IDs at this facility (multi-permit -> secondary col)
    "CWPFacilityTypeIndicator": 28,  # POTW / NON-POTW
    "CWPFacilityTypeCode": 29,
    "CWPPermitTypeDesc": 54,  # e.g. "NPDES Individual Permit", "...(Non-NPDES)"
    "CWPTotalDesignFlowNmbr": 26,  # permitted design flow, MGD (often null)
    "CWPStateWaterBodyName": 159,  # receiving water body (often null)
    "FacDerivedHuc": 19,  # HUC-8 ECHO derived this facility into (reliable)
    "RadWBDHuc12": 170,  # WBD HUC-12 (RAD)
    "FacLat": 24,
    "FacLong": 25,
    "FacCountyName": 13,
    "FacFederalAgencyName": 18,  # non-null => federal facility
    "CWPSNCStatus": 98,  # current CWA compliance status
    "CWPInformalEnfActCount": 113,  # informal enforcement actions
    "CWPFormalEaCnt": 114,  # formal enforcement actions
}

# Summary-stat keys returned by get_facilities, recorded for the count manifest.
_STAT_KEYS = ("QueryRows", "IndianCountryRows", "SVRows", "CVRows", "FEARows", "InfFEARows")


class Facility(BaseModel):
    """One CWA-permitted facility as returned by ECHO, fields read by ObjectName.

    Values are passed through verbatim (strings as ECHO sends them); only the
    obvious numerics are coerced. ``None`` means ECHO returned no value — never a
    fabricated default.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None
    frs_registry_id: str | None
    npdes_id: str | None  # primary SourceID
    npdes_ids_all: str | None  # ECHO's NPDESIDs field (space/again-delimited)
    facility_type: str | None  # POTW / NON-POTW
    facility_type_code: str | None
    permit_type: str | None
    design_flow_mgd: float | None
    receiving_water: str | None
    huc8: str | None  # FacDerivedHuc
    huc12: str | None
    latitude: float | None
    longitude: float | None
    county: str | None
    federal_agency: str | None
    compliance_status: str | None
    informal_enf_count: int | None
    formal_enf_count: int | None
    queried_huc8: str  # the p_huc this row was returned under

    @classmethod
    def from_row(cls, row: dict[str, Any], *, queried_huc8: str) -> Facility:
        return cls(
            name=to_str(row.get("CWPName")),
            frs_registry_id=to_str(row.get("RegistryID")),
            npdes_id=to_str(row.get("SourceID")),
            npdes_ids_all=to_str(row.get("NPDESIDs")),
            facility_type=to_str(row.get("CWPFacilityTypeIndicator")),
            facility_type_code=to_str(row.get("CWPFacilityTypeCode")),
            permit_type=to_str(row.get("CWPPermitTypeDesc")),
            design_flow_mgd=to_float(row.get("CWPTotalDesignFlowNmbr")),
            receiving_water=to_str(row.get("CWPStateWaterBodyName")),
            huc8=to_str(row.get("FacDerivedHuc")),
            huc12=to_str(row.get("RadWBDHuc12")),
            latitude=to_float(row.get("FacLat")),
            longitude=to_float(row.get("FacLong")),
            county=to_str(row.get("FacCountyName")),
            federal_agency=to_str(row.get("FacFederalAgencyName")),
            compliance_status=to_str(row.get("CWPSNCStatus")),
            informal_enf_count=to_int(row.get("CWPInformalEnfActCount")),
            formal_enf_count=to_int(row.get("CWPFormalEaCnt")),
            queried_huc8=queried_huc8,
        )

    @property
    def is_potw(self) -> bool:
        """True iff ECHO classifies this as a publicly owned treatment works."""
        return (self.facility_type or "").strip().upper() == "POTW"

    @property
    def is_federal(self) -> bool:
        return bool(self.federal_agency)


class HucResult(BaseModel):
    """The facilities returned for one HUC-8, plus ECHO's reported summary stats."""

    model_config = ConfigDict(extra="forbid")

    huc8: str
    name: str
    query_id: str | None
    reported_count: int | None  # ECHO's QueryRows
    stats: dict[str, str]
    facilities: list[Facility]


def _get(settings: Settings, service: str, params: dict[str, Any]) -> dict[str, Any]:
    """Perform (or replay from cache) one ECHO REST request; return ``Results``."""
    query = {"output": "JSON", **params}

    def fetch() -> Any:
        url = f"{settings.echo_base_url}/cwa_rest_services.{service}"
        # ECHO throttles at 300 req/hr; back off and retry on 429 so a transient
        # throttle mid-pull doesn't lose the (already-cached) earlier HUCs.
        for attempt in range(settings.echo_max_retries):
            resp = httpx.get(url, params=query, timeout=settings.hydro_request_timeout_s)
            if resp.status_code == 429 and attempt < settings.echo_max_retries - 1:
                wait = settings.echo_retry_base_s * (2**attempt)
                log.info("echo.throttled", service=service, attempt=attempt, wait_s=wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        return None  # unreachable: loop either returns or raise_for_status raises

    # Namespace the cache key by service so get_facilities and get_qid don't collide.
    payload = cached_get("echo", {"_service": service, **query}, fetch, settings=settings)
    results = cast("dict[str, Any]", payload).get("Results", payload)
    if isinstance(results, dict) and "Error" in results:
        raise EchoError(f"ECHO {service} error: {results['Error']}")
    return cast("dict[str, Any]", results)


class EchoError(RuntimeError):
    """ECHO returned an Error object (bad params, throttling, expired QID, ...)."""


def fetch_huc_facilities(
    huc8: str,
    *,
    page_size: int = 1000,
    settings: Settings | None = None,
) -> HucResult:
    """All active-permit facilities ECHO returns for one HUC-8.

    ``get_facilities`` (p_huc, p_act=Y) -> QID + count, then ``get_qid`` paged.
    """
    settings = settings or get_settings()
    name = _HUC8_NAMES.get(huc8, huc8)
    qcolumns = ",".join(str(cid) for cid in _COLUMNS.values())

    summary = _get(settings, "get_facilities", {"p_huc": huc8, "p_act": "Y"})
    qid = to_str(summary.get("QueryID"))
    reported = to_int(summary.get("QueryRows"))
    stats = {k: str(summary[k]) for k in _STAT_KEYS if summary.get(k) is not None}
    log.info("echo.huc", huc8=huc8, name=name, qid=qid, reported=reported)

    facilities: list[Facility] = []
    if qid:
        page = 1
        while True:
            res = _get(
                settings,
                "get_qid",
                {"qid": qid, "pageno": page, "responseset": page_size, "qcolumns": qcolumns},
            )
            rows = res.get("Facilities") or []
            facilities.extend(Facility.from_row(r, queried_huc8=huc8) for r in rows)
            # A short/empty page is the real end-of-data signal. ECHO's `reported`
            # (QueryRows) is a summary-stat estimate that can be stale-low; using it
            # to terminate the loop silently truncates the inventory (#1157). It is a
            # cross-check only — logged below when it disagrees, never a terminator.
            if len(rows) < page_size:
                break
            page += 1

    pulled = len(facilities)
    if reported is not None and pulled != reported:
        # A complete pull that disagrees with the stale summary stat: keep every row
        # (truncation is worse than an extra page for a verified inventory), but
        # surface the mismatch — the count manifest records reported vs rows_pulled.
        log.warning("echo.count_mismatch", huc8=huc8, name=name, reported=reported, pulled=pulled)

    return HucResult(
        huc8=huc8,
        name=name,
        query_id=qid,
        reported_count=reported,
        stats=stats,
        facilities=facilities,
    )


def resolve_basin(basin: Basin | str) -> Basin:
    """A :class:`Basin` from itself or its slug (raises on an unregistered slug)."""
    if isinstance(basin, Basin):
        return basin
    try:
        return BASINS[basin]
    except KeyError as exc:
        raise EchoError(f"unknown basin {basin!r}; registered: {sorted(BASINS)}") from exc


def fetch_basin(
    basin: Basin | str = MAUMEE,
    *,
    huc8s: list[str] | None = None,
    settings: Settings | None = None,
) -> list[HucResult]:
    """Fetch every HUC-8 of a basin (or a given subset), in order."""
    settings = settings or get_settings()
    codes = huc8s if huc8s is not None else list(resolve_basin(basin).huc8s)
    return [fetch_huc_facilities(h, settings=settings) for h in codes]


def fetch_maumee(
    *,
    huc8s: list[str] | None = None,
    settings: Settings | None = None,
) -> list[HucResult]:
    """Fetch every Maumee HUC-8 (or a given subset), in order. (Back-compat alias.)"""
    return fetch_basin(MAUMEE, huc8s=huc8s, settings=settings)


def deduplicate(results: list[HucResult]) -> list[Facility]:
    """One row per physical facility, keyed by FRS Registry ID.

    Facilities without an FRS ID can't be FRS-deduplicated, so each is kept
    distinct (keyed by its NPDES SourceID) rather than collapsed. The primary
    NPDES ID is the first seen; any others are merged into ``npdes_ids_all`` so a
    multi-permit facility surfaces its secondary permits without losing them.
    Two distinct FRS IDs that merely share a name are NOT collapsed.
    """
    by_key: dict[str, Facility] = {}
    for result in results:
        for fac in result.facilities:
            key = fac.frs_registry_id or f"NOFRS:{fac.npdes_id or id(fac)}"
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = fac.model_copy(deep=True)
                continue
            # Merge this permit's NPDES IDs into the kept facility's set.
            merged = _merge_npdes(existing, fac)
            existing.npdes_ids_all = merged
            # Prefer a POTW classification / a present design flow if the kept row lacks it.
            if existing.design_flow_mgd is None and fac.design_flow_mgd is not None:
                existing.design_flow_mgd = fac.design_flow_mgd
            if not existing.is_potw and fac.is_potw:
                existing.facility_type = fac.facility_type
    return list(by_key.values())


def _merge_npdes(a: Facility, b: Facility) -> str:
    seen: list[str] = []
    for fac in (a, b):
        for field in (fac.npdes_id, fac.npdes_ids_all):
            for token in (field or "").replace(",", " ").split():
                if token not in seen:
                    seen.append(token)
    return " ".join(seen)


# --- Inventory assembly (structured YAML + file writers) -------------------

# Provenance shared by every inventory file. Static (no timestamp) so re-running
# `watermark npdes` regenerates byte-identical output — no spurious git churn.
_INVENTORY_SOURCE = "EPA ECHO — cwa_rest_services (CWA v2017-10-13)"
# Generic caveats (every basin); basin-specific ones live on Basin.caveats.
_GENERIC_CAVEATS = [
    "ECHO's CWA facility service has no CWNS column; the POTW flag rests on CWPFacilityTypeIndicator.",
    "Facilities link to HUCs via WATERS (FacDerivedHuc); a permit that didn't geocode can be missed.",
    "design_flow_mgd is null where ECHO returned no value; it is never estimated.",
]


def _ownership(fac: Facility) -> str:
    if fac.is_federal:
        return "Federal"
    if fac.is_potw:
        return "POTW"
    return fac.facility_type or "Unknown"


def _secondary_npdes(fac: Facility) -> list[str]:
    """NPDES IDs at the facility other than the primary."""
    primary = fac.npdes_id or ""
    others = [t for t in (fac.npdes_ids_all or "").replace(",", " ").split() if t and t != primary]
    return list(dict.fromkeys(others))


def facility_record(
    fac: Facility,
    *,
    basin: Basin = MAUMEE,
    correction: echo_curation.AppliedCorrection | None = None,
) -> dict[str, Any]:
    """One facility as a YAML-ready mapping. ``None`` is a genuine ECHO null.

    The ``in_lima_subbasin`` / ``ottawa_discharge`` flags are a Maumee/Lima concept and
    are emitted only for a basin with an ``area_huc8s`` of interest (the Maumee); other
    basins omit them. Key order is preserved so the Maumee inventory regenerates identically.

    ``correction`` is this facility's entry from the curated receiving-water overlay, if it
    has one: it adds the ``receiving_water_*`` provenance keys beside the field (the curated
    value is already on ``fac`` — :func:`echo_curation.curate` applied it before dedup output
    so the derived ``ottawa_discharge`` flag follows from it).
    """
    rec: dict[str, Any] = {
        "frs_registry_id": fac.frs_registry_id,
        "name": fac.name,
        "npdes_id": fac.npdes_id,
        "npdes_ids_secondary": _secondary_npdes(fac),
        "ownership": _ownership(fac),
        "facility_type": fac.facility_type,
        "permit_type": fac.permit_type,
        "design_flow_mgd": fac.design_flow_mgd,
        "design_flow_missing": fac.design_flow_mgd is None,
        "receiving_water": fac.receiving_water,
        **(echo_curation.record_fields(correction) if correction else {}),
        "huc8": fac.huc8,
        "huc8_name": basin.huc8s.get(fac.huc8 or ""),
        "huc12": fac.huc12,
        "county": fac.county,
        "latitude": fac.latitude,
        "longitude": fac.longitude,
        "compliance_status": fac.compliance_status,
        "informal_enf_count": fac.informal_enf_count,
        "formal_enf_count": fac.formal_enf_count,
    }
    if basin.area_huc8s:
        in_area = fac.queried_huc8 in basin.area_huc8s
        rec["in_lima_subbasin"] = in_area
        rec["ottawa_discharge"] = in_area and "OTTAWA" in (fac.receiving_water or "").upper()
    rec["queried_huc8"] = fac.queried_huc8
    return rec


def _dump_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _facilities_doc(
    facilities: list[Facility],
    *,
    scope: str,
    basin: Basin = MAUMEE,
    curation: Curation | None = None,
) -> dict[str, Any]:
    """One emitted inventory file (``meta`` + ``facilities``).

    The curated corrections are scoped to the rows this file actually holds, so the
    POTW-only inventory never advertises a correction to a non-POTW row it doesn't contain.
    """
    ordered = sorted(facilities, key=lambda f: (f.huc8 or "", (f.name or "").upper()))
    curation = curation or Curation()
    by_frs = curation.by_frs()
    present = {f.frs_registry_id for f in ordered if f.frs_registry_id}

    meta: dict[str, Any] = {
        "subject": basin.subject,
        "scope": scope,
        "source": _INVENTORY_SOURCE,
        "watershed": basin.watershed,
        "huc8s": dict(basin.huc8s),
        "dedup_key": "FRS RegistryID",
        "count": len(ordered),
        "caveats": [*_GENERIC_CAVEATS, *basin.caveats, *echo_curation.caveats(curation, present)],
    }
    block = echo_curation.meta_block(curation, present)
    if block is not None:
        meta["receiving_water_curation"] = block

    return {
        "meta": meta,
        "facilities": [
            facility_record(f, basin=basin, correction=by_frs.get(f.frs_registry_id or ""))
            for f in ordered
        ],
    }


def curate_inventory(
    results: list[HucResult], *, basin: Basin = MAUMEE, settings: Settings | None = None
) -> tuple[list[Facility], Curation]:
    """Deduplicate a pull and merge the basin's curated receiving-water overlay into it.

    Split out of :func:`write_inventory` so a refresh can be reconciled (and refused, on a
    conflict or a stale entry) *before* anything is written — see
    :mod:`watermark.hydrology.connectors.echo_curation`.

    Curation scope comes from the HUC-8s this pull *queried* (``HucResult.huc8``), not from
    the rows they returned: a subbasin that came back empty must still count as looked-at, or
    a correction whose facility vanished would be written off as out-of-scope.
    """
    deduped = deduplicate(results)
    curation = echo_curation.curate(
        deduped,
        basin,
        queried_huc8s=frozenset(r.huc8 for r in results),
        settings=settings,
    )
    return deduped, curation


def write_inventory(
    results: list[HucResult],
    out_dir: Path,
    *,
    basin: Basin = MAUMEE,
    settings: Settings | None = None,
    curated: tuple[list[Facility], Curation] | None = None,
) -> dict[str, Path]:
    """Write the deduplicated inventory as YAML: all-NPDES, POTW, and HUC counts.

    Counts in the manifest are real (ECHO's reported ``QueryRows`` vs the rows we
    actually pulled), so totals are sanity-checkable. Output is deterministic (no
    timestamp), so re-running regenerates identical files.

    The basin's curated receiving-water overlay is merged in before writing (pass an
    already-reconciled ``curated`` pair to reuse one from :func:`curate_inventory` rather
    than reconciling twice). A correction that now *disagrees* with the pull (``conflict``)
    or whose facility has vanished from it (``stale``) raises
    :class:`~watermark.hydrology.connectors.echo_curation.CurationError` and **nothing is
    written** — a re-pull must never quietly drop reviewed data (#1698).
    """
    deduped, curation = curated or curate_inventory(results, basin=basin, settings=settings)
    out_dir.mkdir(parents=True, exist_ok=True)
    potws = [f for f in deduped if f.is_potw]

    all_path = out_dir / f"{basin.file_stem}.all-npdes.yaml"
    potw_path = out_dir / f"{basin.file_stem}.potw.yaml"
    counts_path = out_dir / f"{basin.file_stem}.huc-counts.yaml"

    _dump_yaml(
        all_path,
        _facilities_doc(
            deduped,
            scope="all active CWA-permitted dischargers",
            basin=basin,
            curation=curation,
        ),
    )
    _dump_yaml(
        potw_path,
        _facilities_doc(
            potws,
            scope="POTWs only (CWPFacilityTypeIndicator == POTW)",
            basin=basin,
            curation=curation,
        ),
    )
    _dump_yaml(
        counts_path,
        {
            "meta": {
                "subject": basin.subject.replace(" wastewater dischargers", " inventory")
                + " — per-HUC counts",
                "source": _INVENTORY_SOURCE,
                "watershed": basin.watershed,
            },
            "huc_counts": [
                {
                    "huc8": res.huc8,
                    "name": res.name,
                    "reported_count": res.reported_count,
                    "rows_pulled": len(res.facilities),
                    "potw_rows_pulled": sum(1 for f in res.facilities if f.is_potw),
                }
                for res in results
            ],
            "totals": {
                "raw": sum(len(r.facilities) for r in results),
                "deduped": len(deduped),
                "potw": len(potws),
            },
        },
    )

    return {"all": all_path, "potw": potw_path, "counts": counts_path}
