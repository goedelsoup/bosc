"""County parcel/CAMA connector — jurisdiction-agnostic, schema-driven (#237).

Pulls real-estate / parcel attributes from a county's public **ArcGIS REST** server. The
**field names + value encodings** are not hardcoded: they come from the active site's
:class:`~watermark.connectors.gis_schema.GisParcelSchema` (``SiteProfile.gis_parcel``), so a new
jurisdiction is config, not a copied connector. Lima = Allen County's "Current Parcels" layer
(``AGOL/AGOL_NonEditLayers/MapServer/1`` — the auditor's CAMA data joined to parcel geometry:
owner, situs address, land use, acreage, market/CAUV values, last sale, tax district), whose
schema (:data:`watermark.sites.LIMA_PARCEL_SCHEMA`) reproduces the pre-#237 behavior exactly.

The server is anonymous (no token), paginates at the layer's ``maxRecordCount``, and serves
``f=json``. Two ways in:

* :func:`fetch_parcel` — one parcel by its number (deed ids are normalized to the server's
  stored id per the schema's ``id_normalize`` rule);
* :func:`query_parcels` — any ``where`` clause, transparently paged to completion.

Values are passed through **verbatim** from the service; only the obvious encodings are
decoded (the sale-date field per ``schema.date_decode``). ``None`` means the service returned
no value — never a fabricated default. Reuses the shared connector cache/offline/fixture
machinery; synchronous (``httpx``).
"""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any, cast

import httpx
import yaml
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.connectors.gis_schema import GisDefenseConfig, GisParcelSchema
from watermark.hydrology.connectors._cache import cached_get
from watermark.logging import get_logger
from watermark.sites import LIMA_PARCEL_SCHEMA, active_profile

log = get_logger(__name__)


class AllenGisError(RuntimeError):
    """The ArcGIS service returned an error object, or the active site has no parcel schema."""


def _parcel_schema(settings: Settings) -> GisParcelSchema:
    """The active site's parcel GIS schema, or a clean error if it has none."""
    schema = active_profile(settings).gis_parcel
    if schema is None:
        raise AllenGisError(
            f"site {settings.site!r} has no parcel GIS schema (gis_parcel) — cannot query parcels"
        )
    return schema


class Parcel(BaseModel):
    """One parcel's CAMA attributes, as returned by the county GIS."""

    model_config = ConfigDict(extra="forbid")

    parcel_no: str | None
    owner: str | None  # owner_field
    owner_2: str | None  # owner_2_field
    deeded_owner: str | None  # deeded_owner_field
    situs_address: str | None  # assembled from situs_fields
    owner_address: str | None  # assembled from owner_addr_fields
    land_use_code: int | None
    acres: float | None
    market_land_value: int | None
    market_improvement_value: int | None
    market_total_value: int | None
    cauv_value: int | None
    tax_district: str | None
    school_code: str | None
    neighborhood_code: str | None
    last_sale_date: str | None  # ISO yyyy-mm-dd, decoded per schema.date_decode
    last_sale_amount: int | None
    valid_sale: str | None

    @classmethod
    def from_attrs(cls, a: dict[str, Any], schema: GisParcelSchema | None = None) -> Parcel:
        """Decode one ArcGIS feature's attributes by field name (per ``schema``).

        ``schema`` defaults to Lima's (Allen County) field-map, so a bare ``from_attrs(attrs)``
        keeps working for callers/tests that pass Allen-shaped dicts.
        """
        s = schema or LIMA_PARCEL_SCHEMA
        return cls(
            parcel_no=_s(a.get(s.id_field)),
            owner=_s(a.get(s.owner_field)),
            owner_2=_s(a.get(s.owner_2_field)),
            deeded_owner=_s(a.get(s.deeded_owner_field)),
            situs_address=_join(*(a.get(f) for f in s.situs_fields)),
            owner_address=_join(*(a.get(f) for f in s.owner_addr_fields)),
            land_use_code=_decode_land_use(a.get(s.land_use_field), s.land_use_decode),
            acres=_f(a.get(s.acres_field)),
            market_land_value=_i(a.get(s.market_land_field)),
            market_improvement_value=_i(a.get(s.market_improvement_field)),
            market_total_value=_i(a.get(s.market_total_field)),
            cauv_value=_i(a.get(s.cauv_field)),
            tax_district=_s(a.get(s.tax_district_field)),
            school_code=_s(a.get(s.school_field)),
            neighborhood_code=_s(a.get(s.neighborhood_field)),
            last_sale_date=_decode_sale_date(a.get(s.sale_date_field), s.date_decode),
            last_sale_amount=_i(a.get(s.sale_amount_field)),
            valid_sale=_s(a.get(s.valid_sale_field)),
        )


def _s(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _i(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _f(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _join(*parts: Any) -> str | None:
    pieces = [str(p).strip() for p in parts if _s(p) is not None]
    return " ".join(pieces) or None


def _decode_sale_date(value: Any, mode: str) -> str | None:
    """Decode the GIS sale-date field per the schema's encoding."""
    if mode == "mmddyyyy":
        return _parse_parcel_date(value)
    if mode == "iso":
        return _s(value)
    if mode == "mmddyy":
        return _parse_mmddyy(value)
    if mode == "mdyyyy_slash":
        return _parse_mdyyyy_slash(value)
    if mode == "epoch_millis":
        return _parse_epoch_millis(value)
    return None


def _decode_land_use(value: Any, mode: str) -> int | None:
    """Decode the land-use field per the schema's encoding.

    ``"int"`` (default) is a bare numeric code (Lima ``LANDUSE``); ``"leading_int"`` is a
    ``"<code>: <label>"`` string whose leading integer is the code (Ohio ``StateLUC``, e.g.
    ``"511: Res-Custom Code"`` -> ``511``). Non-numeric / missing -> ``None`` (never invented).
    """
    if mode == "leading_int":
        if value is None:
            return None
        m = re.match(r"\s*(\d+)", str(value))
        return int(m.group(1)) if m else None
    return _i(value)


def _parse_parcel_date(value: Any) -> str | None:
    """Decode an ``M(M)DDYYYY``-integer sale field to ISO ``yyyy-mm-dd``.

    e.g. ``2252008`` -> ``2008-02-25``; ``8011994`` -> ``1994-08-01``. Returns
    ``None`` for missing/zero/unparseable values rather than inventing a date.
    """
    n = _i(value)
    if not n or n <= 0:
        return None
    digits = f"{n:08d}"  # MMDDYYYY zero-padded
    month, day, year = int(digits[:2]), int(digits[2:4]), int(digits[4:])
    if not (1 <= month <= 12 and 1 <= day <= 31 and 1800 <= year <= 2100):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def _iso_if_real_date(year: int, month: int, day: int) -> str | None:
    """ISO ``yyyy-mm-dd`` if ``(year, month, day)`` is a real calendar date, else ``None``.

    Range-checking the parts independently (``1 <= day <= 31``) accepts dates that do not exist —
    ``2/30/2025``, or ``2/29`` in a non-leap year — and a parser that emits one has invented a
    conveyance date the county never recorded. ``datetime.date`` is the calendar, leap years
    included; the surrounding 1800-2100 bound stays a plausibility guard on a mis-scanned year.
    """
    if not (1800 <= year <= 2100):
        return None
    try:
        return datetime.date(year, month, day).isoformat()
    except ValueError:
        return None


def _parse_mdyyyy_slash(value: Any) -> str | None:
    """Decode an ``M/D/YYYY`` sale string, with an optional trailing clock, to ISO ``yyyy-mm-dd``.

    e.g. ``"12/10/2025 12:00:00 AM"`` -> ``2025-12-10``; ``"1/4/2001"`` -> ``2001-01-04``. Clinton
    County serves its CAMA ``Date_Conveyed`` pre-formatted as **text**, not as an
    ``esriFieldTypeDate``, so the year is already four digits and no century pivot applies (unlike
    ``mmddyy``). The time component is always midnight and is discarded rather than parsed.
    Returns ``None`` for missing/unparseable values, including calendar-impossible ones.
    """
    text = _s(value)
    if text is None:
        return None
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})\b", text)
    if not m:
        return None
    return _iso_if_real_date(int(m.group(3)), int(m.group(1)), int(m.group(2)))


def _parse_epoch_millis(value: Any) -> str | None:
    """Decode an Esri ``esriFieldTypeDate`` (epoch milliseconds, UTC) to ISO ``yyyy-mm-dd``.

    ArcGIS serves Date fields as integer milliseconds since the Unix epoch (e.g. Allen County,
    IN ``TransferDate`` ``1704844800000`` -> ``2024-01-10``). Negative/zero/unparseable ->
    ``None`` (never inventing a date). Decoded in UTC, matching how the service stores the field.
    """
    n = _i(value)
    if not n or n <= 0:
        return None
    dt = datetime.datetime.fromtimestamp(n / 1000, tz=datetime.UTC)
    return dt.date().isoformat()


def _parse_mmddyy(value: Any) -> str | None:
    """Decode a ``MM-DD-YY`` two-digit-year sale string to ISO ``yyyy-mm-dd``.

    e.g. ``"08-05-94"`` -> ``1994-08-05``; ``"06-22-23"`` -> ``2023-06-22``. The century is
    resolved by the standard C/``strptime`` ``%y`` pivot -- ``69``-``99`` -> ``1900``s, ``00``-
    ``68`` -> ``2000``s -- a documented convention, not a per-row guess; verify the century
    against the deed for sales near the pivot. Returns ``None`` for missing/unparseable values,
    including calendar-impossible ones. Note the century pivot runs BEFORE the calendar check, so
    ``02-29-00`` resolves to 2000 (a leap year) and survives while ``02-29-01`` does not.
    """
    text = _s(value)
    if text is None:
        return None
    m = re.fullmatch(r"(\d{1,2})-(\d{1,2})-(\d{2})", text)
    if not m:
        return None
    month, day, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
    year = 1900 + yy if yy >= 69 else 2000 + yy
    return _iso_if_real_date(year, month, day)


def normalize_parcel_id(raw: str, *, rule: str = "dashless") -> str:
    """A parcel id as the GIS stores it.

    ``"dashless"`` strips every non-digit (``36-0100-03-002.000`` -> ``36010003002000``);
    ``"verbatim"`` returns it unchanged. Defaults to dashless (the Allen County rule), so the
    no-arg form keeps working for the POI / corpus-scan callers.
    """
    if rule == "verbatim":
        return raw
    return re.sub(r"\D", "", raw)


def _scope_where(where: str, schema: GisParcelSchema) -> str:
    """AND the schema's jurisdiction scope into a ``where`` clause (a no-op when unset).

    A multi-jurisdiction layer (the Ohio statewide parcels) must be filtered to one county; a
    single-jurisdiction layer (Lima/Allen) leaves ``query_scope`` empty, so the clause — and
    therefore the connector cache key — is byte-identical to the pre-scope request.
    """
    return f"({where}) AND ({schema.query_scope})" if schema.query_scope else where


def _query(params: dict[str, Any], *, settings: Settings, connector: str) -> dict[str, Any]:
    """Run (or replay) one ArcGIS ``/query`` request; return the parsed JSON."""
    query = {"f": "json", "returnGeometry": "false", **params}

    def fetch() -> Any:
        log.info(f"{connector}.fetch", where=params.get("where"), offset=params.get("resultOffset"))
        resp = httpx.get(
            f"{settings.parcels_url}/query",
            params=query,
            timeout=settings.hydro_request_timeout_s,
        )
        resp.raise_for_status()
        return resp.json()

    payload = cast("dict[str, Any]", cached_get(connector, query, fetch, settings=settings))
    if "error" in payload:
        raise AllenGisError(f"ArcGIS error: {payload['error']}")
    return payload


def query_parcels(
    where: str,
    *,
    out_fields: list[str] | None = None,
    max_records: int | None = None,
    settings: Settings | None = None,
) -> list[Parcel]:
    """Every parcel matching ``where``, paged to completion (or to ``max_records``)."""
    settings = settings or get_settings()
    schema = _parcel_schema(settings)
    fields = ",".join(out_fields or schema.out_fields)
    parcels: list[Parcel] = []
    offset = 0
    while True:
        page = _query(
            {
                "where": _scope_where(where, schema),
                "outFields": fields,
                "resultOffset": offset,
                "resultRecordCount": schema.page_size,
            },
            settings=settings,
            connector=schema.connector,
        )
        features = page.get("features") or []
        parcels.extend(Parcel.from_attrs(f.get("attributes", {}), schema) for f in features)
        if max_records is not None and len(parcels) >= max_records:
            return parcels[:max_records]
        if not page.get("exceededTransferLimit") or not features:
            return parcels
        offset += len(features)


def fetch_parcel(parcel_no: str, *, settings: Settings | None = None) -> Parcel | None:
    """One parcel by number (any separator format); ``None`` if the GIS has no match."""
    settings = settings or get_settings()
    schema = _parcel_schema(settings)
    normalized = normalize_parcel_id(parcel_no, rule=schema.id_normalize)
    matches = query_parcels(f"{schema.id_field}='{normalized}'", settings=settings)
    return matches[0] if matches else None


def parcels_by_owner(name: str, *, settings: Settings | None = None) -> list[Parcel]:
    """Parcels whose owner name contains ``name`` (case-insensitive substring)."""
    settings = settings or get_settings()
    schema = _parcel_schema(settings)
    if not schema.owner_field:
        raise AllenGisError(
            f"site {settings.site!r} parcel layer has no owner-name field "
            "(owner-redacted) — owner search is unavailable"
        )
    safe = name.upper().replace("'", "''")
    return query_parcels(f"UPPER({schema.owner_field}) LIKE '%{safe}%'", settings=settings)


def _geojson_feature(parcel: Parcel, geometry: Any) -> dict[str, Any]:
    """One GeoJSON Feature with schema-decoded, friendly properties (never the raw SDE keys)."""
    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": {
            "parcel_id": parcel.parcel_no,
            "owner": parcel.owner,
            "situs_address": parcel.situs_address,
            "owner_mailing_address": parcel.owner_address,
            "transfer_date": parcel.last_sale_date,
        },
    }


def query_parcels_geojson(where: str, *, settings: Settings | None = None) -> dict[str, Any]:
    """Every parcel matching ``where`` as a WGS84 GeoJSON ``FeatureCollection`` (with geometry).

    Asks ArcGIS for ``f=geojson`` (so the server emits RFC-7946 geometry — no Esri-ring
    conversion) reprojected to ``outSR=4326``, then re-keys each feature's properties through
    the schema decode (``Parcel.from_attrs``) so the committed file carries friendly names, not
    the layer's fully-qualified SDE field keys. Paged to completion like ``query_parcels``.
    """
    settings = settings or get_settings()
    schema = _parcel_schema(settings)
    fields = ",".join(schema.out_fields)
    features: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = _query(
            {
                "where": _scope_where(where, schema),
                "outFields": fields,
                "returnGeometry": "true",
                "outSR": "4326",
                "f": "geojson",
                "resultOffset": offset,
                "resultRecordCount": schema.page_size,
            },
            settings=settings,
            connector=schema.connector,
        )
        page_features = page.get("features") or []
        for ft in page_features:
            parcel = Parcel.from_attrs(ft.get("properties", {}), schema)
            features.append(_geojson_feature(parcel, ft.get("geometry")))
        if not page.get("exceededTransferLimit") or not page_features:
            return {"type": "FeatureCollection", "features": features}
        offset += len(page_features)


def parcels_geojson_by_owner(name: str, *, settings: Settings | None = None) -> dict[str, Any]:
    """A WGS84 GeoJSON ``FeatureCollection`` of every parcel whose owner contains ``name``."""
    settings = settings or get_settings()
    schema = _parcel_schema(settings)
    if not schema.owner_field:
        raise AllenGisError(
            f"site {settings.site!r} parcel layer has no owner-name field "
            "(owner-redacted) — owner search is unavailable"
        )
    safe = name.upper().replace("'", "''")
    return query_parcels_geojson(f"UPPER({schema.owner_field}) LIKE '%{safe}%'", settings=settings)


def parcel_at_point(lon: float, lat: float, *, settings: Settings | None = None) -> Parcel | None:
    """The parcel containing a WGS84 point, or ``None`` if none intersects.

    A spatial ``intersects`` query against the parcel layer — the join that turns a geocoded
    address or a facility coordinate into a canonical parcel id (the POI resolve-to-parcel
    funnel). The GIS repeats split rows, so the result is deduped.
    """
    settings = settings or get_settings()
    schema = _parcel_schema(settings)
    point_params: dict[str, Any] = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": ",".join(schema.out_fields),
    }
    if schema.query_scope:  # scope a multi-jurisdiction layer to its county (no-op for Lima)
        point_params["where"] = schema.query_scope
    page = _query(point_params, settings=settings, connector=schema.connector)
    features = page.get("features") or []
    parcels = _dedupe([Parcel.from_attrs(f.get("attributes", {}), schema) for f in features])
    return parcels[0] if parcels else None


# --- Citations + reference dataset -----------------------------------------


def scan_parcel_ids(*roots: Path, settings: Settings | None = None) -> list[str]:
    """Distinct deed-style parcel ids cited under the given roots (verbatim form).

    Per-site (#611): the deed-id pattern comes from the active site's ``gis_parcel`` schema
    (``deed_id_regex``), resolved at call time — not bound to Lima's format at import (Lima =
    the ``36-0100-03-002.000`` 2-4-2-3.3 form). A site with no parcel schema yields no ids.
    """
    settings = settings or get_settings()
    schema = active_profile(settings).gis_parcel
    if schema is None:
        return []
    parcel_re = re.compile(schema.deed_id_regex)
    found: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".md", ".yaml", ".yml", ".txt"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            found.update(parcel_re.findall(text))
    return sorted(found)


# --- Defense-industry land scan -------------------------------------------
# Jurisdiction-specific (Lima = the JSMC / Lima Army Tank Plant): its configuration lives on
# the parcel schema's optional ``defense`` block, so this never runs another jurisdiction's
# owner/tax-district filter.


def _defense_config(schema: GisParcelSchema, settings: Settings) -> GisDefenseConfig:
    if schema.defense is None:
        raise AllenGisError(
            f"site {settings.site!r} has no defense-land scan configured (gis_parcel.defense)"
        )
    return schema.defense


def _dedupe(parcels: list[Parcel]) -> list[Parcel]:
    """Keep the first row per distinct ``parcel_no`` (the GIS repeats split rows)."""
    seen: set[str] = set()
    out: list[Parcel] = []
    for p in parcels:
        key = p.parcel_no or ""
        if key and key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _owner_names(p: Parcel) -> str:
    """The owner/deed-owner text a pattern is matched against (upper-cased)."""
    return " ".join(filter(None, (p.owner, p.owner_2, p.deeded_owner))).upper()


def defense_owner_scan(
    primes: list[tuple[str, list[str]]], *, settings: Settings | None = None
) -> dict[str, list[Parcel]]:
    """County parcels whose owner name matches a defense-prime pattern.

    ``primes`` is ``[(prime_name, [patterns...]), ...]`` (e.g. from the curated defense-
    contractor seed list). One OR-ed GIS query covers all patterns across the owner fields the
    schema names for the scan; each returned parcel is then tagged locally to the prime(s) it
    matched. Returns ``{prime: [parcels]}`` for primes with at least one hit (empty when no
    prime owns county land — the expected result for Lima, whose defense footprint is
    federally held).
    """
    settings = settings or get_settings()
    schema = _parcel_schema(settings)
    fields = _defense_config(schema, settings).owner_scan_fields
    patterns = sorted({p.upper().replace("'", "''") for _, pats in primes for p in pats})
    if not patterns:
        return {}
    clauses = [
        "(" + " OR ".join(f"UPPER({f}) LIKE '%{p}%'" for f in fields) + ")" for p in patterns
    ]
    parcels = _dedupe(query_parcels(" OR ".join(clauses), settings=settings))
    hits: dict[str, list[Parcel]] = {}
    for name, pats in primes:
        for parcel in parcels:
            text = _owner_names(parcel)
            if any(pat.upper() in text for pat in pats):
                hits.setdefault(name, []).append(parcel)
    return hits


def army_controlled_defense_land(*, settings: Settings | None = None) -> list[Parcel]:
    """The federally-held enclave the defense-contractor seed list flags (Lima = the JSMC).

    Returns the federally-held parcels noted to "function as Army-controlled land" — the
    actual local defense footprint, held by the United States rather than by a prime in its
    own name. Configured by ``gis_parcel.defense`` (owner + tax district).
    """
    settings = settings or get_settings()
    schema = _parcel_schema(settings)
    cfg = _defense_config(schema, settings)
    where = (
        f"{schema.owner_field}='{cfg.enclave_owner}' "
        f"AND {schema.tax_district_field}='{cfg.enclave_tax_district}'"
    )
    return _dedupe(query_parcels(where, settings=settings))


def write_defense_scan(
    prime_owned: dict[str, list[Parcel]],
    army_controlled: list[Parcel],
    out_dir: Path,
    *,
    patterns_searched: int,
    settings: Settings | None = None,
) -> Path:
    """Write the defense-land scan (prime-owned + Army-controlled) to one YAML file."""
    settings = settings or get_settings()
    schema = _parcel_schema(settings)
    meta = _defense_config(schema, settings).meta
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "parcels.defense.yaml"
    owned_rows = [
        {"matched_prime": name, **p.model_dump()}
        for name, parcels in sorted(prime_owned.items())
        for p in sorted(parcels, key=lambda p: p.parcel_no or "")
    ]
    doc = {
        "meta": {
            "subject": meta.subject,
            "source": meta.source,
            "source_url": meta.source_url,
            "scan": meta.scan,
            "patterns_searched": patterns_searched,
            "prime_owned_count": len(owned_rows),
            "finding": meta.finding,
            "army_controlled_note": meta.army_controlled_note,
            "caveats": list(meta.caveats),
        },
        "prime_owned": owned_rows,
        "army_controlled": [
            p.model_dump() for p in sorted(army_controlled, key=lambda p: p.parcel_no or "")
        ],
    }
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def _parcel_doc(p: Parcel) -> dict[str, Any]:
    return p.model_dump()


def write_parcels(
    parcels: list[Parcel], out_dir: Path, *, scope: str, settings: Settings | None = None
) -> Path:
    """Write parcels to one YAML file with a provenance ``meta`` block."""
    settings = settings or get_settings()
    meta = _parcel_schema(settings).meta
    out_dir.mkdir(parents=True, exist_ok=True)
    ordered = sorted(parcels, key=lambda p: p.parcel_no or "")
    path = out_dir / f"parcels.{scope}.yaml"
    doc = {
        "meta": {
            "subject": meta.subject,
            "scope": scope,
            "source": meta.source,
            "source_url": meta.source_url,
            "count": len(ordered),
            "caveats": list(meta.caveats),
        },
        "parcels": [_parcel_doc(p) for p in ordered],
    }
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def write_parcels_geojson(
    feature_collection: dict[str, Any], path: Path, *, settings: Settings | None = None
) -> Path:
    """Write a parcel ``FeatureCollection`` to ``path``, stamping a provenance foreign member.

    The provenance lives under a top-level ``bosc:provenance`` key (an RFC-7946 foreign member,
    ignored by GeoJSON readers) so the committed reference file is self-describing and regenerable.
    """
    settings = settings or get_settings()
    meta = _parcel_schema(settings).meta
    path.parent.mkdir(parents=True, exist_ok=True)
    features = sorted(
        feature_collection.get("features", []),
        key=lambda f: f.get("properties", {}).get("parcel_id") or "",
    )
    doc = {
        "type": "FeatureCollection",
        "bosc:provenance": {
            "subject": meta.subject,
            "source": meta.source,
            "source_url": meta.source_url,
            "crs": "EPSG:4326 (WGS84)",
            "count": len(features),
            "caveats": list(meta.caveats),
        },
        "features": features,
    }
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return path
