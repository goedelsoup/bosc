"""EPA ECHO (Enforcement and Compliance History Online) NPDES connector.

Pulls the inventory of CWA-permitted facilities in a watershed from ECHO's Clean
Water Act REST services (``cwa_rest_services``) at ``echodata.epa.gov``. Used to
build a verified inventory of wastewater dischargers in the Maumee River basin.

The Maumee watershed is **seven** USGS HUC-8 subbasins (subregion 0410, Western
Lake Erie), enumerated in :data:`MAUMEE_HUC8S`. ECHO is queried one HUC-8 at a
time and the results are deduplicated to one row per physical facility by FRS
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
the module note in :mod:`bosc.cli` / the inventory output for that gap.
"""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Any, cast

import httpx
from pydantic import BaseModel, ConfigDict

from bosc.config import Settings, get_settings
from bosc.hydrology.connectors._cache import cached_get
from bosc.logging import get_logger

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
            name=_s(row.get("CWPName")),
            frs_registry_id=_s(row.get("RegistryID")),
            npdes_id=_s(row.get("SourceID")),
            npdes_ids_all=_s(row.get("NPDESIDs")),
            facility_type=_s(row.get("CWPFacilityTypeIndicator")),
            facility_type_code=_s(row.get("CWPFacilityTypeCode")),
            permit_type=_s(row.get("CWPPermitTypeDesc")),
            design_flow_mgd=_f(row.get("CWPTotalDesignFlowNmbr")),
            receiving_water=_s(row.get("CWPStateWaterBodyName")),
            huc8=_s(row.get("FacDerivedHuc")),
            huc12=_s(row.get("RadWBDHuc12")),
            latitude=_f(row.get("FacLat")),
            longitude=_f(row.get("FacLong")),
            county=_s(row.get("FacCountyName")),
            federal_agency=_s(row.get("FacFederalAgencyName")),
            compliance_status=_s(row.get("CWPSNCStatus")),
            informal_enf_count=_i(row.get("CWPInformalEnfActCount")),
            formal_enf_count=_i(row.get("CWPFormalEaCnt")),
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


def _i(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


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
    name = MAUMEE_HUC8S.get(huc8, huc8)
    qcolumns = ",".join(str(cid) for cid in _COLUMNS.values())

    summary = _get(settings, "get_facilities", {"p_huc": huc8, "p_act": "Y"})
    qid = _s(summary.get("QueryID"))
    reported = _i(summary.get("QueryRows"))
    stats = {k: str(summary[k]) for k in _STAT_KEYS if summary.get(k) is not None}
    log.info("echo.huc", huc8=huc8, name=name, qid=qid, reported=reported)

    facilities: list[Facility] = []
    if qid and (reported or 0) > 0:
        page = 1
        while True:
            res = _get(
                settings,
                "get_qid",
                {"qid": qid, "pageno": page, "responseset": page_size, "qcolumns": qcolumns},
            )
            rows = res.get("Facilities") or []
            facilities.extend(Facility.from_row(r, queried_huc8=huc8) for r in rows)
            if len(rows) < page_size or len(facilities) >= (reported or 0):
                break
            page += 1

    return HucResult(
        huc8=huc8,
        name=name,
        query_id=qid,
        reported_count=reported,
        stats=stats,
        facilities=facilities,
    )


def fetch_maumee(
    *,
    huc8s: list[str] | None = None,
    settings: Settings | None = None,
) -> list[HucResult]:
    """Fetch every Maumee HUC-8 (or a given subset), in order."""
    settings = settings or get_settings()
    codes = huc8s if huc8s is not None else list(MAUMEE_HUC8S)
    return [fetch_huc_facilities(h, settings=settings) for h in codes]


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


# --- Inventory assembly (CSV rows + file writers) --------------------------

_CSV_HEADER = [
    "frs_registry_id",
    "name",
    "npdes_id",
    "npdes_ids_secondary",
    "ownership",
    "facility_type",
    "permit_type",
    "design_flow_mgd",
    "design_flow_missing",
    "receiving_water",
    "huc8",
    "huc8_name",
    "huc12",
    "county",
    "latitude",
    "longitude",
    "compliance_status",
    "informal_enf_count",
    "formal_enf_count",
    "in_lima_subbasin",
    "ottawa_discharge",
    "queried_huc8",
]


def _ownership(fac: Facility) -> str:
    if fac.is_federal:
        return "Federal"
    if fac.is_potw:
        return "POTW"
    return fac.facility_type or "Unknown"


def _secondary_npdes(fac: Facility) -> str:
    """NPDES IDs at the facility other than the primary, space-joined."""
    primary = fac.npdes_id or ""
    others = [t for t in (fac.npdes_ids_all or "").replace(",", " ").split() if t and t != primary]
    return " ".join(dict.fromkeys(others))


def facility_row(fac: Facility) -> dict[str, Any]:
    """One CSV row (dict) for a facility. Blank cells are genuine ECHO nulls."""
    recv = (fac.receiving_water or "").upper()
    return {
        "frs_registry_id": fac.frs_registry_id or "",
        "name": fac.name or "",
        "npdes_id": fac.npdes_id or "",
        "npdes_ids_secondary": _secondary_npdes(fac),
        "ownership": _ownership(fac),
        "facility_type": fac.facility_type or "",
        "permit_type": fac.permit_type or "",
        "design_flow_mgd": "" if fac.design_flow_mgd is None else fac.design_flow_mgd,
        "design_flow_missing": "Y" if fac.design_flow_mgd is None else "",
        "receiving_water": fac.receiving_water or "",
        "huc8": fac.huc8 or "",
        "huc8_name": MAUMEE_HUC8S.get(fac.huc8 or "", ""),
        "huc12": fac.huc12 or "",
        "county": fac.county or "",
        "latitude": "" if fac.latitude is None else fac.latitude,
        "longitude": "" if fac.longitude is None else fac.longitude,
        "compliance_status": fac.compliance_status or "",
        "informal_enf_count": "" if fac.informal_enf_count is None else fac.informal_enf_count,
        "formal_enf_count": "" if fac.formal_enf_count is None else fac.formal_enf_count,
        "in_lima_subbasin": "Y" if fac.queried_huc8 in LIMA_AREA_HUC8S else "",
        "ottawa_discharge": (
            "Y" if (fac.queried_huc8 in LIMA_AREA_HUC8S and "OTTAWA" in recv) else ""
        ),
        "queried_huc8": fac.queried_huc8,
    }


def _write_csv(path: Path, facilities: list[Facility]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_HEADER)
        writer.writeheader()
        for fac in sorted(facilities, key=lambda f: (f.huc8 or "", (f.name or "").upper())):
            writer.writerow(facility_row(fac))


def write_inventory(results: list[HucResult], out_dir: Path) -> dict[str, Path]:
    """Write the deduplicated inventory: all-NPDES CSV, POTW CSV, HUC count manifest.

    Returns the paths written. Counts in the manifest are real (ECHO's reported
    ``QueryRows`` vs the rows we actually pulled), so totals are sanity-checkable.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    deduped = deduplicate(results)
    potws = [f for f in deduped if f.is_potw]

    all_path = out_dir / "maumee-wwtp.all-npdes.csv"
    potw_path = out_dir / "maumee-wwtp.potw.csv"
    counts_path = out_dir / "maumee-wwtp.huc-counts.csv"

    _write_csv(all_path, deduped)
    _write_csv(potw_path, potws)

    with counts_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["huc8", "name", "reported_count", "rows_pulled", "potw_rows_pulled"])
        for res in results:
            n_potw = sum(1 for f in res.facilities if f.is_potw)
            writer.writerow([res.huc8, res.name, res.reported_count, len(res.facilities), n_potw])
        writer.writerow([])
        writer.writerow(["TOTAL_RAW", "", "", sum(len(r.facilities) for r in results), ""])
        writer.writerow(["TOTAL_DEDUPED", "", "", len(deduped), len(potws)])

    return {"all": all_path, "potw": potw_path, "counts": counts_path}
