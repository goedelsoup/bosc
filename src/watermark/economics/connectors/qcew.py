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

from watermark.config import Settings, get_settings
from watermark.connectors import cached_get, to_float
from watermark.economics.model import IndustryEmployment, SectorEmployment
from watermark.hydrology.model import ProvenancedValue
from watermark.sites import active_profile

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
    "99": "Unclassified",
}


class QcewError(RuntimeError):
    """The QCEW response is missing the county-total row we key the baseline on.

    Raised rather than coercing a missing total to ``0.0`` — a fabricated
    ``[verified]`` "zero covered employment" claim manufactured from missing data
    (CSV drift, a mistyped FIPS, or an empty upstream response) would violate
    "prefer omission over invention." Symmetric with :class:`EiaError` on an empty
    EIA payload.
    """


_TOTAL_AGG = "70"  # county, total, all industries
_SECTOR_AGG = "74"  # county, by NAICS sector
_TOTAL_OWN = "0"  # all ownerships (for the total)
_PRIVATE_OWN = "5"  # private (for the sector mix)


def _reduce_csv(text: str) -> dict[str, Any]:
    """Reduce the full county CSV to the county total + private NAICS-sector rows.

    Wage columns (``avg_annual_pay``, ``annual_avg_wkly_wage``) ride along on both the
    total and each sector — selected by name, same as everything else (issue #1109).
    """
    total: dict[str, Any] | None = None
    sectors: list[dict[str, Any]] = []
    for row in csv.DictReader(io.StringIO(text)):
        own, agg = row.get("own_code"), row.get("agglvl_code")
        if own == _TOTAL_OWN and agg == _TOTAL_AGG:
            total = {
                "emp": to_float(row.get("annual_avg_emplvl", "")),
                "estabs": to_float(row.get("annual_avg_estabs", "")),
                "pay": to_float(row.get("avg_annual_pay", "")),
                "wkly": to_float(row.get("annual_avg_wkly_wage", "")),
            }
        elif own == _PRIVATE_OWN and agg == _SECTOR_AGG:
            sectors.append(
                {
                    "naics": row.get("industry_code", ""),
                    "emp": to_float(row.get("annual_avg_emplvl", "")),
                    "estabs": to_float(row.get("annual_avg_estabs", "")),
                    "pay": to_float(row.get("avg_annual_pay", "")),
                    "wkly": to_float(row.get("annual_avg_wkly_wage", "")),
                    "lq": to_float(row.get("lq_annual_avg_emplvl", "")),
                }
            )
    return {"total": total or {}, "sectors": sectors}


def fetch_county_industries(
    *,
    year: int,
    fips: str | None = None,
    area_name: str | None = None,
    settings: Settings | None = None,
) -> IndustryEmployment:
    """County employment by NAICS sector for one year, with location quotients.

    ``area_name`` labels the county; the caller passes the authoritative Census name
    (``build_baseline``). It falls back to the active site profile's ``county_name`` so a
    standalone call is never mislabeled with another site's county.
    """
    settings = settings or get_settings()
    fips = fips or settings.econ_fips
    area_name = area_name or active_profile(settings).county_name
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
    # The annual-average year is the natural staleness marker (issue #1107); a bare year is
    # valid reduced-precision ISO 8601. The human citation already carries it in prose.
    asof = str(year)

    def _pay(row: dict[str, Any], key: str, unit: str) -> ProvenancedValue | None:
        """A wage figure as a connector value — omitted (never $0) when QCEW reports
        no covered wages for the row (a suppressed or zero-employment slice)."""
        val = row.get(key)
        if val is None or float(val) <= 0:
            return None
        return ProvenancedValue.from_connector(float(val), unit, citation=cite, asof=asof)

    total = payload.get("total") or {}
    emp = total.get("emp")
    if emp is None:
        raise QcewError(
            f"QCEW response for area {fips} ({year}) carried no county-total employment row "
            f"(agg {_TOTAL_AGG}, own {_TOTAL_OWN}) — refusing to fabricate a zero from missing data"
        )
    total_emp = ProvenancedValue.from_connector(float(emp), "jobs", citation=cite, asof=asof)
    estabs_val = total.get("estabs")
    establishments = (
        ProvenancedValue.from_connector(
            float(estabs_val), "establishments", citation=cite, asof=asof
        )
        if estabs_val is not None
        else None
    )

    sectors: list[SectorEmployment] = []
    for s in payload.get("sectors") or []:
        emp = s.get("emp")
        if emp is None:
            continue
        # Pay is meaningless without covered employment: QCEW occasionally reports a nonzero
        # avg_annual_pay on a sector whose annual_avg_emplvl rounds to 0 (e.g. an "Unclassified"
        # slice) — surfacing "$X pay, 0 jobs" would read as real, so omit pay when emp is 0 (#1109).
        has_jobs = float(emp) > 0
        naics = str(s.get("naics", ""))
        lq = s.get("lq")
        sectors.append(
            SectorEmployment(
                naics=naics,
                sector_name=_SECTOR_NAMES.get(naics, naics),
                annual_avg_employment=ProvenancedValue.from_connector(
                    float(emp), "jobs", citation=cite, asof=asof
                ),
                establishments=(
                    ProvenancedValue.from_connector(
                        float(s["estabs"]), "establishments", citation=cite, asof=asof
                    )
                    if s.get("estabs") is not None
                    else None
                ),
                avg_annual_pay=_pay(s, "pay", "USD/year") if has_jobs else None,
                avg_weekly_wage=_pay(s, "wkly", "USD/week") if has_jobs else None,
                location_quotient=(
                    ProvenancedValue.from_connector(float(lq), "ratio", citation=cite, asof=asof)
                    if lq is not None
                    else None
                ),
            )
        )
    sectors.sort(key=lambda x: x.annual_avg_employment.value, reverse=True)
    return IndustryEmployment(
        fips=fips,
        area_name=area_name,
        year=year,
        total_employment=total_emp,
        establishments=establishments,
        avg_annual_pay=_pay(total, "pay", "USD/year"),
        avg_weekly_wage=_pay(total, "wkly", "USD/week"),
        sectors=sectors,
    )
