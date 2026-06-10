"""BLS QCEW — county employment by NAICS sector, with built-in location quotients.

The Quarterly Census of Employment and Wages open-data CSV API is keyless and
returns one county's full industry breakdown. We reduce it inside the ``fetch``
callable (selecting columns **by name**, never index) to the two slices we use —
the county total (all ownerships) and the private-ownership NAICS *sectors* — so the
cached payload / committed fixture stays small. QCEW already publishes the
**location quotient** (``lq_annual_avg_emplvl``): a sector's county employment share
over its national share, i.e. its export-orientation — the closest county-level
proxy for an import/export ratio (no clean county trade series exists).
"""

from __future__ import annotations

import csv
import io
from typing import Any, cast

import httpx

from bosc.config import Settings, get_settings
from bosc.connectors import cached_get
from bosc.economics.model import IndustryEmployment, SectorEmployment
from bosc.hydrology.model import ProvenancedValue

# Official NAICS 2-digit sector titles (stable reference, not data) for QCEW codes.
_SECTOR_NAMES: dict[str, str] = {
    "11": "Agriculture, Forestry, Fishing & Hunting",
    "21": "Mining, Quarrying, Oil & Gas Extraction",
    "22": "Utilities",
    "23": "Construction",
    "31-33": "Manufacturing",
    "42": "Wholesale Trade",
    "44-45": "Retail Trade",
    "48-49": "Transportation & Warehousing",
    "51": "Information",
    "52": "Finance & Insurance",
    "53": "Real Estate & Rental & Leasing",
    "54": "Professional, Scientific & Technical Services",
    "55": "Management of Companies & Enterprises",
    "56": "Administrative & Support & Waste Management",
    "61": "Educational Services",
    "62": "Health Care & Social Assistance",
    "71": "Arts, Entertainment & Recreation",
    "72": "Accommodation & Food Services",
    "81": "Other Services (except Public Administration)",
    "92": "Public Administration",
}

_TOTAL_AGG = "70"  # county, total, all industries
_SECTOR_AGG = "74"  # county, by NAICS sector
_TOTAL_OWN = "0"  # all ownerships (for the total)
_PRIVATE_OWN = "5"  # private (for the sector mix)


def _num(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _reduce_csv(text: str) -> dict[str, Any]:
    """Reduce the full county CSV to the county total + private NAICS-sector rows."""
    total: dict[str, Any] | None = None
    sectors: list[dict[str, Any]] = []
    for row in csv.DictReader(io.StringIO(text)):
        own, agg = row.get("own_code"), row.get("agglvl_code")
        if own == _TOTAL_OWN and agg == _TOTAL_AGG:
            total = {
                "emp": _num(row.get("annual_avg_emplvl", "")),
                "estabs": _num(row.get("annual_avg_estabs", "")),
            }
        elif own == _PRIVATE_OWN and agg == _SECTOR_AGG:
            sectors.append(
                {
                    "naics": row.get("industry_code", ""),
                    "emp": _num(row.get("annual_avg_emplvl", "")),
                    "estabs": _num(row.get("annual_avg_estabs", "")),
                    "lq": _num(row.get("lq_annual_avg_emplvl", "")),
                }
            )
    return {"total": total or {}, "sectors": sectors}


def fetch_county_industries(
    *, year: int, fips: str | None = None, settings: Settings | None = None
) -> IndustryEmployment:
    """County employment by NAICS sector for one year, with location quotients."""
    settings = settings or get_settings()
    fips = fips or settings.econ_fips
    params = {"connector": "qcew", "year": year, "area": fips, "agg": "a"}

    def fetch() -> Any:
        url = f"{settings.qcew_base_url}/{year}/a/area/{fips}.csv"
        resp = httpx.get(url, timeout=settings.econ_request_timeout_s, follow_redirects=True)
        resp.raise_for_status()
        return _reduce_csv(resp.text)

    payload = cast(
        "dict[str, Any]",
        cached_get(
            "qcew",
            params,
            fetch,
            cache_dir=settings.econ_cache_dir,
            offline=settings.econ_offline,
            fixtures_dir=settings.econ_fixtures_dir,
        ),
    )
    cite = f"BLS QCEW {year} annual averages, area {fips}"
    total = payload.get("total") or {}
    total_emp = ProvenancedValue.from_connector(
        float(total.get("emp") or 0.0), "jobs", citation=cite
    )
    estabs_val = total.get("estabs")
    establishments = (
        ProvenancedValue.from_connector(float(estabs_val), "establishments", citation=cite)
        if estabs_val is not None
        else None
    )

    sectors: list[SectorEmployment] = []
    for s in payload.get("sectors") or []:
        emp = s.get("emp")
        if emp is None:
            continue
        naics = str(s.get("naics", ""))
        lq = s.get("lq")
        sectors.append(
            SectorEmployment(
                naics=naics,
                sector_name=_SECTOR_NAMES.get(naics, naics),
                annual_avg_employment=ProvenancedValue.from_connector(
                    float(emp), "jobs", citation=cite
                ),
                establishments=(
                    ProvenancedValue.from_connector(
                        float(s["estabs"]), "establishments", citation=cite
                    )
                    if s.get("estabs") is not None
                    else None
                ),
                location_quotient=(
                    ProvenancedValue.from_connector(float(lq), "ratio", citation=cite)
                    if lq is not None
                    else None
                ),
            )
        )
    sectors.sort(key=lambda x: x.annual_avg_employment.value, reverse=True)
    return IndustryEmployment(
        fips=fips,
        area_name="Allen County, Ohio",
        year=year,
        total_employment=total_emp,
        establishments=establishments,
        sectors=sectors,
    )
