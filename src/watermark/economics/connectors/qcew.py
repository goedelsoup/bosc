"""BLS QCEW — county employment by NAICS sector + government ownership, with location quotients.

The Quarterly Census of Employment and Wages open-data CSV API is keyless and
returns one county's full industry breakdown. We reduce it inside the ``fetch``
callable (selecting columns **by name**, never index) to the three slices we use —
the county total (all ownerships), the private-ownership NAICS *sectors*, and the
federal/state/local *government* ownership rows (own 1/2/3 at agglvl 71) — so the
cached payload / committed fixture stays small. The government slices close the
total-vs-sectors reconciliation the private-only mix leaves open (#1661): at a federal
enclave the federal row is the county's largest employer yet carries no NAICS sector.
QCEW covers UI-covered + federal-civilian (UCFE) employment only — uniformed active-duty
military is in neither the total nor any ownership row (see ``model.QCEW_COVERAGE_NOTE``).
QCEW already publishes the **location quotient** (``lq_annual_avg_emplvl``): a slice's
county employment share over its national share, i.e. its export-orientation — the closest
county-level proxy for an import/export ratio (no clean county trade series exists).
"""

from __future__ import annotations

import csv
import io
from typing import Any, cast

import httpx

from watermark.config import Settings, get_settings
from watermark.connectors import cached_get, to_float
from watermark.economics.model import (
    IndustryEmployment,
    OwnershipEmployment,
    SectorEmployment,
)
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
_OWN_AGG = "71"  # county, by ownership (all industries) — the government-ownership rows
_ALL_INDUSTRY = "10"  # "Total, all industries" (the industry_code carried at agglvl 71)
_TOTAL_OWN = "0"  # all ownerships (for the total)
_PRIVATE_OWN = "5"  # private (for the sector mix)
# Government ownerships (own_code -> title). The federal / state / local slices the private-only
# sector mix cannot show; their sum plus the private sectors reconciles the all-ownership total
# (#1661). Federal first — at an enclave it is the county's single largest employer.
_GOV_OWN: dict[str, str] = {
    "1": "Federal Government",
    "2": "State Government",
    "3": "Local Government",
}


def _row_figures(row: dict[str, Any], *, with_lq: bool = False) -> dict[str, Any]:
    """Pull the employment / establishments / wage (and optional LQ) figures from a CSV row,
    selected **by name** (issue #1109), shared by the total, sector, and government branches."""
    figures = {
        "emp": to_float(row.get("annual_avg_emplvl", "")),
        "estabs": to_float(row.get("annual_avg_estabs", "")),
        "pay": to_float(row.get("avg_annual_pay", "")),
        "wkly": to_float(row.get("annual_avg_wkly_wage", "")),
    }
    if with_lq:
        figures["lq"] = to_float(row.get("lq_annual_avg_emplvl", ""))
    return figures


def _reduce_csv(text: str) -> dict[str, Any]:
    """Reduce the full county CSV to the county total, private NAICS sectors, and government rows.

    Wage columns (``avg_annual_pay``, ``annual_avg_wkly_wage``) ride along on the total, each
    sector, and each government row — selected by name, same as everything else (issue #1109).
    The government rows (own 1/2/3 at agglvl 71, the all-industries slice) close the total-vs-
    sectors reconciliation the private-only sector mix leaves open (#1661).
    """
    total: dict[str, Any] | None = None
    sectors: list[dict[str, Any]] = []
    government: list[dict[str, Any]] = []
    for row in csv.DictReader(io.StringIO(text)):
        own, agg = row.get("own_code"), row.get("agglvl_code")
        if own == _TOTAL_OWN and agg == _TOTAL_AGG:
            total = _row_figures(row)
        elif own == _PRIVATE_OWN and agg == _SECTOR_AGG:
            sectors.append(
                {"naics": row.get("industry_code", ""), **_row_figures(row, with_lq=True)}
            )
        elif own in _GOV_OWN and agg == _OWN_AGG and row.get("industry_code") == _ALL_INDUSTRY:
            government.append(
                {"own": own, "name": _GOV_OWN[own], **_row_figures(row, with_lq=True)}
            )
    return {"total": total or {}, "sectors": sectors, "government": government}


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

    def _conn(row: dict[str, Any], key: str, unit: str) -> ProvenancedValue | None:
        """A connector value from a reduced-row figure, or ``None`` when QCEW omitted it
        (a suppressed slice) — keeps a reported 0 (e.g. an LQ of 0.0), unlike ``_pay``."""
        val = row.get(key)
        return (
            ProvenancedValue.from_connector(float(val), unit, citation=cite, asof=asof)
            if val is not None
            else None
        )

    def _pay(row: dict[str, Any], key: str, unit: str) -> ProvenancedValue | None:
        """A wage figure as a connector value — omitted (never $0) when QCEW reports
        no covered wages for the row (a suppressed or zero-employment slice)."""
        val = row.get(key)
        if val is None or float(val) <= 0:
            return None
        return ProvenancedValue.from_connector(float(val), unit, citation=cite, asof=asof)

    def _wage_fields(row: dict[str, Any]) -> dict[str, ProvenancedValue | None]:
        """The establishments / pay / weekly-wage / LQ figures shared by a sector or government
        row. Pay is omitted when employment rounds to 0 — surfacing "$X pay, 0 jobs" would read
        as real (#1109) — while establishments and the LQ keep a reported value (incl. 0)."""
        has_jobs = float(row.get("emp") or 0.0) > 0
        return {
            "establishments": _conn(row, "estabs", "establishments"),
            "avg_annual_pay": _pay(row, "pay", "USD/year") if has_jobs else None,
            "avg_weekly_wage": _pay(row, "wkly", "USD/week") if has_jobs else None,
            "location_quotient": _conn(row, "lq", "ratio"),
        }

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
        naics = str(s.get("naics", ""))
        sectors.append(
            SectorEmployment(
                naics=naics,
                sector_name=_SECTOR_NAMES.get(naics, naics),
                annual_avg_employment=ProvenancedValue.from_connector(
                    float(emp), "jobs", citation=cite, asof=asof
                ),
                **_wage_fields(s),
            )
        )
    sectors.sort(key=lambda x: x.annual_avg_employment.value, reverse=True)

    # Government ownership (own 1/2/3, agglvl 71) — the federal/state/local slices the private
    # sector mix cannot show, closing the total-vs-sectors reconciliation (#1661). Kept in own-code
    # order (federal → state → local): at a federal enclave the federal row leads and is the
    # county's single largest employer, yet carries no NAICS sector of its own.
    government: list[OwnershipEmployment] = []
    for g in payload.get("government") or []:
        emp = g.get("emp")
        if emp is None:
            continue
        government.append(
            OwnershipEmployment(
                ownership=str(g.get("own", "")),
                ownership_name=str(g.get("name", "")),
                annual_avg_employment=ProvenancedValue.from_connector(
                    float(emp), "jobs", citation=cite, asof=asof
                ),
                **_wage_fields(g),
            )
        )

    return IndustryEmployment(
        fips=fips,
        area_name=area_name,
        year=year,
        total_employment=total_emp,
        establishments=establishments,
        avg_annual_pay=_pay(total, "pay", "USD/year"),
        avg_weekly_wage=_pay(total, "wkly", "USD/week"),
        sectors=sectors,
        government=government,
    )
