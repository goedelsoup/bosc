"""Toxic-load x assimilative-capacity screen for the industrial water dischargers.

:mod:`watermark.hydrology.assimilative` screens the three *municipal* WWTPs against
their receiving stream's cited 7Q10. This module extends that screen to the
*industrial* side: the EPA RSEI facilities that release toxics **to water**
(:mod:`watermark.rsei`), placed on the same receiving reaches and read against the same
cited low flows (:mod:`watermark.hydrology.lowflow`).

The headline the data carries: the county's highest-RSEI-Score water dischargers —
INEOS, Lima Refining, PCS Nitrogen — cluster on the **Ottawa River at Lima**, whose
cited 7Q10 is **0.2 cfs (1Q10 = 0)**. The toxic load is largest exactly where the
stream's assimilative capacity is smallest, and that floor coincides with the
May-Oct growing-season precipitation deficit the report already frames.

Provenance discipline (the corpus is litigation evidence):

* **Receiving water** is resolved on a ladder, never invented —
  1. a coordinate/name match to an EPA **ECHO** facility that carries a cited
     receiving water (``connector``);
  2. otherwise, membership in the Ottawa River industrial corridor at Lima, a
     coordinate-cluster **inference** (``assumption``) flagged as such;
  3. otherwise left ``None`` and reported "uncharacterized".
* The **screening concentration** (annual reported water pounds carried at the
  receiving stream's 7Q10) is a coarse, order-of-magnitude ``derived`` value: it
  assumes the reported water releases enter that reach, annualized over the
  facility's reporting years, fully mixed at design low flow, with no decay or mixing zone.
  It is a *screen*, not a permit determination or a measured concentration.

**Chemical-specific criteria (WS-07 / #1607).** The screen no longer collapses chemically
distinct pollutants into one aggregate mg/L against a flat 1.0 mg/L band. Each facility's
per-chemical *water* load (``RseiFacility.top_water_chemicals``, the media-3 breakdown —
ammonia, chlorine, nitrate, metals, cyanide, …, **not** the all-media ``top_chemicals``) is
carried at its regulatory design flow and screened against its **own Ohio water-quality
criterion** (``watermark.hydrology.criteria``, committed under ``data/reference/wqs/``). Each
criterion type pairs to its design flow: **acute** (CMC / OMZM) → **1Q10**, **chronic**
(CCC / OMZA) → **7Q10**, **human health** (public water supply) → **harmonic mean**. This is
the standard regulatory form of assimilative capacity — loading capacity = Q x (criterion minus
background) — a far stronger, harder-to-rebut finding than an arbitrary aggregate band. A
chemical with no committed Ohio criterion is reported ``no_criterion`` (omitted, never guessed);
the Ottawa's 1Q10 = 0 cfs means *zero* acute assimilative capacity — any acute load exceeds by
construction, surfaced honestly (no ``Inf`` concentration).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.hydrology import criteria, units
from watermark.hydrology.criteria import CriteriaTable, WaterQualityCriterion
from watermark.hydrology.lowflow import _normalize, load_low_flows
from watermark.hydrology.model import ProvenancedValue, SourceKind
from watermark.logging import get_logger
from watermark.rsei import RseiFacility, RseiWaterChemical, load_inventory
from watermark.sites import active_profile

if TYPE_CHECKING:
    from pathlib import Path

log = get_logger(__name__)

# lbs/day -> mg/L at a flow Q: mg/L = (lbs/day) / (MGD * 8.34). The 8.34 lb per
# (mg/L · MG) factor is the standard regulatory mass-balance conversion; cfs->MGD
# goes through units.cfs_to_mgd (1 cfs ≈ 0.6464 MGD). Used only for the screening
# concentration below.
_LBS_PER_MGL_MGD = 8.34

# The receiving-water industrial corridor box + its inferred receiving water are per-site
# (active SiteProfile: toxic_corridor_bbox, receiving_water_name). A facility inside the box
# without an independently cited receiving water is *inferred* to discharge there
# (tagged `assumption`).

# Spatial-join tolerance (degrees ~ 0.0018 ≈ 200 m at this latitude) for matching an
# RSEI facility to an ECHO permit by coordinate.
_MATCH_DEG = 0.0018


# --- Models ----------------------------------------------------------------
class CriterionScreen(BaseModel):
    """One chemical read against one Ohio criterion type at its regulatory design flow.

    ``criterion_type`` ∈ {``acute``, ``chronic``, ``human_health``}, each paired to its design
    flow (1Q10 / 7Q10 / harmonic mean). ``exceedance_factor`` = derived concentration ÷
    criterion = reported load ÷ loading capacity; ≥ 1 is an exceedance. When the design flow is
    0 cfs (the Ottawa 1Q10) there is no assimilative capacity: ``derived_concentration`` and
    ``exceedance_factor`` are ``None`` (not ``Inf``), ``loading_capacity_lb_day`` is 0, and the
    flag is ``exceedance`` — any load exceeds by construction (see ``note``).
    """

    model_config = ConfigDict(extra="forbid")

    criterion_type: str  # "acute" | "chronic" | "human_health"
    design_flow: ProvenancedValue  # 1Q10 / 7Q10 / harmonic-mean cfs
    criterion: ProvenancedValue  # the Ohio criterion, mg/L (reference)
    reported_load_lb_day: float  # annual water pounds / 365
    loading_capacity_lb_day: float | None  # criterion x Q x 8.34 (0 when the flow is 0)
    derived_concentration: ProvenancedValue | None  # mg/L at the design flow (None when Q = 0)
    exceedance_factor: float | None  # derived / criterion (None when Q = 0 -> unbounded)
    flag: str  # "exceedance" | "approach" | "ok"
    note: str | None = None


class ChemicalScreen(BaseModel):
    """One water-released chemical, screened against every applicable Ohio criterion."""

    model_config = ConfigDict(extra="forbid")

    chemical: str
    cas: str | None = None
    annual_water_pounds: float  # cumulative water pounds / reporting years
    reporting_years: int
    criteria: list[CriterionScreen] = []  # empty when no criterion is committed
    flag: str  # worst across `criteria`, or "no_criterion"


class ToxicDischargeScreen(BaseModel):
    """One RSEI water-releasing facility read against its receiving stream's 7Q10."""

    model_config = ConfigDict(extra="forbid")

    facility: str
    rsei_facility_id: str
    latitude: float | None = None
    longitude: float | None = None

    # RSEI modeled toxic magnitude (EPA's output, not a BOSC estimate).
    score: float
    cancer_score: float
    water_pounds: float  # cumulative pounds released to water over the record
    annual_water_pounds: float  # derived: water_pounds / count of reporting years
    year_span: str | None = None  # "1988-2022"
    top_water_chemical: str | None = None

    # Resolved discharge target.
    npdes_id: str | None = None  # matched ECHO permit, if any
    receiving_water: str | None = None
    receiving_water_source: SourceKind | None = None  # connector | assumption
    receiving_water_citation: str | None = None

    # Assimilative context.
    low_flow_7q10: ProvenancedValue | None = None
    # Aggregate mg/L (all water toxics summed, at the 7Q10). Kept as coarse *context* only —
    # superseded by the per-chemical `chemical_screens`; the flag no longer derives from it.
    screening_concentration: ProvenancedValue | None = None  # mg/L, derived, aggregate context

    # The per-chemical, per-criterion screen (WS-07): each water chemical against its own Ohio
    # criterion at the criterion's design flow. The facility `flag` is derived from these.
    chemical_screens: list[ChemicalScreen] = []

    flag: str  # "critical" | "elevated" | "context" | "uncharacterized"
    detail: str


class ToxicDischargeInventory(BaseModel):
    """The committed screen artifact: provenance meta + ranked dischargers."""

    model_config = ConfigDict(extra="forbid")

    meta: dict[str, Any]
    screens: list[ToxicDischargeScreen]

    @property
    def flagged(self) -> list[ToxicDischargeScreen]:
        """Facilities on a near-undiluted reach (the `critical` band)."""
        return [s for s in self.screens if s.flag == "critical"]


# --- Resolution helpers ----------------------------------------------------
def _in_corridor(
    lat: float | None, lon: float | None, bbox: tuple[float, float, float, float]
) -> bool:
    if lat is None or lon is None:
        return False
    lat_min, lat_max, lon_min, lon_max = bbox
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def _match_echo(fac: RseiFacility, echo: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Closest ECHO facility within the spatial tolerance, else None."""
    if fac.latitude is None or fac.longitude is None:
        return None
    best: dict[str, Any] | None = None
    best_d = _MATCH_DEG
    for e in echo:
        elat, elon = e.get("latitude"), e.get("longitude")
        if elat is None or elon is None:
            continue
        d = ((elat - fac.latitude) ** 2 + (elon - fac.longitude) ** 2) ** 0.5
        if d <= best_d:
            best, best_d = e, d
    return best


def _resolve_receiving_water(
    fac: RseiFacility, echo: list[dict[str, Any]], *, settings: Settings
) -> tuple[str | None, SourceKind | None, str | None, str | None]:
    """Resolve (receiving_water, source, citation, npdes_id) on the provenance ladder."""
    match = _match_echo(fac, echo)
    npdes = match.get("npdes_id") if match else None

    # 1. ECHO carries a cited receiving water -> connector-grounded.
    if match and match.get("receiving_water"):
        return (
            match["receiving_water"],
            "connector",
            f"EPA ECHO {match.get('npdes_id')} — {match['receiving_water']}",
            npdes,
        )

    # 2. The site's industrial receiving-water corridor -> coordinate-cluster inference.
    prof = active_profile(settings)
    bbox = prof.toxic_corridor_bbox
    if _in_corridor(fac.latitude, fac.longitude, bbox):
        return (
            prof.receiving_water_name,
            "assumption",
            (
                f"within the {prof.receiving_water_name} industrial corridor at {prof.place} "
                f"(coordinate cluster {bbox[0]}-{bbox[1]}N, {abs(bbox[3])}-{abs(bbox[2])}W); "
                "receiving water not independently cited"
            ),
            npdes,
        )

    # 3. unresolved.
    return None, None, None, npdes


def _annual_water_pounds(fac: RseiFacility) -> float:
    """Cumulative water pounds annualized over the years the facility actually reported.

    `fac.pounds_by_media["water"]` is the cumulative total across `fac.years` only, so
    the divisor is the *count of reporting years*, never the calendar interval spanned.
    An intermittent reporter (e.g. 1988 and 2022, nothing between) has a 2-year total,
    not a 35-year one; dividing by the span would understate the annual load by the gap
    ratio and drag the screening mg/L below its threshold. Feeds the aggregate context
    `screening_concentration`; the per-chemical screen annualizes each chemical the same way
    over its own water reporting years (`RseiWaterChemical.reporting_years`).
    """
    water_lbs = (fac.pounds_by_media or {}).get("water", 0.0)
    reporting_years = len(fac.years) or 1
    return water_lbs / reporting_years


def _screening_concentration(annual_lbs: float, q7: ProvenancedValue) -> ProvenancedValue | None:
    """mg/L if the annual reported water pounds entered the reach at its 7Q10 (screen-only)."""
    mgd = units.cfs_to_mgd(q7.value)
    if mgd <= 0 or annual_lbs <= 0:
        return None
    conc = (annual_lbs / 365.0) / (mgd * _LBS_PER_MGL_MGD)
    return ProvenancedValue.derived(
        round(conc, 3),
        "mg/L",
        citation=(
            f"{annual_lbs:,.0f} lb/yr reported to water / 365 d, fully mixed at the "
            f"{q7.value:g} cfs 7Q10 — screening order-of-magnitude only "
            "(assumes all water releases reach this reach; no decay/mixing zone)"
        ),
        confidence="low",
    )


# Per-criterion exceedance bands on the ratio (derived concentration / Ohio criterion). A
# ratio >= 1 exceeds the criterion; >= 0.1 approaches it (an order of magnitude below). These
# are ratios against a *chemical-specific* regulatory criterion, not the old arbitrary mg/L band.
_EXCEEDANCE = 1.0
_APPROACH = 0.1

# criterion_type -> (context-block flow key, human label). Chronic uses the top-level 7Q10.
_FLOW_LABEL = {"acute": "1Q10", "chronic": "7Q10", "human_health": "harmonic mean"}
_CONTEXT_FLOW_KEY = {"acute": "one_q10_cfs", "human_health": "harmonic_mean_cfs"}
# Worst-first ordering for rolling per-criterion flags up to a chemical / facility flag.
_FLAG_RANK = {"exceedance": 0, "approach": 1, "ok": 2, "no_criterion": 3}


def _criterion_flag(ratio: float | None) -> str:
    """Band a (derived concentration / criterion) ratio: exceedance / approach / ok."""
    if ratio is None:
        return "ok"
    if ratio >= _EXCEEDANCE:
        return "exceedance"
    if ratio >= _APPROACH:
        return "approach"
    return "ok"


def _worst(flags: list[str]) -> str:
    """The most severe flag in a list (exceedance > approach > ok > no_criterion)."""
    return min(flags, key=lambda f: _FLAG_RANK.get(f, 9)) if flags else "no_criterion"


def _design_flows(
    q7: ProvenancedValue | None, ctx: dict[str, Any]
) -> dict[str, ProvenancedValue | None]:
    """Resolve the three regulatory design flows for a reach (acute/chronic/human-health).

    Chronic is the cited top-level 7Q10; acute (1Q10) and human-health (harmonic mean) are read
    from the reach's ``context`` block, cited to the same fact sheet. A flow absent from the
    committed table stays ``None`` (its criterion type is then not screened — omit, don't guess).
    """
    flows: dict[str, ProvenancedValue | None] = {"chronic": q7}
    for ctype, key in _CONTEXT_FLOW_KEY.items():
        raw = ctx.get(key)
        if raw is None:
            flows[ctype] = None
            continue
        cite = (
            f"{_FLOW_LABEL[ctype]} — {q7.citation}"
            if q7 and q7.citation
            else f"{_FLOW_LABEL[ctype]} design flow"
        )
        flows[ctype] = ProvenancedValue.from_document(
            float(raw), "cfs", cite, confidence=(q7.confidence if q7 else "high")
        )
    return flows


def _criterion_pv(crit: WaterQualityCriterion, ctype: str, value: float) -> ProvenancedValue:
    """The Ohio criterion as a `reference` ProvenancedValue (cite the OAC rule/table)."""
    basis = {
        "acute": crit.basis_acute,
        "chronic": crit.basis_chronic,
        "human_health": crit.basis_human_health,
    }.get(ctype) or "Ohio WQS (OAC 3745-1)"
    return ProvenancedValue.from_reference(value, "mg/L", basis, confidence="high")


def _criterion_screen(
    ctype: str, flow: ProvenancedValue, criterion: ProvenancedValue, annual_lbs: float
) -> CriterionScreen:
    """Screen one chemical's annual water load against one criterion at its design flow."""
    load_lb_day = annual_lbs / 365.0
    if flow.value <= 0.0:
        # No assimilative capacity (the Ottawa 1Q10 = 0). Any load exceeds; no Inf concentration.
        return CriterionScreen(
            criterion_type=ctype,
            design_flow=flow,
            criterion=criterion,
            reported_load_lb_day=round(load_lb_day, 4),
            loading_capacity_lb_day=0.0,
            derived_concentration=None,
            exceedance_factor=None,
            flag="exceedance",
            note=(
                f"{_FLOW_LABEL[ctype]} = 0 cfs: no assimilative capacity at design low flow — "
                "any load exceeds the criterion by construction"
            ),
        )
    mgd = units.cfs_to_mgd(flow.value)
    conc = load_lb_day / (mgd * _LBS_PER_MGL_MGD)
    loading_capacity = criterion.value * mgd * _LBS_PER_MGL_MGD
    ratio = conc / criterion.value if criterion.value else None
    conc_pv = ProvenancedValue.derived(
        round(conc, 4),
        "mg/L",
        citation=(
            f"{annual_lbs:,.0f} lb/yr to water / 365 d, fully mixed at the {flow.value:g} cfs "
            f"{_FLOW_LABEL[ctype]} — screening order-of-magnitude only (no decay/mixing zone)"
        ),
        confidence="low",
    )
    return CriterionScreen(
        criterion_type=ctype,
        design_flow=flow,
        criterion=criterion,
        reported_load_lb_day=round(load_lb_day, 4),
        loading_capacity_lb_day=round(loading_capacity, 4),
        derived_concentration=conc_pv,
        exceedance_factor=round(ratio, 3) if ratio is not None else None,
        flag=_criterion_flag(ratio),
    )


def _screen_chemical(
    wc: RseiWaterChemical, flows: dict[str, ProvenancedValue | None], crit: WaterQualityCriterion
) -> ChemicalScreen:
    """Screen one water chemical against every applicable Ohio criterion type."""
    annual = wc.water_pounds / (wc.reporting_years or 1)
    crit_values = {
        "acute": crit.acute_cmc_mg_l,
        "chronic": crit.chronic_ccc_mg_l,
        "human_health": crit.human_health_mg_l,
    }
    screens: list[CriterionScreen] = []
    for ctype in ("acute", "chronic", "human_health"):
        value, flow = crit_values[ctype], flows.get(ctype)
        if value is None or flow is None:
            continue  # no committed criterion of this type, or no cited design flow
        screens.append(_criterion_screen(ctype, flow, _criterion_pv(crit, ctype, value), annual))
    return ChemicalScreen(
        chemical=wc.chemical,
        cas=wc.cas,
        annual_water_pounds=round(annual, 1),
        reporting_years=wc.reporting_years,
        criteria=screens,
        flag=_worst([s.flag for s in screens]),
    )


def _facility_flag(chem_screens: list[ChemicalScreen], receiving: str | None) -> str:
    """Roll per-chemical exceedances up to the facility flag (preserving the screen vocab).

    ``critical`` requires a *computed* aquatic-life exceedance — a chronic (7Q10) or a
    nonzero-flow acute exceedance with a real ``exceedance_factor``. The Ottawa's 1Q10 = 0
    degenerate acute exceedance (any load "exceeds" a zero-capacity stream) is surfaced honestly
    but on its own only yields ``elevated`` — otherwise every trace corridor discharger (e.g. 5
    lb of chromium over the record) would read ``critical``, which is alarmist and rebuttable.
    """
    if receiving is None:
        return "uncharacterized"
    cs = [c for chem in chem_screens for c in chem.criteria]
    aquatic = {"acute", "chronic"}
    if any(
        c.criterion_type in aquatic and c.flag == "exceedance" and c.exceedance_factor is not None
        for c in cs
    ):
        return "critical"
    degenerate_acute = any(
        c.criterion_type == "acute" and c.flag == "exceedance" and c.exceedance_factor is None
        for c in cs
    )
    if (
        degenerate_acute
        or any(c.criterion_type in aquatic and c.flag == "approach" for c in cs)
        or any(c.criterion_type == "human_health" and c.flag == "exceedance" for c in cs)
    ):
        return "elevated"
    return "context"


def _screen_water_chemicals(
    fac: RseiFacility, flows: dict[str, ProvenancedValue | None], table: CriteriaTable
) -> list[ChemicalScreen]:
    """Every water chemical of a facility, screened (or reported ``no_criterion``)."""
    out: list[ChemicalScreen] = []
    for wc in fac.top_water_chemicals:
        crit = table.match(wc.cas)
        if crit is None:
            out.append(
                ChemicalScreen(
                    chemical=wc.chemical,
                    cas=wc.cas,
                    annual_water_pounds=round(wc.water_pounds / (wc.reporting_years or 1), 1),
                    reporting_years=wc.reporting_years,
                    criteria=[],
                    flag="no_criterion",
                )
            )
        else:
            out.append(_screen_chemical(wc, flows, crit))
    return out


# --- Build -----------------------------------------------------------------
def _load_echo(settings: Settings) -> list[dict[str, Any]]:
    """Load the committed ECHO Maumee NPDES inventory rows (or [] if absent)."""
    path = settings.reference_dir / "echo" / "maumee-wwtp.all-npdes.yaml"
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(data.get("facilities") or [])


def _low_flow_context(settings: Settings) -> dict[str, dict[str, Any]]:
    """Read the per-stream `context` blocks (1Q10, summer 30Q10) from the 7Q10 table."""
    path = settings.reference_dir / "hydrology" / "low-flow-7q10.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, dict[str, Any]] = {}
    for name, entry in (data.get("streams") or {}).items():
        if isinstance(entry, dict):
            out[_normalize(str(name))] = dict(entry.get("context") or {})
    return out


def _water_releasers(facilities: list[RseiFacility]) -> list[RseiFacility]:
    return [
        f
        for f in facilities
        if f.water_releases or (f.pounds_by_media or {}).get("water", 0.0) > 0.0
    ]


def worst_exceedances(
    chem_screens: list[ChemicalScreen], k: int = 3
) -> list[tuple[float, str, str]]:
    """The k worst per-chemical exceedances (factor, chemical, criterion type), one per chemical.

    One entry per chemical, using its largest *computed* exceedance factor (chronic/nonzero-flow
    acute) — the discriminating magnitude. A chemical whose only exceedance is the degenerate
    1Q10 = 0 acute case (factor ``inf``) is included but ranked after all computed ones, so the
    detail leads with quantified severity. Used by the detail line, the CLI, and the map tooltip.
    """
    per_chem: list[tuple[float, str, str]] = []
    for cs in chem_screens:
        exc = [c for c in cs.criteria if c.flag == "exceedance"]
        if not exc:
            continue
        finite = [c for c in exc if c.exceedance_factor is not None]
        if finite:
            best = max(finite, key=lambda c: c.exceedance_factor or 0.0)
            per_chem.append((best.exceedance_factor or 0.0, cs.chemical, best.criterion_type))
        else:  # only the degenerate 1Q10 = 0 acute exceedance
            per_chem.append((float("inf"), cs.chemical, exc[0].criterion_type))
    # Computed (finite) factors first, descending; the inf (zero-capacity) entries trail.
    per_chem.sort(key=lambda t: (t[0] == float("inf"), -t[0] if t[0] != float("inf") else 0.0))
    return per_chem[:k]


def format_factor(ef: float) -> str:
    """Human exceedance factor: ``∞`` for zero-capacity, 1 decimal under 10x, integer above."""
    if ef == float("inf"):
        return "∞"
    if ef >= 10.0:
        return f"{ef:,.0f}x"
    return f"{ef:.1f}x"


def _facility_detail(
    fac: RseiFacility,
    water: str | None,
    src: SourceKind | None,
    chem_screens: list[ChemicalScreen],
    flag: str,
) -> str:
    """A per-chemical summary line naming the worst criterion exceedances."""
    if water is None:
        return f"{fac.name}: water releaser with no cited/inferred receiving water."
    tag = "inferred" if src == "assumption" else "cited"
    n_water = len(chem_screens)
    n_screened = sum(1 for cs in chem_screens if cs.criteria)
    worst = worst_exceedances(chem_screens)
    if worst:
        parts = "; ".join(
            f"{_short_chem(chem)} ({ctype} {format_factor(ef)})" for ef, chem, ctype in worst
        )
        return (
            f"{fac.name}: {n_screened}/{n_water} water chemicals vs Ohio criteria on {water} "
            f"({tag}) — {parts} [{flag}]."
        )
    return (
        f"{fac.name}: {n_screened}/{n_water} water chemicals screened on {water} "
        f"({tag}) — no criterion exceedance [{flag}]."
    )


def _short_chem(name: str) -> str:
    """Trim RSEI's long parenthetical chemical names for a readable detail line."""
    return name.split(" (")[0].strip()


def build_screen(settings: Settings | None = None) -> ToxicDischargeInventory:
    """Screen every RSEI water-releasing facility, per chemical, against its Ohio criteria.

    Each facility's per-chemical *water* load is carried at its receiving reach's design flows
    (7Q10 chronic / 1Q10 acute / harmonic-mean human-health) and read against the chemical's own
    Ohio WQS criterion (:mod:`watermark.hydrology.criteria`). The facility flag rolls the
    per-chemical exceedances up (``critical`` = an acute/chronic exceedance).
    """
    settings = settings or get_settings()
    inv = load_inventory(settings)
    if inv is None:
        raise FileNotFoundError(
            "RSEI inventory not found — run `watermark rsei` first (data/reference/rsei/inventory.yaml)."
        )
    echo = _load_echo(settings)
    low_flows = load_low_flows(settings=settings)
    context = _low_flow_context(settings)
    table = criteria.load_criteria(settings=settings)

    screens: list[ToxicDischargeScreen] = []
    for fac in _water_releasers(inv.facilities):
        water_lbs = (fac.pounds_by_media or {}).get("water", 0.0)
        annual_lbs = _annual_water_pounds(fac)
        top_water_chem = fac.top_water_chemicals[0].chemical if fac.top_water_chemicals else None

        water, src, cite, npdes = _resolve_receiving_water(fac, echo, settings=settings)
        q7 = low_flows.get(_normalize(water)) if water else None
        conc = _screening_concentration(annual_lbs, q7) if q7 else None

        if water is None:
            chem_screens: list[ChemicalScreen] = []
        else:
            flows = _design_flows(q7, context.get(_normalize(water), {}))
            chem_screens = _screen_water_chemicals(fac, flows, table)
        flag = _facility_flag(chem_screens, water)
        detail = _facility_detail(fac, water, src, chem_screens, flag)

        screens.append(
            ToxicDischargeScreen(
                facility=fac.name,
                rsei_facility_id=fac.facility_id,
                latitude=fac.latitude,
                longitude=fac.longitude,
                score=fac.score,
                cancer_score=fac.cancer_score,
                water_pounds=round(water_lbs, 1),
                annual_water_pounds=round(annual_lbs, 1),
                year_span=(f"{fac.first_year}-{fac.last_year}" if fac.first_year else None),
                top_water_chemical=top_water_chem,
                npdes_id=npdes,
                receiving_water=water,
                receiving_water_source=src,
                receiving_water_citation=cite,
                low_flow_7q10=q7,
                screening_concentration=conc,
                chemical_screens=chem_screens,
                flag=flag,
                detail=detail,
            )
        )

    # Rank: critical/elevated first, then by RSEI Score.
    order = {"critical": 0, "elevated": 1, "context": 2, "uncharacterized": 3}
    screens.sort(key=lambda s: (order.get(s.flag, 9), -s.score))

    # A *computed* aquatic-life exceedance (chronic, or nonzero-flow acute) — the discriminating
    # count, excluding the degenerate 1Q10 = 0 acute case (which alone only lifts to `elevated`).
    exceeding_chemicals = sum(
        1
        for s in screens
        for cs in s.chemical_screens
        if any(
            c.criterion_type in ("acute", "chronic")
            and c.flag == "exceedance"
            and c.exceedance_factor is not None
            for c in cs.criteria
        )
    )
    assumptions = table.assumptions
    meta = {
        "subject": "Industrial toxic water dischargers vs chemical-specific Ohio WQS criteria",
        "source": (
            "EPA RSEI (per-chemical water-media releases) x EPA ECHO (receiving water) x "
            "Ohio EPA cited design low flows (data/reference/hydrology/low-flow-7q10.yaml) x "
            "Ohio WQS criteria (data/reference/wqs/ohio-water-quality-criteria.yaml)"
        ),
        "criteria_source": str(table.source.get("document", "OAC 3745-1")),
        "county_fips": inv.county_fips,
        "county_name": inv.county_name,
        "water_releaser_count": len(screens),
        "critical_count": sum(1 for s in screens if s.flag == "critical"),
        "exceeding_chemical_count": exceeding_chemicals,
        "design_flows": {
            "acute_cmc": "1Q10",
            "chronic_ccc": "7Q10",
            "human_health": "harmonic mean",
        },
        "hardness_assumption_mg_l": assumptions.get("hardness_mg_l_caco3"),
        "ammonia_condition": (
            f"pH {assumptions.get('ammonia_ph')}, {assumptions.get('ammonia_temp_c')} C, "
            f"{assumptions.get('ammonia_season')}"
        ),
        "caveats": [
            "Each water chemical's derived concentration is screened against its OWN Ohio "
            "criterion (acute CMC at 1Q10, chronic CCC at 7Q10, human health at harmonic mean) "
            "— not a flat aggregate band. A chemical with no committed Ohio criterion is "
            "reported 'no_criterion' (omitted, never guessed).",
            "Receiving water is ECHO-cited where available, else inferred from the Ottawa River "
            "industrial corridor coordinate cluster (tagged assumption).",
            "Derived concentrations are order-of-magnitude: annual reported water pounds, fully "
            "mixed at the design flow, no decay or mixing-zone credit — a screen, not a permit "
            "wasteload allocation. Exceedance flags the need for a WQBEL determination.",
            "Metals criteria are evaluated at a stated reference hardness (100 mg/L CaCO3); "
            "ammonia at a stated pH/temperature; chromium screened conservatively as Cr(VI). "
            "See data/reference/wqs/ for the re-derivable assumptions.",
            "RSEI Score is EPA's modeled, population-weighted Risk-Screening Score (unitless, "
            "comparative only); the aggregate screening_concentration is coarse context only.",
        ],
    }
    return ToxicDischargeInventory(meta=meta, screens=screens)


# --- Persistence -----------------------------------------------------------
def write_screen(inv: ToxicDischargeInventory, out_dir: Path) -> Path:
    """Write the screen to ``<out_dir>/toxic-discharge-screen.yaml``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "toxic-discharge-screen.yaml"
    path.write_text(
        yaml.safe_dump(inv.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def load_screen(reference_dir: Path) -> ToxicDischargeInventory | None:
    """Load the committed screen, or None if it hasn't been generated."""
    path = reference_dir / "rsei" / "toxic-discharge-screen.yaml"
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ToxicDischargeInventory(**data)
