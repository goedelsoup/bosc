"""EPA RSEI (Risk-Screening Environmental Indicators) — per-county toxic-release inventory.

Pulls the EPA **RSEI Public Data Set** (AWS Open Data ``s3://epa-rsei-pds``, served
at the public HTTPS endpoint) and reduces it to the facilities in one county (Allen
County, OH by default). Each facility carries its modeled, population-weighted RSEI
**Score** (with the cancer / non-cancer split), the toxicity-weighted **Hazard**,
and **pounds released** — as a cumulative total, a per-year time series, a by-media
breakdown, and the top contributing chemicals.

RSEI is a relational dump; the reduction joins five tables (keys in parentheses)::

    elements   (ReleaseNumber)   -> Score, CScore, NCScore, Hazard, Population
      via release    (ReleaseNumber -> SubmissionNumber, Media, PoundsReleased)
      via submission (SubmissionNumber -> FacilityNumber, ChemicalNumber, Year)
      via facility   (FacilityNumber -> name, coords, parent, NPDES permit, ...)
      via chemical   (ChemicalNumber -> name, CAS, toxicity category)

The bulk ``.gz`` tables (``elements`` alone is ~250 MB) are **not** committed: they
cache under the git-ignored ``data/cache/rsei/`` and the committed artifact is the
small per-county YAML under ``data/reference/rsei/``. Regenerate with ``bosc rsei``.

Nothing here is fabricated. Pounds are summed from the reported ``release`` rows;
Score / Cancer / Non-cancer / Hazard are summed from EPA's modeled ``elements``
rows — they are EPA's modeled output, **not** a BOSC estimate. A facility with
reported pounds but no modeled element (non-modeled media/chemical) shows pounds
with a zero Score, which is faithful to the data.
"""

from __future__ import annotations

import csv
import gzip
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import BaseModel

from bosc.config import Settings, get_settings
from bosc.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterator

log = get_logger(__name__)

# --- Source layout ---------------------------------------------------------
# The five tables the per-county reduction needs, plus the small media lookup.
_TABLES = ("facility", "submission", "release", "chemical", "media")
# RSEI text uses Latin-1 (facility/chemical names carry bytes that aren't UTF-8).
_ENC = "latin-1"
# MediaCode (media.csv last column) -> the bucket we report pounds under.
_MEDIA_GROUP = {1: "air", 3: "water", 4: "underground", 5: "land", 6: "potw", 7: "offsite"}
_DEFAULT_FIPS = "39003"  # Allen County, OH
_DEFAULT_COUNTY = "Allen County, OH"
_TOP_CHEMICALS = 8

_SOURCE = "EPA RSEI Public Data Set (AWS Open Data s3://epa-rsei-pds)"
_CAVEATS = [
    "Pounds are summed from reported `release` rows; Score/Cancer/NonCancer/Hazard "
    "from EPA's modeled `elements` rows. Nothing is estimated by BOSC.",
    "Score is EPA's modeled, population-weighted Risk-Screening Score (unitless, "
    "comparative only — NOT a risk or a concentration). Hazard = pounds x toxicity "
    "weight (no exposure/population term).",
    "A facility with reported pounds but a zero Score released only non-modeled "
    "media/chemicals in the modeled years — faithful to the data, not a gap.",
    "RSEI tracks TRI reporters; small/unpermitted sources and non-TRI chemicals are "
    "out of scope by construction.",
]


# --- Models ----------------------------------------------------------------
class RseiYearScore(BaseModel):
    """One reporting year of a facility's RSEI totals."""

    year: int
    score: float
    cancer_score: float
    noncancer_score: float
    hazard: float
    pounds: float


class RseiChemicalScore(BaseModel):
    """A chemical's contribution to a facility (cumulative across years)."""

    chemical: str
    cas: str | None = None
    toxicity_category: str | None = None  # Carcinogen / Non-carcinogen / Mixed / None
    score: float
    pounds: float


class RseiFacility(BaseModel):
    """One TRI/RSEI facility in the target county, with modeled results rolled up."""

    facility_id: str
    facility_number: str
    name: str
    parent_name: str | None = None
    federal_facility: bool = False
    latitude: float | None = None
    longitude: float | None = None
    street: str | None = None
    city: str | None = None
    state: str | None = None
    fips: str
    npdes_permit: str | None = None
    naics: str | None = None
    sic: str | None = None
    water_releases: bool = False
    # Modeled results, cumulative across the reporting record.
    score: float = 0.0
    cancer_score: float = 0.0
    noncancer_score: float = 0.0
    hazard: float = 0.0
    pounds: float = 0.0
    pounds_by_media: dict[str, float] = {}
    first_year: int | None = None
    last_year: int | None = None
    years: list[RseiYearScore] = []
    top_chemicals: list[RseiChemicalScore] = []


class RseiInventory(BaseModel):
    """The committed per-county RSEI artifact: provenance meta + ranked facilities."""

    meta: dict[str, Any]
    county_fips: str
    county_name: str
    facilities: list[RseiFacility]


# --- Helpers ---------------------------------------------------------------
def _f(x: str | None) -> float:
    if x is None or x in ("", "NA"):
        return 0.0
    try:
        return float(x)
    except ValueError:
        return 0.0


def _clean(x: str | None) -> str | None:
    """Normalize an RSEI text cell: strip, treat ``NA``/empty as missing."""
    if x is None:
        return None
    x = x.strip()
    return None if x in ("", "NA", "<Not Assigned>") else x


def _code(x: str | None) -> str | None:
    """Like :func:`_clean` but also drops RSEI's ``0`` unassigned-code sentinel."""
    v = _clean(x)
    return None if v == "0" else v


def _read_csv_gz(path: Path) -> Iterator[dict[str, str]]:
    with gzip.open(path, "rt", encoding=_ENC, newline="") as fh:
        yield from csv.DictReader(fh)


def table_path(settings: Settings, name: str) -> Path:
    """Cache path for an RSEI table's gzip (under the git-ignored data/cache)."""
    return settings.rsei_cache_dir / settings.rsei_version / "data_tables" / f"{name}.csv.gz"


def _ensure_table(settings: Settings, name: str) -> Path:
    """Return the local gzip for ``name``, downloading it to cache if absent.

    Bulk tables are large (``elements`` ~250 MB) — they live only in the git-ignored
    cache, never committed. Download is skipped when the file is already present, so a
    pre-warmed cache makes regeneration fully offline.
    """
    path = table_path(settings, name)
    if path.is_file() and path.stat().st_size > 0:
        return path
    if settings.rsei_offline:
        raise FileNotFoundError(
            f"RSEI table {name!r} not in cache ({path}) and rsei_offline is set. "
            f"Pre-warm the cache or run online."
        )
    import httpx

    url = f"{settings.rsei_base_url}/{settings.rsei_version}/data_tables/{name}.csv.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    log.info("rsei.download", table=name, url=url)
    with (
        httpx.stream(
            "GET", url, timeout=settings.rsei_request_timeout_s, follow_redirects=True
        ) as resp,
        path.open("wb") as out,
    ):
        resp.raise_for_status()
        for chunk in resp.iter_bytes():
            out.write(chunk)
    return path


# --- Build -----------------------------------------------------------------
def build_inventory(
    settings: Settings | None = None,
    *,
    fips: str | None = None,
    county_name: str | None = None,
) -> RseiInventory:
    """Pull RSEI and reduce it to one county's facilities with rolled-up results."""
    settings = settings or get_settings()
    fips = fips or settings.rsei_fips
    county_name = county_name or _DEFAULT_COUNTY
    for name in _TABLES:
        _ensure_table(settings, name)

    # media code -> reporting bucket (air/water/land/...)
    media_group: dict[str, str] = {}
    for row in _read_csv_gz(table_path(settings, "media")):
        try:
            media_group[row["Media"]] = _MEDIA_GROUP.get(int(row["MediaCode"]), "other")
        except (ValueError, KeyError):
            continue

    # chemical lookup
    chem: dict[str, dict[str, str | None]] = {}
    for row in _read_csv_gz(table_path(settings, "chemical")):
        chem[row["ChemicalNumber"]] = {
            "name": _clean(row.get("Chemical")),
            "cas": _clean(row.get("CASStandard")),
            "category": _clean(row.get("ToxicityCategory")),
        }

    # facility roster for the county, keyed by FacilityNumber
    facilities: dict[str, RseiFacility] = {}
    for row in _read_csv_gz(table_path(settings, "facility")):
        if row.get("FIPS") != fips:
            continue
        facilities[row["FacilityNumber"]] = RseiFacility(
            facility_id=row["FacilityID"],
            facility_number=row["FacilityNumber"],
            name=row.get("FacilityName") or row["FacilityID"],
            parent_name=_clean(row.get("ParentName")),
            # FederalFacilityFlag is an agency code (e.g. "D" = DoD), blank for private
            # sites; any non-empty, non-negative value marks a federal facility.
            federal_facility=(row.get("FederalFacilityFlag") or "").strip() not in ("", "N", "NA"),
            latitude=_f(row.get("Latitude")) or None,
            longitude=_f(row.get("Longitude")) or None,
            street=_clean(row.get("Street")),
            city=_clean(row.get("City")),
            state=_clean(row.get("State")),
            fips=fips,
            npdes_permit=_clean(row.get("NPDESPermit")),
            # DerivedNAICS/DerivedSIC are "0" (unassigned) in this set; the primary
            # reported code lives in NAICS1/SIC1.
            naics=_code(row.get("NAICS1")),
            sic=_code(row.get("SIC1")),
            water_releases=_f(row.get("WaterReleases")) > 0,
        )
    log.info("rsei.facilities", county=county_name, n=len(facilities))

    # submission -> (FacilityNumber, year, ChemicalNumber), county only
    sub: dict[str, tuple[str, int, str]] = {}
    for row in _read_csv_gz(table_path(settings, "submission")):
        fn = row["FacilityNumber"]
        if fn not in facilities:
            continue
        try:
            yr = int(row["SubmissionYear"])
        except ValueError:
            continue
        sub[row["SubmissionNumber"]] = (fn, yr, row["ChemicalNumber"])

    # release -> (FacilityNumber, year, ChemicalNumber, media-bucket, pounds), county only.
    # Pounds accumulate here (reported); ReleaseNumber bridges to the modeled elements.
    rel: dict[str, tuple[str, int, str]] = {}
    pounds_fy: dict[tuple[str, int], float] = defaultdict(float)
    pounds_media: dict[tuple[str, str], float] = defaultdict(float)
    pounds_chem: dict[tuple[str, str], float] = defaultdict(float)
    for row in _read_csv_gz(table_path(settings, "release")):
        meta = sub.get(row["SubmissionNumber"])
        if meta is None:
            continue
        fn, yr, cn = meta
        rel[row["ReleaseNumber"]] = (fn, yr, cn)
        lbs = _f(row.get("PoundsReleased"))
        pounds_fy[(fn, yr)] += lbs
        pounds_media[(fn, media_group.get(row.get("Media", ""), "other"))] += lbs
        pounds_chem[(fn, cn)] += lbs

    # elements -> modeled Score/Cancer/NonCancer/Hazard, summed per facility/year/chemical.
    score_fy: dict[tuple[str, int], list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
    score_chem: dict[tuple[str, str], float] = defaultdict(float)
    n_elem = 0
    for row in _read_csv_gz(table_path(settings, "elements")):
        meta = rel.get(row["ReleaseNumber"])
        if meta is None:
            continue
        fn, yr, cn = meta
        n_elem += 1
        s, cs, ncs, hz = _f(row["Score"]), _f(row["CScore"]), _f(row["NCScore"]), _f(row["Hazard"])
        acc = score_fy[(fn, yr)]
        acc[0] += s
        acc[1] += cs
        acc[2] += ncs
        acc[3] += hz
        score_chem[(fn, cn)] += s
    log.info("rsei.elements_matched", n=n_elem)

    _rollup(facilities, pounds_fy, pounds_media, pounds_chem, score_fy, score_chem, chem)

    ranked = sorted(facilities.values(), key=lambda f: (-f.score, -f.pounds, f.name))
    n_scored = sum(1 for f in ranked if f.score > 0)
    return RseiInventory(
        meta={
            "subject": f"RSEI toxic-release inventory — {county_name}",
            "source": _SOURCE,
            "version": settings.rsei_version,
            "county_fips": fips,
            "facility_count": len(ranked),
            "scored_facility_count": n_scored,
            "join": "elements -> release -> submission -> facility (+ chemical, media)",
            "caveats": _CAVEATS,
        },
        county_fips=fips,
        county_name=county_name,
        facilities=ranked,
    )


def _rollup(
    facilities: dict[str, RseiFacility],
    pounds_fy: dict[tuple[str, int], float],
    pounds_media: dict[tuple[str, str], float],
    pounds_chem: dict[tuple[str, str], float],
    score_fy: dict[tuple[str, int], list[float]],
    score_chem: dict[tuple[str, str], float],
    chem: dict[str, dict[str, str | None]],
) -> None:
    """Fold the per-year / per-chemical accumulators onto each facility in place."""
    years_by_fac: dict[str, set[int]] = defaultdict(set)
    for fn, yr in pounds_fy:
        years_by_fac[fn].add(yr)
    for (fn, yr), _ in score_fy.items():
        years_by_fac[fn].add(yr)

    for fn, fac in facilities.items():
        years: list[RseiYearScore] = []
        for yr in sorted(years_by_fac.get(fn, set())):
            s, cs, ncs, hz = score_fy.get((fn, yr), [0.0, 0.0, 0.0, 0.0])
            years.append(
                RseiYearScore(
                    year=yr,
                    score=round(s, 1),
                    cancer_score=round(cs, 1),
                    noncancer_score=round(ncs, 1),
                    hazard=round(hz, 1),
                    pounds=round(pounds_fy.get((fn, yr), 0.0), 1),
                )
            )
        fac.years = years
        fac.score = round(sum(y.score for y in years), 1)
        fac.cancer_score = round(sum(y.cancer_score for y in years), 1)
        fac.noncancer_score = round(sum(y.noncancer_score for y in years), 1)
        fac.hazard = round(sum(y.hazard for y in years), 1)
        fac.pounds = round(sum(y.pounds for y in years), 1)
        fac.first_year = years[0].year if years else None
        fac.last_year = years[-1].year if years else None
        fac.pounds_by_media = {
            bucket: round(v, 1)
            for bucket, v in sorted(
                ((b, pounds_media.get((fn, b), 0.0)) for b in _MEDIA_GROUP.values()),
                key=lambda kv: -kv[1],
            )
            if v > 0
        }

        # Top chemicals by modeled score, falling back to pounds when nothing scored.
        cn_scores = {cn: sc for (f2, cn), sc in score_chem.items() if f2 == fn}
        cn_pounds = {cn: lb for (f2, cn), lb in pounds_chem.items() if f2 == fn}
        all_cn = set(cn_scores) | set(cn_pounds)
        top = sorted(all_cn, key=lambda cn: (-cn_scores.get(cn, 0.0), -cn_pounds.get(cn, 0.0)))
        fac.top_chemicals = [
            RseiChemicalScore(
                chemical=(chem.get(cn, {}).get("name") or f"chem#{cn}"),
                cas=chem.get(cn, {}).get("cas"),
                toxicity_category=chem.get(cn, {}).get("category"),
                score=round(cn_scores.get(cn, 0.0), 1),
                pounds=round(cn_pounds.get(cn, 0.0), 1),
            )
            for cn in top[:_TOP_CHEMICALS]
        ]


# --- Load / write ----------------------------------------------------------
def load_inventory(reference_dir: Path) -> RseiInventory | None:
    """Load the committed ``data/reference/rsei/inventory.yaml`` if present."""
    path = reference_dir / "rsei" / "inventory.yaml"
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return RseiInventory.model_validate(data)


def write_inventory(inv: RseiInventory, out_dir: Path) -> Path:
    """Write the per-county inventory as deterministic YAML (no timestamp)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "inventory.yaml"
    data = inv.model_dump(mode="json", exclude_none=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
    )
    return path
