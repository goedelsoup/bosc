"""The federal registers a county-scoped model structurally cannot see (#1664, epic #1659 ME-E).

Everything else in the platform locates a facility through a *local* instrument: a county CAMA
parcel, a county-FIPS toxics inventory, a municipal utility's service territory. A **federal
enclave** is invisible to all three at once — it is off the tax rolls, so no county parcel layer
will ever carry its ~8,200 acres; and it reports its releases from whichever county it is
addressed in, which for a straddling installation is not the county the site profile picked as
its economic unit. The result before this module was a base represented only as county backdrop.

Three keyless, public-domain federal registers close that gap. Each is a pure sync
``fn(..., settings) -> pydantic`` over :func:`watermark.connectors._cache.cached_get`, so all
three ride the standard on-disk cache + TTL + offline/committed-fixture discipline and tests
never hit the network (fixtures under ``tests/fixtures/federal/<connector>/``):

* :func:`fetch_installation_boundary` — **DoD MIRTA** (Military Installations, Ranges and
  Training Areas), the authoritative DoD site-boundary layer published through Esri's US Federal
  Data organization. The enclave's ``FEATURENAME`` is the federal peer of a parcel id.
* :func:`fetch_water_systems` — **EPA SDWIS** via Envirofacts, keyed on the installation's own
  PWSIDs: a base runs its own community water systems, and this is where their source, their
  population served and their connection count are on the record.
* :func:`fetch_discharges` — **EPA ECHO** (CWA), keyed on the installation's own NPDES ids: the
  enclave's own outfalls and their reported average flow.

Nothing here is estimated. Every field is carried verbatim from the register that published it,
and a value the register leaves blank comes back ``None`` (``[open]``) rather than defaulted —
the acreage is the one derived number, and it is computed from the published geometry, not
transcribed.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

import httpx
from pydantic import BaseModel, ConfigDict
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform as shapely_transform

from watermark.connectors._cache import OfflineError, cached_get
from watermark.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from watermark.config import Settings

log = get_logger(__name__)

_SQM_PER_ACRE = 4046.8564224

# The MIRTA register's own vocabulary, carried through rather than remapped: the layer codes the
# operational status as a three-letter abbreviation. Expanded only for display; the raw code is
# what travels on the model.
MIRTA_STATUS = {"Act": "Active", "Inact": "Inactive", "Clos": "Closed"}


class FederalOfflineError(OfflineError):
    """Offline (``settings.federal_offline``) and no cache/fixture for a federal-register key."""


class InstallationBoundary(BaseModel):
    """One DoD MIRTA site polygon — a federal enclave's boundary and register identity.

    ``acres`` is the ONLY derived value: the published WGS84 geometry projected to the site's UTM
    zone and measured, so it is reproducible from the geometry that ships with it rather than
    transcribed from a report. It is expected to differ somewhat from an acreage quoted in an
    older instrument (WPAFB's 1991 CERCLA agreement says "approximately 8,200 acres"); the two are
    independent measurements a decade-plus apart, and the model carries both rather than picking.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    register_name: str = "DoD MIRTA (Military Installations, Ranges, and Training Areas)"
    feature_name: str  # FEATURENAME — the register key
    site_name: str  # SITENAME
    component: str  # SITEREPORTINGCOMPONENT, e.g. "USAF", "Army National Guard"
    operational_status: str  # SITEOPERATIONALSTATUS raw code ("Act")
    state: str  # STATENAMECODE
    is_joint_base: bool
    acres: float  # derived from the geometry (see above), not transcribed
    # How many disjoint parts the register draws the site in (WPAFB is a MultiPolygon: one large
    # Area A/C body plus slivers). Carried because a low part count against a record that names
    # several separate areas is the signal that the register's polygon is incomplete.
    parts: int = 1
    geometry: dict[str, Any]  # GeoJSON Polygon/MultiPolygon, WGS84
    source_url: str

    @property
    def status_label(self) -> str:
        """The operational status spelled out, falling back to the raw register code."""
        return MIRTA_STATUS.get(self.operational_status, self.operational_status)


class WaterSystem(BaseModel):
    """One EPA SDWIS public water system operated by the enclave (its own supply, not the city's)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pwsid: str
    name: str
    system_type: str | None = None  # CWS / NTNCWS / TNCWS
    source_type: str | None = None  # GW / SW / GU / ...
    population_served: int | None = None
    service_connections: int | None = None
    owner_type: str | None = None
    is_active: bool | None = None  # pws_activity_code == "A"


class Discharge(BaseModel):
    """One EPA ECHO NPDES-permitted discharge held by the enclave itself."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    npdes_id: str
    name: str
    registry_id: str | None = None  # EPA FRS RegistryID — the cross-register join
    permit_status: str | None = None
    permit_type: str | None = None
    county: str | None = None
    # The county the permit is ADDRESSED in. Load-bearing for a straddling enclave: when this
    # disagrees with the site profile's `rsei_fips`/`econ_fips`, the county-scoped instruments
    # miss the base by construction — which is the finding, not a data error.
    county_fips: str | None = None
    federal_agency: str | None = None  # non-null ⇒ ECHO flags this a federal facility
    design_flow_mgd: float | None = None  # permitted design flow (often blank in ECHO)
    actual_average_flow_mgd: float | None = None  # reported average — the enclave's own effluent
    latitude: float | None = None
    longitude: float | None = None


# ECHO result columns, selected *by ObjectName* against the verified `cwa_rest_services.metadata`
# and mapped to their ColumnID for `qcolumns` — never by index (the repo-wide ECHO rule). The
# response is keyed by ObjectName regardless, so the reads below are by name.
_ECHO_COLUMNS: dict[str, int] = {
    "CWPName": 1,
    "SourceID": 2,  # the NPDES / permit (source) ID
    "RegistryID": 9,  # FRS Registry ID — joins ECHO to TRI/FRS
    "FacStdCountyName": 14,
    "FacFIPSCode": 15,  # the county the permit reports from
    "FacFederalAgencyName": 18,  # non-null => federal facility
    "FacLat": 24,
    "FacLong": 25,
    "CWPTotalDesignFlowNmbr": 26,
    "CWPActualAverageFlowNmbr": 27,
    "CWPPermitStatusDesc": 51,
    "CWPPermitTypeDesc": 54,
}


# --- Shared plumbing --------------------------------------------------------------------


def _get(
    connector: str,
    params: dict[str, Any],
    url: str,
    *,
    settings: Settings,
    request_params: dict[str, Any] | None = None,
) -> Any:
    """One cached GET against a federal register (JSON in, JSON out)."""

    def _live() -> Any:
        resp = httpx.get(
            url,
            params=request_params if request_params is not None else params,
            timeout=settings.federal_request_timeout_s,
            follow_redirects=True,
        )
        resp.raise_for_status()
        return resp.json()

    return cached_get(
        connector,
        params,
        _live,
        cache_dir=settings.federal_cache_dir,
        offline=settings.federal_offline,
        fixtures_dir=settings.federal_fixtures_dir,
        ttl_hours=settings.federal_cache_ttl_hours,
        offline_error=FederalOfflineError,
    )


def _f(x: object) -> float | None:
    """A register cell as a float, or ``None`` when it is blank/unparseable ([open])."""
    if x is None or x == "":
        return None
    try:
        return float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _i(x: object) -> int | None:
    """A register cell as an int, or ``None`` when it is blank/unparseable ([open])."""
    v = _f(x)
    return None if v is None else int(v)


def _s(x: object) -> str | None:
    """A register cell as trimmed text, or ``None`` when blank."""
    if x is None:
        return None
    text = str(x).strip()
    return text or None


# --- DoD MIRTA — the enclave's land ------------------------------------------------------


def geodesic_acres(geometry: dict[str, Any], *, utm_epsg: int) -> float:
    """A WGS84 GeoJSON geometry's area in acres, measured in the site's UTM zone.

    Split out (and exported) so the same projection the hydrology stack uses for this site
    measures the enclave — a federal boundary must not be sized in a different frame from the
    watershed it sits in.
    """
    to_utm = Transformer.from_crs(4326, utm_epsg, always_xy=True).transform
    return round(float(shapely_transform(to_utm, shape(geometry)).area) / _SQM_PER_ACRE, 1)


def fetch_installation_boundary(
    feature_name: str, *, utm_epsg: int, settings: Settings | None = None
) -> InstallationBoundary | None:
    """The DoD MIRTA boundary for one installation, by its register ``FEATURENAME``.

    ``None`` when the register holds no such feature — the caller then leaves the enclave's land
    ``[open]`` rather than falling back to a bounding box or a county parcel that cannot exist.
    Multi-part installations (WPAFB is Areas A, B and C) come back as a single MultiPolygon, which
    is the register's own representation and is kept verbatim.
    """
    from watermark.config import get_settings

    settings = settings or get_settings()
    params = {"register": "mirta", "feature_name": feature_name}
    request = {
        "where": f"FEATURENAME='{feature_name}'",
        "outFields": (
            "FEATURENAME,SITENAME,SITEREPORTINGCOMPONENT,SITEOPERATIONALSTATUS,"
            "STATENAMECODE,ISJOINTBASE"
        ),
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "geojson",
    }
    url = f"{settings.mirta_url}/query"
    payload = _get("mirta", params, url, settings=settings, request_params=request)
    features = cast("list[dict[str, Any]]", (payload or {}).get("features") or [])
    if not features:
        log.warning("federal.mirta.miss", feature_name=feature_name)
        return None
    if len(features) > 1:
        # One register key must resolve to one site. More than one means the name is not the
        # identity we assumed, and silently taking the first would ship an arbitrary polygon.
        raise ValueError(
            f"MIRTA returned {len(features)} features for FEATURENAME={feature_name!r} — the "
            f"register key is ambiguous; narrow it before committing a boundary"
        )
    feat = features[0]
    props = feat.get("properties") or {}
    geometry = cast("dict[str, Any]", feat.get("geometry") or {})
    if not geometry:
        raise ValueError(f"MIRTA feature {feature_name!r} carries no geometry")
    return InstallationBoundary(
        feature_name=str(props.get("FEATURENAME") or feature_name),
        site_name=str(props.get("SITENAME") or props.get("FEATURENAME") or feature_name),
        component=str(props.get("SITEREPORTINGCOMPONENT") or ""),
        operational_status=str(props.get("SITEOPERATIONALSTATUS") or ""),
        state=str(props.get("STATENAMECODE") or ""),
        is_joint_base=str(props.get("ISJOINTBASE") or "").strip().lower() == "yes",
        acres=geodesic_acres(geometry, utm_epsg=utm_epsg),
        parts=(
            len(geometry.get("coordinates") or []) if geometry.get("type") == "MultiPolygon" else 1
        ),
        geometry=geometry,
        source_url=url,
    )


# --- EPA SDWIS — the enclave's own water systems -----------------------------------------


def fetch_water_systems(
    pwsids: Sequence[str], *, settings: Settings | None = None
) -> list[WaterSystem]:
    """The EPA SDWIS record for each of the enclave's own public water systems.

    One cached request per PWSID (they are independent register lookups, and keying the cache per
    system keeps a re-pull of one from invalidating the others). A PWSID the register does not
    know is skipped with a warning rather than fabricated.
    """
    from watermark.config import get_settings

    settings = settings or get_settings()
    out: list[WaterSystem] = []
    for pwsid in pwsids:
        url = f"{settings.sdwis_url}/water_system/pwsid/{pwsid}/JSON"
        rows = _get("sdwis", {"register": "sdwis", "pwsid": pwsid}, url, settings=settings)
        if isinstance(rows, dict):
            rows = [rows]
        if not rows:
            log.warning("federal.sdwis.miss", pwsid=pwsid)
            continue
        row = cast("dict[str, Any]", rows[0])
        activity = _s(row.get("pws_activity_code"))
        out.append(
            WaterSystem(
                pwsid=str(row.get("pwsid") or pwsid),
                name=str(row.get("pws_name") or pwsid),
                system_type=_s(row.get("pws_type_code")),
                source_type=_s(row.get("primary_source_code")),
                population_served=_i(row.get("population_served_count")),
                service_connections=_i(row.get("service_connections_count")),
                owner_type=_s(row.get("owner_type_code")),
                is_active=None if activity is None else activity.upper() == "A",
            )
        )
    return out


# --- EPA ECHO — the enclave's own discharges ---------------------------------------------


def fetch_discharges(
    npdes_ids: Sequence[str], *, settings: Settings | None = None
) -> list[Discharge]:
    """The EPA ECHO CWA record for each NPDES permit the enclave itself holds.

    Distinct from :mod:`watermark.hydrology.connectors.echo`, which pulls a whole basin's
    inventory by HUC: here the permits are already known (they are named on the profile), and what
    is wanted is the facility record behind each one — including the county it reports from, which
    is what reveals a straddling enclave falling outside its own site's county scope.
    """
    from watermark.config import get_settings

    settings = settings or get_settings()
    qcolumns = ",".join(str(cid) for cid in _ECHO_COLUMNS.values())
    out: list[Discharge] = []
    for npdes_id in npdes_ids:
        request = {
            "output": "JSON",
            "p_pid": npdes_id,
            "responseset": "1",
            "qcolumns": qcolumns,
        }
        payload = _get(
            "echo_cwa",
            {"register": "echo_cwa", "npdes_id": npdes_id},
            settings.echo_cwa_url,
            settings=settings,
            request_params=request,
        )
        facilities = ((payload or {}).get("Results") or {}).get("Facilities") or []
        if not facilities:
            log.warning("federal.echo.miss", npdes_id=npdes_id)
            continue
        fac = cast("dict[str, Any]", facilities[0])
        out.append(
            Discharge(
                npdes_id=str(fac.get("SourceID") or npdes_id),
                name=str(fac.get("CWPName") or npdes_id),
                registry_id=_s(fac.get("RegistryID")),
                permit_status=_s(fac.get("CWPPermitStatusDesc")),
                permit_type=_s(fac.get("CWPPermitTypeDesc")),
                county=_s(fac.get("FacStdCountyName")),
                county_fips=_s(fac.get("FacFIPSCode")),
                federal_agency=_s(fac.get("FacFederalAgencyName")),
                design_flow_mgd=_f(fac.get("CWPTotalDesignFlowNmbr")),
                actual_average_flow_mgd=_f(fac.get("CWPActualAverageFlowNmbr")),
                latitude=_f(fac.get("FacLat")),
                longitude=_f(fac.get("FacLong")),
            )
        )
    return out


def boundary_geojson(boundary: InstallationBoundary, *, slug: str) -> dict[str, Any]:
    """The committed ``federal-land.geojson`` payload for one enclave boundary.

    A one-feature FeatureCollection carrying the register's own attributes plus a
    ``bosc:provenance`` foreign member (the same non-Feature convention the parcel assemblages
    use, which :func:`watermark.site.gismap.campus_from_parcels` already tolerates). Deliberately
    NOT parcel-shaped: there is no owner, situs, transfer date or valuation, because a federal
    enclave has none — inventing those columns to fit the CAMA model is exactly the fabrication
    this seam exists to avoid.
    """
    return {
        "type": "FeatureCollection",
        "bosc:provenance": {
            "site": slug,
            "register": boundary.register_name,
            "source_url": boundary.source_url,
            "note": (
                "Federal enclave boundary from the DoD MIRTA site register — federally owned or "
                "otherwise managed land, planning-grade, NOT a legal survey or a cadastral "
                "parcel. A federal enclave is off the county tax rolls and appears in no county "
                "CAMA layer; acreage is measured from this published geometry."
            ),
        },
        "features": [
            {
                "type": "Feature",
                "geometry": boundary.geometry,
                "properties": {
                    "layer": "enclave",
                    "label": boundary.site_name,
                    "feature_name": boundary.feature_name,
                    "component": boundary.component,
                    "operational_status": boundary.status_label,
                    "state": boundary.state,
                    "is_joint_base": boundary.is_joint_base,
                    "acres": boundary.acres,
                },
            }
        ],
    }


def write_boundary(payload: dict[str, Any], path: object) -> None:
    """Write a boundary FeatureCollection deterministically (sorted keys, trailing newline)."""
    from pathlib import Path

    dest = Path(str(path))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
