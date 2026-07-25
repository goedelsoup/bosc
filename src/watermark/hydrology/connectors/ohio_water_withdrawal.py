"""Ohio DNR Water Withdrawal Facilities Registration Program (WWFRP) connector.

The makeup-side data source for the cooling-water account (epic #1676). Under R.C.
1521.16 every facility able to withdraw **>100,000 gallons/day** (70 gpm) registers
with the Ohio DNR, Division of Water Resources, and files an **annual water-use
report**. The Division publishes the registry as a public **ArcGIS FeatureServer**:

* a facility **point layer** (id 0, ``DSW_WaterWithdrawalFacility_A_GIS``) — one row
  per registered facility: registration number, name, county, primary use type,
  registered capacity (MGD), source counts, HUC-12, status, coordinates;
* three **annual-total tables**, each one-to-many to the facility on
  ``RegistrationNumber`` and shaped ``Year`` + twelve monthly columns + ``Total``,
  values in **million gallons (MG)**:
  ground-water (id 3, ``…_I_GW_Totals``), surface-water (id 2, ``…_J_SW_Totals``),
  and water **returned** to the source (id 1, ``…_K_Return_Totals``).

Why the makeup side matters: a "closed-loop-dry" facility (``CLOSED_LOOP_DRY``,
:mod:`watermark.hydrology.cooling_models`) is modeled at ~0 water, but a sealed
process loop with an evaporative heat-rejection tower still *cycles* — makeup in,
blowdown out. A reported annual withdrawal is the single strongest tell of that
spend, and the reported **return** is the discharge peer (makeup - return ~
consumptive). So this connector pulls all three series; the A3 reconciliation
harness (#1679) back-solves cycles-of-concentration against the claimed archetype.

Reported quantities are ``[verified]`` for the reported amount; anything inferred
from them (implied blowdown, cycles, or the once-through IT-load inversion via
:func:`implied_it_load_mw`) is ``[inference]``. Like every hydrology connector this
reuses :func:`_cache.cached_get` (on-disk cache + TTL + offline/committed-fixture
fallback), so tests and CI never touch the network. Synchronous (``httpx``).

**Ohio only.** The WWFRP is Ohio's registry; a non-Ohio watershed point (Fort Wayne,
IN) has its own state service and is not served here — the CLI refuses cleanly rather
than query the wrong state. The regional **Great Lakes-St. Lawrence River Water Use
Database** (glc.org) is a *secondary, aggregate* source (basin / jurisdiction / use
sector, not facility level, for confidentiality) and is left as a documented lead.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import httpx
import yaml
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.connectors import to_float, to_int, to_str
from watermark.hydrology.connectors._cache import cached_get
from watermark.logging import get_logger

log = get_logger(__name__)

# FeatureServer layer/table ids (intrinsic to the service, not per-site config).
OHIO_WWFRP_FACILITY_LAYER = 0  # DSW_WaterWithdrawalFacility_A_GIS (point)
OHIO_WWFRP_RETURN_TABLE = 1  # DSW_waterwithdrawal_K_Return_Totals — water returned to source
OHIO_WWFRP_SW_TABLE = 2  # DSW_waterwithdrawal_J_SW_Totals — surface-water withdrawal
OHIO_WWFRP_GW_TABLE = 3  # DSW_waterwithdrawal_I_GW_Totals — ground-water withdrawal

# ArcGIS server page size. County-scale volumes sit far under any hosted maxRecordCount,
# but the query loop pages to completion (and logs a warning) rather than truncate silently.
_PAGE_SIZE = 2000

# The annual-total tables' month columns (as published) -> the uppercase key the rest of
# the hydrology package uses. Order is calendar order.
_MONTH_COLUMNS: tuple[tuple[str, str], ...] = (
    ("Jan", "JAN"),
    ("Feb", "FEB"),
    ("Mar", "MAR"),
    ("Apr", "APR"),
    ("May", "MAY"),
    ("Jun", "JUN"),
    ("Jul", "JUL"),
    ("Aug", "AUG"),
    ("Sep", "SEP"),
    ("Oct", "OCT"),
    ("Nov", "NOV"),
    ("Dec", "DEC"),
)

# The per-table count column (wells / intakes / return records for that year). The three
# tables name it differently; everything else about them is identical.
_COUNT_COLUMN = {
    OHIO_WWFRP_GW_TABLE: "WellCount",
    OHIO_WWFRP_SW_TABLE: "Well_Count",
    OHIO_WWFRP_RETURN_TABLE: "RecCount",
}

# Facility-layer fields we read by name (never by index — column order is not stable).
_FACILITY_FIELDS = (
    "RegistrationNumber",
    "Name",
    "CountyName",
    "FacilityPrimaryUseType",
    "FacilityTotCapacity",
    "GWSTotNumWells",
    "GWSTotWellsWithdrawalCap",
    "SWSTotNumIntakes",
    "SWSTotIntakesWithdrawalCap",
    "Status",
    "RegistrationDate",
    "InactiveDate",
    "HUC12",
    "LastAnnualReportYear",
    "Latitude",
    "Longitude",
)


class WwfrpError(RuntimeError):
    """An ArcGIS-level error from the WWFRP FeatureServer (query rejected, etc.)."""


class AnnualWithdrawal(BaseModel):
    """One facility-year of a single series (ground-water, surface-water, or return).

    ``total_mg`` and every ``monthly_mg`` value are **million gallons**, verbatim from
    the annual-total table; a missing month is a genuine ``None`` (not a fabricated 0).
    ``count`` is that year's well / intake / return-record count for the series.
    """

    model_config = ConfigDict(extra="forbid")

    year: int
    total_mg: float | None
    monthly_mg: dict[str, float | None]
    count: int | None = None

    def mean_daily_mgd(self) -> float | None:
        """The reported annual total as a mean daily rate (MGD).

        A calendar-year total in million gallons divided by the days in that year is
        million-gallons-per-day; leap years use 366. ``None`` when the year has no total.
        """
        if self.total_mg is None:
            return None
        return self.total_mg / _days_in_year(self.year)


class WithdrawalFacility(BaseModel):
    """One registered WWFRP facility: its registry record + annual-total series.

    Registry fields are verbatim from the facility point layer; capacities are the
    *registered* capacity (MGD), distinct from the *reported* annual withdrawal carried
    on the series lists. ``ground_water`` / ``surface_water`` / ``returns`` hold one
    :class:`AnnualWithdrawal` per reported year (newest first), filtered to the pull's
    ``since_year`` floor.
    """

    model_config = ConfigDict(extra="forbid")

    registration_number: str
    name: str | None
    county: str | None
    primary_use_type: str | None  # FacilityPrimaryUseType (Public, Industry, Agriculture, …)
    status: str | None  # Active / Inactive
    total_capacity_mgd: float | None  # registered capacity, NOT reported withdrawal
    gw_wells: int | None
    gw_capacity_mgd: float | None
    sw_intakes: int | None
    sw_capacity_mgd: float | None
    huc12: str | None
    latitude: float | None
    longitude: float | None
    registration_date: str | None  # ISO date
    inactive_date: str | None  # ISO date
    last_annual_report_year: int | None
    ground_water: list[AnnualWithdrawal] = []
    surface_water: list[AnnualWithdrawal] = []
    returns: list[AnnualWithdrawal] = []

    def reported_years(self) -> list[int]:
        """Every year with a withdrawal record (ground- or surface-water), newest first."""
        years = {a.year for a in (*self.ground_water, *self.surface_water)}
        return sorted(years, reverse=True)

    def withdrawal_total_mg(self, year: int) -> float | None:
        """Combined ground- + surface-water withdrawal (million gallons) for ``year``.

        ``None`` when the facility reported neither series that year; a series present but
        blank contributes 0 (a reported zero), so a facility that withdrew only surface
        water still sums cleanly.
        """
        totals = [
            a.total_mg
            for a in (*self.ground_water, *self.surface_water)
            if a.year == year and a.total_mg is not None
        ]
        return sum(totals) if totals else None

    def return_total_mg(self, year: int) -> float | None:
        """Water returned to the source (million gallons) for ``year``; ``None`` if unreported."""
        totals = [a.total_mg for a in self.returns if a.year == year and a.total_mg is not None]
        return sum(totals) if totals else None

    def mean_daily_withdrawal_mgd(self, year: int | None = None) -> float | None:
        """Combined reported withdrawal as a mean daily rate (MGD) for ``year``.

        ``year`` defaults to the most recent reported year. This is the makeup-side figure
        the cooling-water account reads; ``None`` when there is no reported year to read.
        """
        if year is None:
            years = self.reported_years()
            if not years:
                return None
            year = years[0]
        total = self.withdrawal_total_mg(year)
        if total is None:
            return None
        return total / _days_in_year(year)


class WithdrawalRegistry(BaseModel):
    """The WWFRP registry for one county: its facilities + the pull's provenance."""

    model_config = ConfigDict(extra="forbid")

    county: str
    state: str = "OH"
    source_url: str
    since_year: int
    facilities: list[WithdrawalFacility]


# --- ArcGIS query -----------------------------------------------------------------------


def _days_in_year(year: int) -> int:
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    return 366 if leap else 365


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


def _query_all(
    layer: int, where: str, out_fields: str, *, settings: Settings
) -> list[dict[str, Any]]:
    """Every ``attributes`` dict matching ``where`` on a layer/table, paged to completion.

    Each page is a distinct cache key (the ``resultOffset`` is in the params), so an
    offline replay needs one committed fixture per page — for county-scale pulls that is a
    single page. A server that still flags ``exceededTransferLimit`` at the last fetched
    page is logged (no silent truncation), per the connectors' data discipline.
    """
    base = settings.ohio_water_withdrawal_base_url
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        # ``layer`` MUST be in the cache-key params: it lives in the URL path, not the query
        # string, so the ground/surface/return tables share an identical ``where`` and would
        # otherwise collide on one key — silently serving one table's rows for all three.
        params: dict[str, Any] = {
            "layer": layer,
            "where": where,
            "outFields": out_fields,
            "resultOffset": offset,
            "resultRecordCount": _PAGE_SIZE,
        }

        def fetch(_offset: int = offset) -> Any:
            log.info("ohio_water_withdrawal.fetch", layer=layer, where=where, offset=_offset)
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
            cached_get("ohio_water_withdrawal", params, fetch, settings=settings),
        )
        if "error" in payload:
            raise WwfrpError(f"ArcGIS error on layer {layer}: {payload['error']}")
        features = payload.get("features") or []
        rows.extend(f.get("attributes", {}) for f in features)
        if not features or not payload.get("exceededTransferLimit"):
            if payload.get("exceededTransferLimit"):
                log.warning(
                    "ohio_water_withdrawal.transfer_limit",
                    layer=layer,
                    where=where,
                    fetched=len(rows),
                )
            return rows
        offset += len(features)


def _series_from_rows(rows: list[dict[str, Any]], table: int) -> list[AnnualWithdrawal]:
    """Parse annual-total table rows into :class:`AnnualWithdrawal`, newest year first."""
    count_field = _COUNT_COLUMN[table]
    out: list[AnnualWithdrawal] = []
    for attrs in rows:
        year = to_int(attrs.get("Year"))
        if year is None:
            continue
        out.append(
            AnnualWithdrawal(
                year=year,
                total_mg=to_float(attrs.get("Total")),
                monthly_mg={key: to_float(attrs.get(col)) for col, key in _MONTH_COLUMNS},
                count=to_int(attrs.get(count_field)),
            )
        )
    return sorted(out, key=lambda a: a.year, reverse=True)


def _facility_from_attrs(attrs: dict[str, Any]) -> WithdrawalFacility | None:
    """Build the registry record from a facility-layer feature; ``None`` without a reg number."""
    reg = to_str(attrs.get("RegistrationNumber"))
    if reg is None:
        return None
    return WithdrawalFacility(
        registration_number=reg,
        name=to_str(attrs.get("Name")),
        county=to_str(attrs.get("CountyName")),
        primary_use_type=to_str(attrs.get("FacilityPrimaryUseType")),
        status=to_str(attrs.get("Status")),
        total_capacity_mgd=to_float(attrs.get("FacilityTotCapacity")),
        gw_wells=to_int(attrs.get("GWSTotNumWells")),
        gw_capacity_mgd=to_float(attrs.get("GWSTotWellsWithdrawalCap")),
        sw_intakes=to_int(attrs.get("SWSTotNumIntakes")),
        sw_capacity_mgd=to_float(attrs.get("SWSTotIntakesWithdrawalCap")),
        huc12=to_str(attrs.get("HUC12")),
        latitude=to_float(attrs.get("Latitude")),
        longitude=to_float(attrs.get("Longitude")),
        registration_date=_iso_date(attrs.get("RegistrationDate")),
        inactive_date=_iso_date(attrs.get("InactiveDate")),
        last_annual_report_year=to_int(attrs.get("LastAnnualReportYear")),
    )


def _attach_series(
    facilities: list[WithdrawalFacility], *, since_year: int, settings: Settings
) -> None:
    """Pull the three annual-total series for a set of facilities and attach them in place.

    One ``RegistrationNumber IN (...)`` query per table (ground / surface / return),
    filtered to ``Year >= since_year`` — three fetches for the whole county rather than
    three per facility. Registration numbers are sorted so the ``where`` clause (and its
    cache key) is deterministic.
    """
    regs = sorted(f.registration_number for f in facilities)
    if not regs:
        return
    reg_list = ", ".join(_sql_quote(r) for r in regs)
    where = f"RegistrationNumber IN ({reg_list}) AND Year >= {int(since_year)}"
    by_reg: dict[str, WithdrawalFacility] = {f.registration_number: f for f in facilities}
    for table, target in (
        (OHIO_WWFRP_GW_TABLE, "ground_water"),
        (OHIO_WWFRP_SW_TABLE, "surface_water"),
        (OHIO_WWFRP_RETURN_TABLE, "returns"),
    ):
        grouped: dict[str, list[dict[str, Any]]] = {}
        for attrs in _query_all(table, where, "*", settings=settings):
            reg = to_str(attrs.get("RegistrationNumber"))
            if reg is not None:
                grouped.setdefault(reg, []).append(attrs)
        for reg, rows in grouped.items():
            fac = by_reg.get(reg)
            if fac is not None:
                setattr(fac, target, _series_from_rows(rows, table))


def fetch_county(
    county: str, *, since_year: int | None = None, settings: Settings | None = None
) -> WithdrawalRegistry:
    """Every WWFRP-registered facility in an Ohio county, with its annual-total series.

    ``county`` is the bare county name as the registry stores it (e.g. ``"Allen"``), and
    ``since_year`` floors the annual-total window (default
    ``settings.ohio_water_withdrawal_since_year``); the facility registry itself is always
    returned in full, regardless of the floor. Facilities come back sorted by registration
    number.
    """
    settings = settings or get_settings()
    if since_year is None:
        since_year = settings.ohio_water_withdrawal_since_year

    facility_rows = _query_all(
        OHIO_WWFRP_FACILITY_LAYER,
        f"CountyName = {_sql_quote(county)}",
        ",".join(_FACILITY_FIELDS),
        settings=settings,
    )
    facilities = [f for f in (_facility_from_attrs(a) for a in facility_rows) if f is not None]
    facilities.sort(key=lambda f: f.registration_number)
    _attach_series(facilities, since_year=since_year, settings=settings)

    return WithdrawalRegistry(
        county=county,
        source_url=f"{settings.ohio_water_withdrawal_base_url}/{OHIO_WWFRP_FACILITY_LAYER}",
        since_year=since_year,
        facilities=facilities,
    )


def fetch_facility(
    registration_number: str, *, since_year: int | None = None, settings: Settings | None = None
) -> WithdrawalFacility | None:
    """One facility by registration number, with its annual-total series; ``None`` if unknown."""
    settings = settings or get_settings()
    if since_year is None:
        since_year = settings.ohio_water_withdrawal_since_year
    rows = _query_all(
        OHIO_WWFRP_FACILITY_LAYER,
        f"RegistrationNumber = {_sql_quote(registration_number)}",
        ",".join(_FACILITY_FIELDS),
        settings=settings,
    )
    facilities = [f for f in (_facility_from_attrs(a) for a in rows) if f is not None]
    if not facilities:
        return None
    _attach_series(facilities, since_year=since_year, settings=settings)
    return facilities[0]


# --- the makeup-side -> IT-load seam (#1677 / feeds A3 #1679) ---------------------------


def implied_it_load_mw(
    withdrawal_mgd: float, *, heat_reject_multiplier: float | None = None
) -> float:
    """Invert a reported withdrawal (MGD) to the IT load (MW) it implies **as once-through**.

    A thin wrapper over :func:`watermark.hydrology.cooling_models.it_load_mw_from_once_through_withdrawal`
    that closes the makeup-side seam this connector exists to open: a reported withdrawal
    figure feeds the once-through inversion. The result is an ``[inference]`` and is only
    physically meaningful when the withdrawal *is* a once-through cooling intake — for a
    recirculating tower the withdrawal is makeup (not condenser flow), and for a public /
    agricultural / industrial-process registrant the inversion is meaningless. The A3
    reconciliation harness (#1679) is what applies it selectively per archetype; this keeps
    the connector and the cooling math from drifting on the unit chain.
    """
    from watermark.hydrology.cooling_models import it_load_mw_from_once_through_withdrawal

    if heat_reject_multiplier is None:
        return it_load_mw_from_once_through_withdrawal(withdrawal_mgd)
    return it_load_mw_from_once_through_withdrawal(
        withdrawal_mgd, heat_reject_multiplier=heat_reject_multiplier
    )


# --- reference dataset assembly ---------------------------------------------------------


def county_slug(county: str) -> str:
    """A filesystem slug for a county name (``"Allen"`` / ``"Allen County, OH"`` -> ``"allen"``)."""
    bare = county.split(" County")[0].strip() or county.strip()
    return "-".join(bare.lower().split())


def _series_doc(series: list[AnnualWithdrawal]) -> list[dict[str, Any]]:
    return [
        {
            "year": a.year,
            "total_mg": a.total_mg,
            "count": a.count,
            "monthly_mg": a.monthly_mg,
        }
        for a in series
    ]


def _facility_doc(fac: WithdrawalFacility) -> dict[str, Any]:
    return {
        "registration_number": fac.registration_number,
        "name": fac.name,
        "county": fac.county,
        "primary_use_type": fac.primary_use_type,
        "status": fac.status,
        "total_capacity_mgd": fac.total_capacity_mgd,
        "gw_wells": fac.gw_wells,
        "gw_capacity_mgd": fac.gw_capacity_mgd,
        "sw_intakes": fac.sw_intakes,
        "sw_capacity_mgd": fac.sw_capacity_mgd,
        "huc12": fac.huc12,
        "latitude": fac.latitude,
        "longitude": fac.longitude,
        "registration_date": fac.registration_date,
        "inactive_date": fac.inactive_date,
        "last_annual_report_year": fac.last_annual_report_year,
        "ground_water": _series_doc(fac.ground_water),
        "surface_water": _series_doc(fac.surface_water),
        "returns": _series_doc(fac.returns),
    }


def _use_type_counts(facilities: list[WithdrawalFacility]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for fac in facilities:
        key = (fac.primary_use_type or "?").strip()
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def write_registry(registry: WithdrawalRegistry, out_dir: Path) -> Path:
    """Write one county's WWFRP registry to YAML with a ``meta:`` provenance block.

    Deterministic: every value is verbatim from the service and facilities are reg-number
    sorted, so re-running an unchanged pull regenerates identical bytes (no generation
    timestamp — the data self-dates via each facility's ``last_annual_report_year``).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{county_slug(registry.county)}.yaml"
    facilities = registry.facilities
    active = sum(1 for f in facilities if (f.status or "").lower() == "active")
    reporting = sum(1 for f in facilities if f.reported_years())
    doc = {
        "meta": {
            "subject": (
                f"Ohio DNR Water Withdrawal Facilities Registration Program — "
                f"{registry.county} County, {registry.state}"
            ),
            "source": (
                "Ohio DNR, Division of Water Resources — Water Withdrawal Facilities "
                "Registration Program (WWFRP), R.C. 1521.16 (>100,000 gpd registration + "
                "annual water-use reports)"
            ),
            "source_url": registry.source_url,
            "county": registry.county,
            "state": registry.state,
            "since_year": registry.since_year,
            "facility_count": len(facilities),
            "active_count": active,
            "reporting_count": reporting,
            "use_type_counts": _use_type_counts(facilities),
            "units": "annual/monthly withdrawal + return values are million gallons (MG)",
            "caveats": [
                "Withdrawal/return amounts are verbatim from the WWFRP annual-total tables; "
                "nothing is inferred, normalized, or backfilled — a blank month is null.",
                "Capacities (total_capacity_mgd, *_capacity_mgd) are the REGISTERED capacity, "
                "not the reported withdrawal (which lives on the annual series).",
                f"Annual series are floored at {registry.since_year}; the facility registry is "
                "kept in full. Older years remain live at the source.",
                "Registration is self-reported; a use type is the registrant's declared primary "
                "use. Any IT-load inversion from a withdrawal is [inference], never [verified].",
            ],
        },
        "facilities": [_facility_doc(f) for f in facilities],
    }
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path
