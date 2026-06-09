"""Tier-1 SWMM escalation: detention sizing + sanitary wet-weather surcharge.

Runs the real EPA SWMM5 engine on the campus footprint under the design storm to
answer two questions Tier-0 only approximated:

* **Detention sizing** — bisect the basin's bottom-orifice diameter until the
  released post-development peak matches the pre-development peak (the regulatory
  "no net increase" rule); report the storage volume that requires.
* **Sanitary surcharge** — the storm-driven wet-weather peak (dry-weather base +
  RDII) versus each plant's documented peak hydraulic capacity.

Everything degrades gracefully if the SWMM engine is unavailable.

The engine is version-dependent and may be absent (no pyswmm wheel, or macOS killing
an ad-hoc-signed bundle). So a successful live run is **committed**: the four input
decks land as ``.inp`` files under ``data/reference/hydrology/swmm/`` (chain of
custody — anyone can re-run them in EPA SWMM) and the reviewed result as
``tier1-swmm.yaml``. :func:`load_tier1` reads that committed artifact so the dossier
and tests show real SWMM numbers offline, without the engine; :func:`run_tier1`
regenerates it (``bosc tier1 --write``).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from bosc.config import Settings, get_settings
from bosc.hydrology.model import (
    DetentionDesign,
    HydroFinding,
    ProvenancedValue,
    SanitaryBasis,
    SanitarySurcharge,
    SwmmDeck,
    Tier1Result,
)
from bosc.hydrology.stormwater import _parcels_path
from bosc.hydrology.swmm import engine, inp
from bosc.hydrology.units import cfs_to_mgd
from bosc.logging import get_logger

log = get_logger(__name__)

# Land-cover imperviousness (assumptions): cropland vs near-impervious campus.
_PRE_IMPERV = 5.0
_POST_IMPERV = 90.0
# Detention basin footprint as a fraction of the campus, and max depth (assumptions).
_BASIN_FRAC = 0.04
_BASIN_DEPTH_FT = 12.0
# RDII fraction of rainfall entering the new sanitary system as inflow/infiltration.
_RDII_R = 0.05

_SWMM_SUBDIR = "swmm"
_FILENAME = "tier1-swmm.yaml"

# Forcemain + receiver labels for the campus sanitary routing (routing.yaml).
_FM = {"bosc-fm1": "FM-1", "bosc-fm2": "FM-2"}
_RECEIVER_NAMES = {
    "watch-lima-fm2-terminus": "City of Lima WWTP",
    "watch-american-bath-wwtp": "American Bath WWTP",
    "watch-american-ii-wwtp": "American II WWTP",
}

# Fallback peak hydraulic capacity, used only if the cited sanitary basis is absent.
# Shawnee II is deliberately NOT here: it receives no campus flow (FM-3 is theorized
# and excluded — routing.yaml). American II is the FM-1 receiver with a cited capacity.
_PLANT_CAPACITY: list[tuple[str, float, str, str]] = [
    (
        "American II WWTP",
        3.6,
        "FM-1",
        "Ohio EPA fact sheet 2PH00006: peak hydraulic capacity 3.6 MGD",
    ),
]


def _forcemain_label(via: str | None) -> str | None:
    return _FM.get(via or "", via)


def _design_depth_in(settings: Settings, *, return_period_yr: int, live: bool) -> float:
    from bosc.hydrology.stormwater import _resolve_storm

    return _resolve_storm(return_period_yr, settings=settings, live=live).depth.value


def _size_detention(
    area: float, depth: float, pre_peak: float
) -> tuple[float, float, float, str, float, str, str]:
    """Bisect orifice diameter so the released peak ~= pre peak.

    Returns ``(diam, release, storage, inp_text, continuity_pct, outfall, storage_node)``
    for the *final* sized deck (rebuilt once after the search so the committed deck is
    internally consistent with the reported numbers).
    """
    basin_area = area * 43560.0 * _BASIN_FRAC
    lo, hi = 0.25, 12.0
    diam = hi
    for _ in range(10):
        diam = 0.5 * (lo + hi)
        det = inp.DetentionGeom(basin_area, _BASIN_DEPTH_FT, diam)
        text, outfall, _orifice, sto = inp.stormwater_inp(
            area_acres=area, pct_imperv=_POST_IMPERV, depth_in=depth, detention=det
        )
        res = engine.simulate(text, nodes=[outfall], storages=[sto])
        release = res.node_peak_cfs.get(outfall, 0.0)
        if release > pre_peak:  # too much release -> smaller orifice
            hi = diam
        else:
            lo = diam

    # Rebuild + run the final deck so the committed .inp matches the reported numbers.
    det = inp.DetentionGeom(basin_area, _BASIN_DEPTH_FT, diam)
    text, outfall, _orifice, sto = inp.stormwater_inp(
        area_acres=area, pct_imperv=_POST_IMPERV, depth_in=depth, detention=det
    )
    res = engine.simulate(text, nodes=[outfall], storages=[sto])
    release = res.node_peak_cfs.get(outfall, 0.0)
    storage = res.storage_peak_acft.get(sto, 0.0)
    return diam, release, storage, text, res.continuity_error_pct, outfall, sto


def _build_surcharge(
    basis: SanitaryBasis | None,
    wet_peak_mgd: float,
    wet_pv: ProvenancedValue,
    *,
    receivers: dict[str, str],
) -> list[SanitarySurcharge]:
    """Judge the campus wet-weather contribution against each *receiving* plant's headroom.

    Only plants that actually receive campus flow (``routing_id`` in ``receivers``, the
    confirmed FM-1/FM-2 destinations from ``routing.yaml``) are judged — so Shawnee II,
    which has no campus routing, is no longer compared. The comparison is the campus
    contribution vs *wet-weather headroom* (peak hydraulic capacity - permitted average).
    Without a cited basis, fall back to the documented FM-1 receiver only.
    """
    if basis is None:
        return [
            SanitarySurcharge(
                plant=name,
                forcemain=fm,
                capacity=ProvenancedValue.from_document(cap, "MGD", citation=cite),
                wet_weather_peak=wet_pv,
                exceeds=wet_peak_mgd > cap,
                margin_mgd=round(cap - wet_peak_mgd, 2),
            )
            for name, cap, fm, cite in _PLANT_CAPACITY
        ]
    out: list[SanitarySurcharge] = []
    for p in basis.plants:
        if p.routing_id not in receivers:
            continue  # not a campus receiver -> not part of the surcharge
        headroom = p.headroom_mgd
        if p.peak_capacity is None or headroom is None:
            continue  # a receiver, but no cited peak capacity (surfaced in the surcharge note)
        out.append(
            SanitarySurcharge(
                plant=p.plant,
                forcemain=_forcemain_label(receivers.get(p.routing_id)),
                capacity=p.peak_capacity,
                avg_design_flow=p.avg_design_flow,
                peaking_factor=p.peaking_factor,
                headroom_mgd=headroom,
                wet_weather_peak=wet_pv,
                exceeds=wet_peak_mgd > headroom,
                margin_mgd=round(headroom - wet_peak_mgd, 2),
            )
        )
    return out


def _surcharge_note(basis: SanitaryBasis | None, receivers: dict[str, str]) -> str:
    """Auditable record of where the campus flow goes and who is / isn't judged.

    Keeps the omission honest: Shawnee II is excluded because it receives no campus
    flow, and the receivers we can't quantify (no cited peak hydraulic capacity) are
    named rather than silently dropped.
    """
    if basis is None or not receivers:
        return ""
    by_fm: dict[str, list[str]] = {}
    for node_id, via in receivers.items():
        by_fm.setdefault(_FM.get(via, via or "?"), []).append(_RECEIVER_NAMES.get(node_id, node_id))
    split = "; ".join(f"{fm} → {' + '.join(sorted(rs))}" for fm, rs in sorted(by_fm.items()))

    cited = {p.routing_id for p in basis.plants if p.peak_capacity is not None and p.routing_id}
    uncited = sorted(_RECEIVER_NAMES.get(n, n) for n in receivers if n not in cited)
    excluded = sorted(
        p.plant for p in basis.plants if p.routing_id and p.routing_id not in receivers
    )

    parts = [f"Campus sanitary routing: {split}."]
    if uncited:
        parts.append(
            "Receives campus flow but peak hydraulic capacity not cited (campus share not "
            f"quantified): {', '.join(uncited)}."
        )
    if excluded:
        parts.append(f"Excluded — no campus routing (FM-3 theorized): {', '.join(excluded)}.")
    return " ".join(parts)


def _deck(
    name: str, text: str, *, node: str, peak: float, continuity: float, note: str
) -> SwmmDeck:
    return SwmmDeck(
        name=name,
        filename=f"{_SWMM_SUBDIR}/tier1-{name}.inp",
        reports_node=node,
        peak_cfs=round(peak, 2),
        continuity_error_pct=round(continuity, 3),
        note=note,
        inp_text=text,
    )


def run_tier1(
    *,
    return_period_yr: int = 25,
    settings: Settings | None = None,
    live: bool = True,
) -> Tier1Result:
    """Run the SWMM detention-sizing + sanitary-surcharge analyses (engine required)."""
    settings = settings or get_settings()
    if not engine.swmm_available():
        return Tier1Result(available=False, note="SWMM engine unavailable (pyswmm did not load)")

    from bosc.hydrology import geo

    area = geo.parcels_total_acres(_parcels_path(settings), settings=settings)
    depth = _design_depth_in(settings, return_period_yr=return_period_yr, live=live)
    decks: list[SwmmDeck] = []

    # --- Stormwater detention sizing ---
    pre_text, pre_out, _o, _s = inp.stormwater_inp(
        area_acres=area, pct_imperv=_PRE_IMPERV, depth_in=depth
    )
    pre_res = engine.simulate(pre_text, nodes=[pre_out])
    pre_peak = pre_res.node_peak_cfs.get(pre_out, 0.0)
    decks.append(
        _deck(
            "pre",
            pre_text,
            node=pre_out,
            peak=pre_peak,
            continuity=pre_res.continuity_error_pct,
            note="pre-development (cropland) stormwater",
        )
    )

    post_text, post_out, _o, _s = inp.stormwater_inp(
        area_acres=area, pct_imperv=_POST_IMPERV, depth_in=depth
    )
    post_res = engine.simulate(post_text, nodes=[post_out])
    post_peak = post_res.node_peak_cfs.get(post_out, 0.0)
    decks.append(
        _deck(
            "post",
            post_text,
            node=post_out,
            peak=post_peak,
            continuity=post_res.continuity_error_pct,
            note="post-development (impervious), undetained",
        )
    )

    diam, controlled, storage, det_text, det_cont, det_out, _sto = _size_detention(
        area, depth, pre_peak
    )
    decks.append(
        _deck(
            "detention",
            det_text,
            node=det_out,
            peak=controlled,
            continuity=det_cont,
            note=f"post-development with sized basin (bottom orifice {diam:.2f} ft)",
        )
    )
    detention = DetentionDesign(
        pre_peak_cfs=round(pre_peak, 1),
        post_peak_cfs=round(post_peak, 1),
        controlled_peak_cfs=round(controlled, 1),
        orifice_diam_ft=round(diam, 2),
        required_storage_acft=round(storage, 1),
        basin_area_acres=round(area * _BASIN_FRAC, 1),
    )

    # --- Sanitary wet-weather surcharge ---
    # The campus dry-weather base is the documented FM-2 industrial discharge (cited via
    # the sanitary basis); RDII over the sewershed remains an assumption (no calibrated R).
    # The surcharge is judged only against plants that actually receive campus flow per
    # the routing table (FM-1 -> American Bath + American II; FM-2 -> Lima), not Shawnee II.
    from bosc.hydrology.routing import load_routing
    from bosc.hydrology.sanitary import load_sanitary_basis

    basis = load_sanitary_basis(settings=settings)
    routing = load_routing(settings=settings)
    receivers = routing.campus_receivers() if routing is not None else {}
    campus_base = basis.campus_industrial.value if basis is not None else 2.5
    san_text, wwtp = inp.sanitary_inp(
        base_mgd=campus_base, sewershed_acres=area, rdii_r=_RDII_R, depth_in=depth
    )
    san_res = engine.simulate(san_text, nodes=[wwtp])
    wet_peak_cfs = san_res.node_peak_cfs.get(wwtp, 0.0)
    wet_peak_mgd = cfs_to_mgd(wet_peak_cfs)
    decks.append(
        _deck(
            "sanitary",
            san_text,
            node=wwtp,
            peak=wet_peak_cfs,
            continuity=san_res.continuity_error_pct,
            note="DWF + RDII sanitary wet-weather",
        )
    )
    wet_pv = ProvenancedValue.derived(
        round(wet_peak_mgd, 2),
        "MGD",
        citation=(
            f"SWMM RDII (R={_RDII_R}, assumption) over {area:.0f} ac + {campus_base:g} MGD "
            f"campus dry base (FM-2, document), {return_period_yr}-yr storm"
        ),
    )
    surcharge = _build_surcharge(basis, wet_peak_mgd, wet_pv, receivers=receivers)
    surcharge_note = _surcharge_note(basis, receivers)

    # Ground the detention result in the real 95% SPS drainage design, if extracted.
    from bosc.hydrology.stormplan import load_inventory

    inventory = load_inventory(settings=settings)

    log.info(
        "hydro.tier1",
        pre_peak=detention.pre_peak_cfs,
        post_peak=detention.post_peak_cfs,
        storage_acft=detention.required_storage_acft,
        wet_peak_mgd=round(wet_peak_mgd, 1),
    )
    return Tier1Result(
        available=True,
        detention=detention,
        surcharge=surcharge,
        surcharge_note=surcharge_note,
        decks=decks,
        engine=engine.engine_version(),
        storm_return_period_yr=return_period_yr,
        design_depth_in=round(depth, 2),
        inventory=inventory,
        sanitary_basis=basis,
    )


# ------------------------------------------------------------------- persistence


def _reference_dir(settings: Settings) -> Path:
    return settings.data_dir / "reference" / "hydrology"


def write_tier1(result: Tier1Result, *, settings: Settings | None = None) -> Path:
    """Commit a live Tier-1 result: write the ``.inp`` decks + the reviewed YAML.

    The decks (the model inputs) land as files with their sha256 recorded, so the
    result is reproducible. The grounding (inventory / sanitary basis) is *not*
    re-embedded — it is already committed under its own reference files and re-attached
    by :func:`load_tier1`.
    """
    settings = settings or get_settings()
    ref = _reference_dir(settings)
    for deck in result.decks:
        path = ref / deck.filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(deck.inp_text, encoding="utf-8")
        deck.sha256 = hashlib.sha256(deck.inp_text.encode("utf-8")).hexdigest()

    persist = result.model_copy(update={"inventory": None, "sanitary_basis": None})
    doc = {
        "meta": {
            "subject": "Tier-1 EPA SWMM — detention sizing + sanitary wet-weather surcharge",
            "engine": result.engine,
            "storm": f"{result.storm_return_period_yr}-yr 24-hr, {result.design_depth_in} in",
            "discipline": (
                "SWMM-computed (derived). Footprint + storm + plant design flows are "
                "document/connector-sourced; imperviousness, RDII R, and basin geometry are "
                "assumptions. The .inp decks are committed for chain of custody."
            ),
        },
        "tier1": persist.model_dump(mode="json"),
    }
    out = ref / _FILENAME
    out.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100), "utf-8")
    log.info("hydro.tier1.wrote", path=str(out), decks=len(result.decks))
    return out


def load_tier1(*, settings: Settings | None = None) -> Tier1Result | None:
    """Load the committed Tier-1 result (engine-free), re-attaching its cited grounding.

    Each deck's committed ``.inp`` text is read back into ``inp_text`` so callers can
    verify the sha256 and inspect the model; the inventory + sanitary basis are loaded
    fresh from their own reference files.
    """
    settings = settings or get_settings()
    ref = _reference_dir(settings)
    path = ref / _FILENAME
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    block = data.get("tier1")
    if not block:
        return None
    result = Tier1Result.model_validate(block)

    for deck in result.decks:
        deck_path = ref / deck.filename
        if deck_path.is_file():
            deck.inp_text = deck_path.read_text(encoding="utf-8")

    from bosc.hydrology.sanitary import load_sanitary_basis
    from bosc.hydrology.stormplan import load_inventory

    result.inventory = load_inventory(settings=settings)
    result.sanitary_basis = load_sanitary_basis(settings=settings)
    return result


def deck_checksum_mismatches(result: Tier1Result) -> list[str]:
    """Deck names whose committed ``.inp`` text no longer matches the recorded sha256."""
    out: list[str] = []
    for deck in result.decks:
        if not deck.inp_text:
            continue
        actual = hashlib.sha256(deck.inp_text.encode("utf-8")).hexdigest()
        if deck.sha256 and actual != deck.sha256:
            out.append(deck.name)
    return out


def tier1_findings(result: Tier1Result) -> list[HydroFinding]:
    """Render the Tier-1 result as findings."""
    if not result.available:
        return [HydroFinding("SWMM", "engine", False, result.note)]
    findings: list[HydroFinding] = []

    # Lead with the document-grounded drainage facts when the sheet has been extracted.
    if result.inventory is not None:
        from bosc.hydrology.stormplan import storm_plan_findings

        findings.extend(storm_plan_findings(result.inventory))

    d = result.detention
    if d is not None:
        # When the real 95% design shows no on-site storage, the SWMM-sized basin is the
        # *absent* control — say so, citing the sheet, rather than implying a redesign.
        absent = result.inventory is not None and not result.inventory.detention_shown
        frame = (
            f"the {result.inventory.phase} ({result.inventory.sheet_id}) provides no "
            f"on-site detention, so SWMM sizes the absent control: "
            if absent and result.inventory is not None
            else "SWMM: "
        )
        findings.append(
            HydroFinding(
                "BOSC campus",
                "detention-sizing",
                not absent,  # an absent required control is a gap, not an OK
                f"{frame}post-dev peak {d.post_peak_cfs:.0f} cfs vs pre-dev {d.pre_peak_cfs:.0f} cfs; "
                f"a {d.required_storage_acft:.0f} ac-ft basin (orifice {d.orifice_diam_ft:.1f} ft) "
                f"holds release to {d.controlled_peak_cfs:.0f} cfs",
            )
        )
    for s in result.surcharge:
        if s.headroom_mgd is not None and s.avg_design_flow is not None:
            pf = f", {s.peaking_factor.value:g}x peaking" if s.peaking_factor else ""
            detail = (
                f"campus wet-weather contribution {s.wet_weather_peak.value:.1f} MGD vs "
                f"{s.headroom_mgd:g} MGD wet-weather headroom "
                f"(peak {s.capacity.value:g} - avg {s.avg_design_flow.value:g} MGD{pf}, document) "
                f"({'EXCEEDS' if s.exceeds else 'within'}, margin {s.margin_mgd:+.1f} MGD)"
            )
        else:
            detail = (
                f"storm wet-weather peak {s.wet_weather_peak.value:.1f} MGD vs peak capacity "
                f"{s.capacity.value:g} MGD ({'EXCEEDS' if s.exceeds else 'within'}, "
                f"margin {s.margin_mgd:+.1f} MGD)"
            )
        findings.append(HydroFinding(s.plant, "wet-weather-surcharge", not s.exceeds, detail))

    # Make the routing auditable: which plants receive campus flow, which were excluded.
    if result.surcharge_note:
        findings.append(
            HydroFinding("campus sanitary routing", "sanitary-routing", True, result.surcharge_note)
        )

    # The decisive context is regulatory: the system is already under an SSO-elimination
    # mandate with active I/I remediation, so the documented headroom is effectively spent.
    b = result.sanitary_basis
    if b is not None and b.decree_note:
        findings.append(
            HydroFinding(
                "Allen County collection system",
                "sso-mandate",
                False,
                f"already under an SSO-elimination mandate (eliminate all bypassing by 2015) "
                f"with ${b.ii_remediation_musd.value:g}M of documented storm-water I/I remediation; "
                f"the campus load lands on a system with no wet-weather headroom to spare",
            )
        )
    return findings
