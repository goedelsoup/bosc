"""Ohio DNR water-well-log census connector (Division of Water Resources).

Under **R.C. 1521.05** every water-well contractor files a completion / sealing log with
the Ohio DNR; the Division of Water Resources publishes the (nightly-refreshed) well-log
database as a public **ArcGIS MapServer** — layer 0, one point per well. This is the
*groundwater* peer of the surface-water supply model (:mod:`watermark.hydrology.supply`):
the population of private and public wells whose **static water levels** and **reported
yields** are the empirical basis for an ``[inference]`` aquifer-parameter estimate and the
well-**drawdown** ("cone of depression") thread the data-center cooling withdrawal
implicates — the "area well concerns" that surface in the PAAC record (2026-03-30).

**Distinct from :mod:`ohio_water_withdrawal`** (the WWFRP >100,000-gpd withdrawal
*registration* registry): that is who is licensed to withdraw a lot; this is the well
*census* — where the wells are, how deep, into what aquifer, at what static level, at what
reported test yield.

Provenance discipline: a reported driller figure is ``[verified]`` for *what the log
states* (the transcription may still be wrong — driller logs are self-reported); anything
derived from it (specific capacity, a transmissivity estimate, a drawdown cone) is
``[inference]`` and lives in :mod:`watermark.hydrology.aquifer`, never here. Owner / name /
street / house-number fields are **deliberately not ingested** — the model needs locations
and hydraulics, not a names-and-addresses list of private residents. Like every hydrology
connector this reuses :func:`_cache.cached_get` (on-disk cache + TTL + offline/committed-
fixture fallback), so tests and CI never touch the network. Synchronous (``httpx``).

**Ohio only.** This is Ohio's well-log service; a non-Ohio watershed point uses its own
state service and the CLI refuses cleanly rather than query the wrong state.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import httpx
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.connectors import to_float, to_int, to_str
from watermark.hydrology.connectors._cache import cached_get
from watermark.logging import get_logger

log = get_logger(__name__)

# The single well-point layer (intrinsic to the service, not per-site config).
OHIO_WATERWELLS_LAYER = 0  # DSW_Services/waterwells/MapServer/0 — one point per well log

# ArcGIS server page size. The hosted service caps a page at 1000 (maxRecordCount); the
# query loop pages to completion on ``exceededTransferLimit`` rather than truncate silently.
_PAGE_SIZE = 1000

# Layer-0 fields we read **by name** (never by index — column order is not stable). The
# owner / last-name / street / house-number columns are intentionally omitted (private-
# resident PII the model does not need). ``COMPLETION_DATE`` is an epoch-ms Date column
# (rendered ISO); ``STR_COMP_DATE`` is its redundant string form and is dropped.
_WELL_FIELDS = (
    "OBJECTID",
    "TYPE",
    "WELL_USE",
    "LONG83",
    "LAT83",
    "SOURCE_OF_COORD",
    "COUNTY",
    "TOWNSHIP",
    "COMPLETION_DATE",
    "TOTAL_DEPTH",
    "DEM_ELEV",
    "AQUIFER_TYPE",
    "DRILL_TYPE",
    "TEST_RATE_GPM",
    "STATIC_WATER_LEVEL_FT",
    "CASE_LENGTH",
    "BEDROCK_DEPTH",
    "WELL_NO",
)

# The committed-CSV column order (stable; drives the reference dataset header + row order).
_CSV_COLUMNS = (
    "object_id",
    "record_type",
    "well_use",
    "longitude",
    "latitude",
    "coord_source",
    "county",
    "township",
    "completion_date",
    "total_depth_ft",
    "dem_elev_ft",
    "aquifer_type",
    "drill_type",
    "test_rate_gpm",
    "static_water_level_ft",
    "case_length_ft",
    "bedrock_depth_ft",
    "well_no",
)


class WaterWellsError(RuntimeError):
    """An ArcGIS-level error from the ODNR water-wells MapServer (query rejected, etc.)."""


class WaterWell(BaseModel):
    """One well-log record, verbatim from the ODNR layer-0 feature (nothing inferred).

    Every quantity is the **driller-reported** value as the DNR stores it: a missing field
    is a genuine ``None`` (never a fabricated 0). Coordinates are NAD83 decimal degrees
    (``LONG83`` / ``LAT83``); ``coord_source`` records how the point was located (a
    geocoded address is coarser than a surveyed GPS fix) and gates spatial confidence
    downstream. There is **no** pumping-water-level / drawdown-during-test column in this
    service, so a true specific capacity is not derivable from a single record — see
    :mod:`watermark.hydrology.aquifer`.
    """

    model_config = ConfigDict(extra="forbid")

    object_id: int
    record_type: str | None  # TYPE — well vs sealing / other log type
    well_use: str | None  # DOMESTIC, PUBLIC/SEMI-PUB, MONITOR, HTG/COOLING, …
    longitude: float | None  # LONG83 (NAD83)
    latitude: float | None  # LAT83 (NAD83)
    coord_source: str | None  # SOURCE_OF_COORD — locational quality
    county: str | None
    township: str | None
    completion_date: str | None  # ISO YYYY-MM-DD
    total_depth_ft: float | None
    dem_elev_ft: float | None  # DEM-sampled ground elevation
    aquifer_type: str | None  # LIMESTONE, GRAVEL, SAND & GRAVEL, SHALE, …
    drill_type: str | None
    test_rate_gpm: float | None  # reported yield-test rate
    static_water_level_ft: float | None  # rest level below surface
    case_length_ft: float | None
    bedrock_depth_ft: int | None
    well_no: int | None


class WaterWellInventory(BaseModel):
    """One county's well-log census + the pull's provenance."""

    model_config = ConfigDict(extra="forbid")

    county: str
    state: str = "OH"
    source_url: str
    wells: list[WaterWell]

    def _counts(self, key: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for w in self.wells:
            label = (getattr(w, key) or "?").strip() or "?"
            counts[label] = counts.get(label, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))

    def use_counts(self) -> dict[str, int]:
        """Well count by ``well_use``, most common first."""
        return self._counts("well_use")

    def aquifer_counts(self) -> dict[str, int]:
        """Well count by ``aquifer_type``, most common first."""
        return self._counts("aquifer_type")


# --- ArcGIS query -----------------------------------------------------------------------


def _iso_date(value: Any) -> str | None:
    """ArcGIS epoch-milliseconds -> ISO ``YYYY-MM-DD`` (UTC); passthrough for a plain string."""
    if value is None:
        return None
    if isinstance(value, str):
        return to_str(value)
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=UTC).date().isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _sql_quote(value: str) -> str:
    """A SQL string literal for an ArcGIS ``where`` clause (single-quotes doubled)."""
    return "'" + value.replace("'", "''") + "'"


def _query_all(where: str, out_fields: str, *, settings: Settings) -> list[dict[str, Any]]:
    """Every ``attributes`` dict matching ``where`` on layer 0, paged to completion.

    Each page is a distinct cache key (``resultOffset`` is in the params), so an offline
    replay needs one committed fixture per page. ``layer`` is carried in the cache-key
    params for symmetry with the sibling WWFRP connector (the layer lives in the URL path,
    not the query string) and to stay collision-safe if a second layer is ever queried.
    """
    base = settings.ohio_waterwells_base_url
    layer = OHIO_WATERWELLS_LAYER
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        params: dict[str, Any] = {
            "layer": layer,
            "where": where,
            "outFields": out_fields,
            "resultOffset": offset,
            "resultRecordCount": _PAGE_SIZE,
        }

        def fetch(_offset: int = offset) -> Any:
            log.info("ohio_waterwells.fetch", where=where, offset=_offset)
            resp = httpx.get(
                f"{base}/{layer}/query",
                params={
                    "f": "json",
                    "where": where,
                    "outFields": out_fields,
                    "returnGeometry": "false",
                    "orderByFields": "OBJECTID",
                    "resultOffset": _offset,
                    "resultRecordCount": _PAGE_SIZE,
                },
                timeout=settings.hydro_request_timeout_s,
            )
            resp.raise_for_status()
            return resp.json()

        payload = cast(
            "dict[str, Any]",
            cached_get("ohio_waterwells", params, fetch, settings=settings),
        )
        if "error" in payload:
            raise WaterWellsError(f"ArcGIS error on layer {layer}: {payload['error']}")
        features = payload.get("features") or []
        rows.extend(f.get("attributes", {}) for f in features)
        if not features or not payload.get("exceededTransferLimit"):
            return rows
        offset += len(features)


def _well_from_attrs(attrs: dict[str, Any]) -> WaterWell | None:
    """Build a :class:`WaterWell` from a layer-0 feature; ``None`` without an ``OBJECTID``."""
    oid = to_int(attrs.get("OBJECTID"))
    if oid is None:
        return None
    return WaterWell(
        object_id=oid,
        record_type=to_str(attrs.get("TYPE")),
        well_use=to_str(attrs.get("WELL_USE")),
        longitude=to_float(attrs.get("LONG83")),
        latitude=to_float(attrs.get("LAT83")),
        coord_source=to_str(attrs.get("SOURCE_OF_COORD")),
        county=to_str(attrs.get("COUNTY")),
        township=to_str(attrs.get("TOWNSHIP")),
        completion_date=_iso_date(attrs.get("COMPLETION_DATE")),
        total_depth_ft=to_float(attrs.get("TOTAL_DEPTH")),
        dem_elev_ft=to_float(attrs.get("DEM_ELEV")),
        aquifer_type=to_str(attrs.get("AQUIFER_TYPE")),
        drill_type=to_str(attrs.get("DRILL_TYPE")),
        test_rate_gpm=to_float(attrs.get("TEST_RATE_GPM")),
        static_water_level_ft=to_float(attrs.get("STATIC_WATER_LEVEL_FT")),
        case_length_ft=to_float(attrs.get("CASE_LENGTH")),
        bedrock_depth_ft=to_int(attrs.get("BEDROCK_DEPTH")),
        well_no=to_int(attrs.get("WELL_NO")),
    )


def fetch_county(county: str, *, settings: Settings | None = None) -> WaterWellInventory:
    """Every ODNR-logged water well in an Ohio county, OBJECTID-sorted.

    ``county`` is the bare county name (e.g. ``"Allen"``); the service stores it uppercase,
    so the ``where`` clause upper-cases it. Wells come back sorted by ``object_id`` so the
    census — and the committed CSV it writes — is deterministic.
    """
    settings = settings or get_settings()
    rows = _query_all(
        f"COUNTY = {_sql_quote(county.upper())}",
        ",".join(_WELL_FIELDS),
        settings=settings,
    )
    wells = [w for w in (_well_from_attrs(a) for a in rows) if w is not None]
    wells.sort(key=lambda w: w.object_id)
    return WaterWellInventory(
        county=county,
        source_url=f"{settings.ohio_waterwells_base_url}/{OHIO_WATERWELLS_LAYER}",
        wells=wells,
    )


# --- reference dataset assembly ---------------------------------------------------------


def county_slug(county: str) -> str:
    """A filesystem slug for a county name (``"Allen County, OH"`` -> ``"allen"``)."""
    bare = county.split(" County")[0].strip() or county.strip()
    return "-".join(bare.lower().split())


def _well_row(well: WaterWell) -> dict[str, Any]:
    return {col: getattr(well, col) for col in _CSV_COLUMNS}


def inventory_csv(inventory: WaterWellInventory) -> str:
    """The census as deterministic CSV text (stable header + OBJECTID-sorted rows).

    A flat well census is naturally tabular, so it lands as CSV (compact, diffable) with
    provenance in the sibling ``README.md`` — the EPA-ECHO reference-dataset convention,
    not the nested-YAML shape the WWFRP registry needs. A missing value is an empty cell
    (never a fabricated 0). No generation timestamp, so an unchanged pull is byte-stable.
    """
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=list(_CSV_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for well in sorted(inventory.wells, key=lambda w: w.object_id):
        row = _well_row(well)
        writer.writerow({k: ("" if v is None else v) for k, v in row.items()})
    return buf.getvalue()


def write_inventory(inventory: WaterWellInventory, out_dir: Path) -> Path:
    """Write one county's well census to ``<slug>.csv``; returns the path.

    Deterministic: every value is verbatim from the service and rows are OBJECTID-sorted,
    so re-running an unchanged pull regenerates identical bytes.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{county_slug(inventory.county)}.csv"
    path.write_text(inventory_csv(inventory), encoding="utf-8")
    return path


def _well_from_csv_row(row: dict[str, str]) -> WaterWell:
    """Reverse of :func:`_well_row` — an empty cell parses back to ``None``."""

    def s(col: str) -> str | None:
        return to_str(row.get(col))

    def f(col: str) -> float | None:
        return to_float(row.get(col) or None)

    def i(col: str) -> int | None:
        return to_int(row.get(col) or None)

    return WaterWell(
        object_id=int(row["object_id"]),
        record_type=s("record_type"),
        well_use=s("well_use"),
        longitude=f("longitude"),
        latitude=f("latitude"),
        coord_source=s("coord_source"),
        county=s("county"),
        township=s("township"),
        completion_date=s("completion_date"),
        total_depth_ft=f("total_depth_ft"),
        dem_elev_ft=f("dem_elev_ft"),
        aquifer_type=s("aquifer_type"),
        drill_type=s("drill_type"),
        test_rate_gpm=f("test_rate_gpm"),
        static_water_level_ft=f("static_water_level_ft"),
        case_length_ft=f("case_length_ft"),
        bedrock_depth_ft=i("bedrock_depth_ft"),
        well_no=i("well_no"),
    )


def read_inventory(path: Path, *, settings: Settings | None = None) -> WaterWellInventory:
    """Load a committed county census CSV back into a :class:`WaterWellInventory`.

    The county display name is recovered from the data's own ``county`` column (title-cased);
    ``source_url`` is reconstructed from settings. Round-trips :func:`write_inventory`.
    """
    settings = settings or get_settings()
    wells = [
        _well_from_csv_row(row)
        for row in csv.DictReader(io.StringIO(path.read_text(encoding="utf-8")))
    ]
    wells.sort(key=lambda w: w.object_id)
    counties = {w.county for w in wells if w.county}
    county = next(iter(counties)).title() if len(counties) == 1 else county_slug(path.stem).title()
    return WaterWellInventory(
        county=county,
        source_url=f"{settings.ohio_waterwells_base_url}/{OHIO_WATERWELLS_LAYER}",
        wells=wells,
    )
