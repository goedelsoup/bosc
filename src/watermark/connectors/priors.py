"""Discovery priors — the two open registers that say where data centers already are (#1390,
epic #1387).

The domestic funnel starts from an instrument: a permit, a deed, a resolution. Abroad there is
usually no such instrument to start from, so stage 1 of the international funnel starts from
**open registers of the thing itself**, and everything downstream is bounded by what they can and
cannot support.

Two are wired here, chosen because they are free, keyless, globally scoped, and *independent of
each other* — which is the only reason agreement between them means anything:

* :func:`fetch_peeringdb_facilities` — **PeeringDB**, the interconnection community's facility
  register. Rows are maintained largely by the operators themselves against a database that
  networks actually route by, and each carries the interconnection counts that make "capability
  first" measurable rather than rhetorical. Its blind spot is structural: a facility with no
  carrier presence — a single-tenant hyperscale campus, which is exactly the class this epic
  cares most about — has no reason to appear at all.
* :func:`fetch_osm_data_centers` — **OpenStreetMap** ``telecom=data_center`` /
  ``building=data_center`` via Overpass. Crowd-sourced, so its coverage is uneven and its
  attribution is a mapper's reading of a sign; but it sees buildings, including ones no network
  interconnects at, and it carries real footprint geometry for ways.

Neither is a record *about* a facility in the evidentiary sense — both are published third-party
registers, so everything sourced here is ``[reference]``, and the register that consumes these
rows (:mod:`watermark.international.register`) is what turns agreement between them into a
corroborated candidate. Nothing in this module infers anything: a field the register leaves blank
comes back ``None``.

Both are pure sync ``fn(..., settings) -> pydantic`` over
:func:`watermark.connectors._cache.cached_get`, so both ride the on-disk cache + TTL +
offline/committed-fixture discipline and tests never hit the network (fixtures under
``tests/fixtures/priors/<connector>/``).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, cast

import httpx
from pydantic import BaseModel, ConfigDict

from watermark.connectors._cache import OfflineError, cached_get
from watermark.logging import get_logger

if TYPE_CHECKING:
    from watermark.config import Settings

log = get_logger(__name__)

# The licence each register publishes under, carried onto every row so the terms travel with the
# data rather than living only in a dataset README (the #1390 licence audit). Both permit
# redistribution of derived facts with attribution; OSM additionally imposes share-alike on a
# derived *database*, which is why the register republishes rows rather than silently folding
# them into an unattributed layer.
PEERINGDB_LICENSE = "PeeringDB data, CC BY 4.0 — attribution required"
OSM_LICENSE = "© OpenStreetMap contributors, ODbL 1.0 — attribution + share-alike"

# Overpass answers `406 Not Acceptable` to httpx's default `python-httpx/x.y` User-Agent, and
# identifying the client is OSM's stated API etiquette besides — a shared free endpoint needs to
# know who to throttle. Same string as the research fetcher's, tagged for this subsystem.
USER_AGENT = "watermark-bosc/1.0 (priors; +https://github.com/watermark-directory)"

# The OSM tags that mean "this is a data center". `telecom=data_center` is the documented
# primary; `building=data_center` is the widely-used building-level peer. Deliberately NOT
# included: `office=it`, `man_made=telephone_exchange`, and similar near-misses — they would
# raise recall by admitting things that are not data centers, and this stage feeds a
# corroboration test where a false row on one side can only manufacture agreement.
OSM_TAGS: tuple[tuple[str, str], ...] = (("telecom", "data_center"), ("building", "data_center"))


class PriorsOfflineError(OfflineError):
    """Offline (``settings.priors_offline``) and no cache/fixture for a priors key."""


class PeeringDbFacility(BaseModel):
    """One PeeringDB carrier-neutral facility row, carried verbatim.

    ``net_count`` / ``ix_count`` are the register's own interconnection counts — how many networks
    and exchanges are present. They are the capability signal this epic's driver is named for, and
    they are also the honest measure of what PeeringDB *is*: a facility with a high net_count is
    an interconnection hub, which is a different claim from "a large data center".
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    facility_id: int  # PeeringDB `id` — the register key
    name: str
    organization: str | None = None  # `org_name` — the operator as PeeringDB states it
    website: str | None = None
    latitude: float
    longitude: float
    address: str | None = None
    city: str | None = None
    country: str | None = None  # ISO 3166-1 alpha-2
    net_count: int | None = None
    ix_count: int | None = None
    updated: str | None = None  # the register row's own last-modified stamp

    @property
    def url(self) -> str:
        """The citable permalink for this row."""
        return f"https://www.peeringdb.com/fac/{self.facility_id}"


class OsmDataCenter(BaseModel):
    """One OSM feature tagged as a data center, carried verbatim.

    ``element`` is the OSM type/id pair (``way/123456``) — the register key and the permalink
    stem. For a way or relation the position is Overpass's computed ``center``, which is a
    representative interior point, not a centroid of record; it is precise enough to test whether
    two registers mean the same building and is never used as a boundary.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    element: str  # "node/123" | "way/123" | "relation/123"
    latitude: float
    longitude: float
    name: str | None = None
    operator: str | None = None  # the `operator=` tag, verbatim
    website: str | None = None
    address: str | None = None  # assembled from the `addr:*` tags present
    country: str | None = None  # `addr:country` where the mapper set it
    is_area: bool = False  # a way/relation (has a footprint) vs a bare node

    @property
    def url(self) -> str:
        """The citable permalink for this feature."""
        return f"https://www.openstreetmap.org/{self.element}"


def _s(x: object) -> str | None:
    """A register cell as trimmed text, or ``None`` when blank."""
    if x is None:
        return None
    text = str(x).strip()
    return text or None


def _f(x: object) -> float | None:
    """A register cell as a float, or ``None`` when blank/unparseable."""
    if x is None or x == "":
        return None
    try:
        return float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _i(x: object) -> int | None:
    """A register cell as an int, or ``None`` when blank/unparseable."""
    v = _f(x)
    return None if v is None else int(v)


# --- PeeringDB --------------------------------------------------------------------------


def fetch_peeringdb_facilities(
    country: str, *, settings: Settings | None = None
) -> list[PeeringDbFacility]:
    """Every PeeringDB facility registered in one country, ascending by facility id.

    The country slice is the natural cache unit — it is what the API keys on, it is stable, and it
    lets several AOIs in one country share a single pull. Callers narrow to an AOI themselves
    (``Aoi.contains``) rather than pushing a bbox the API does not support.

    A row PeeringDB carries without coordinates is **dropped**, not defaulted: an uncoordinated
    facility cannot be corroborated against a map feature, and placing it at (0, 0) would put it
    in the Gulf of Guinea.
    """
    from watermark.config import get_settings

    settings = settings or get_settings()
    params = {"register": "peeringdb", "endpoint": "fac", "country": country}
    request: dict[str, str | int] = {"country": country, "limit": 1000}

    def _live() -> Any:
        resp = httpx.get(
            f"{settings.peeringdb_url}/fac",
            params=request,
            headers={"User-Agent": USER_AGENT},
            timeout=settings.priors_request_timeout_s,
            follow_redirects=True,
        )
        resp.raise_for_status()
        return resp.json()

    payload = cached_get(
        "peeringdb",
        params,
        _live,
        cache_dir=settings.priors_cache_dir,
        offline=settings.priors_offline,
        fixtures_dir=settings.priors_fixtures_dir,
        ttl_hours=settings.priors_cache_ttl_hours,
        offline_error=PriorsOfflineError,
    )
    rows = cast("list[dict[str, Any]]", (payload or {}).get("data") or [])

    out: list[PeeringDbFacility] = []
    skipped = 0
    for row in rows:
        lat, lon = _f(row.get("latitude")), _f(row.get("longitude"))
        if lat is None or lon is None:
            skipped += 1
            continue
        address = " ".join(
            part for part in (_s(row.get("address1")), _s(row.get("address2"))) if part
        )
        out.append(
            PeeringDbFacility(
                facility_id=int(row["id"]),
                name=str(row.get("name") or f"facility {row['id']}"),
                organization=_s(row.get("org_name")),
                website=_s(row.get("website")),
                latitude=lat,
                longitude=lon,
                address=address or None,
                city=_s(row.get("city")),
                country=_s(row.get("country")),
                net_count=_i(row.get("net_count")),
                ix_count=_i(row.get("ix_count")),
                updated=_s(row.get("updated")),
            )
        )
    if skipped:
        log.info("priors.peeringdb.uncoordinated", country=country, skipped=skipped)
    return sorted(out, key=lambda f: f.facility_id)


# --- OpenStreetMap / Overpass ------------------------------------------------------------

# The `addr:*` keys assembled into a display address, in the order they read.
_ADDR_KEYS = ("addr:housenumber", "addr:street", "addr:city", "addr:postcode")


# Overpass runs a small fixed number of query slots per client IP and answers `429` when they
# are all busy, `504` when the instance is overloaded. Both are transient and both are the normal
# response to sweeping several AOIs in a row, so they are retried rather than surfaced — an
# unretried 429 makes a multi-AOI sweep fail on whichever AOI happened to be third. The cache
# above means this cost is paid once per AOI, not once per run.
_OVERPASS_RETRY_STATUS = frozenset({429, 502, 503, 504})
_OVERPASS_ATTEMPTS = 5
_OVERPASS_BACKOFF_S = 20.0

# The SERVER's own per-query budget, sent inside the Overpass QL. A fixed constant rather than a
# fraction of the client timeout so it stays out of the cache key (see `fetch_osm_data_centers`);
# `priors_request_timeout_s` must exceed it, or the client hangs up on a query the server is
# still successfully running and the result is thrown away.
OVERPASS_QUERY_TIMEOUT_S = 160


def _post_overpass(url: str, query: str, *, timeout_s: float) -> Any:
    """POST one Overpass query, backing off through the endpoint's slot limit."""
    last: httpx.HTTPStatusError | None = None
    for attempt in range(_OVERPASS_ATTEMPTS):
        resp = httpx.post(
            url,
            data={"data": query},
            headers={"User-Agent": USER_AGENT},
            timeout=timeout_s,
            follow_redirects=True,
        )
        if resp.status_code not in _OVERPASS_RETRY_STATUS:
            resp.raise_for_status()
            return resp.json()
        last = httpx.HTTPStatusError(
            f"overpass {resp.status_code}", request=resp.request, response=resp
        )
        if attempt < _OVERPASS_ATTEMPTS - 1:
            delay = _OVERPASS_BACKOFF_S * (attempt + 1)
            log.info("priors.osm.backoff", status=resp.status_code, attempt=attempt, delay_s=delay)
            time.sleep(delay)
    raise RuntimeError(
        f"Overpass refused {_OVERPASS_ATTEMPTS} attempts (last: {last}). The public endpoint is "
        "rate-limited; retry later, or point `overpass_url` at another mirror."
    ) from last


def _overpass_query(bbox: str, *, timeout_s: int) -> str:
    """The Overpass QL for every data-center-tagged feature in a bbox.

    ``out center`` asks Overpass to reduce each way/relation to a representative point, so nodes
    and areas come back in one uniform shape. The in-query ``[timeout:]`` is the *server's* budget
    and must sit under the client's, or the client gives up while the server is still working and
    the (successful, expensive) result is thrown away.
    """
    clauses = "".join(f'nwr["{k}"="{v}"]({bbox});' for k, v in OSM_TAGS)
    return f"[out:json][timeout:{timeout_s}];({clauses});out center;"


def fetch_osm_data_centers(bbox: str, *, settings: Settings | None = None) -> list[OsmDataCenter]:
    """Every OSM feature tagged as a data center in a bbox, ascending by element id.

    ``bbox`` is Overpass's own ``"south,west,north,east"`` string (``Aoi.overpass_bbox``) — passed
    through rather than re-derived, so the cache key is the exact query that was run.
    """
    from watermark.config import get_settings

    settings = settings or get_settings()
    query = _overpass_query(bbox, timeout_s=OVERPASS_QUERY_TIMEOUT_S)
    # Key on what determines the RESULT — the window and the tag set — not on the rendered query.
    # Folding the query text in would make every cache entry and every committed fixture depend on
    # the server-timeout literal and on Overpass QL formatting, so a cosmetic edit to
    # `_overpass_query` would silently invalidate the lot.
    params = {"register": "osm", "bbox": bbox, "tags": [f"{k}={v}" for k, v in OSM_TAGS]}

    def _live() -> Any:
        return _post_overpass(
            settings.overpass_url, query, timeout_s=settings.priors_request_timeout_s
        )

    payload = cached_get(
        "osm",
        params,
        _live,
        cache_dir=settings.priors_cache_dir,
        offline=settings.priors_offline,
        fixtures_dir=settings.priors_fixtures_dir,
        ttl_hours=settings.priors_cache_ttl_hours,
        offline_error=PriorsOfflineError,
    )
    elements = cast("list[dict[str, Any]]", (payload or {}).get("elements") or [])

    out: list[OsmDataCenter] = []
    for el in elements:
        # A node carries its own lat/lon; a way/relation carries Overpass's computed `center`.
        center = cast("dict[str, Any]", el.get("center") or {})
        lat = _f(el.get("lat")) if el.get("lat") is not None else _f(center.get("lat"))
        lon = _f(el.get("lon")) if el.get("lon") is not None else _f(center.get("lon"))
        if lat is None or lon is None:
            continue
        tags = cast("dict[str, Any]", el.get("tags") or {})
        el_type = str(el.get("type") or "node")
        address = " ".join(part for k in _ADDR_KEYS if (part := _s(tags.get(k))))
        out.append(
            OsmDataCenter(
                element=f"{el_type}/{el['id']}",
                latitude=lat,
                longitude=lon,
                name=_s(tags.get("name")) or _s(tags.get("short_name")),
                operator=_s(tags.get("operator")),
                website=_s(tags.get("website")) or _s(tags.get("contact:website")),
                address=address or None,
                country=_s(tags.get("addr:country")),
                is_area=el_type in ("way", "relation"),
            )
        )
    return sorted(out, key=lambda f: f.element)
