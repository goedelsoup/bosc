"""Basin-wide low-flow assimilative screen + derived receiving-water 7Q10s.

The cited 7Q10 table (:mod:`watermark.hydrology.lowflow`) covers only the three Lima-loop
streams read off Ohio EPA fact sheets in our corpus. This module extends the
assimilative screen to the basin-wide POTW inventory (EPA ECHO dischargers per basin,
e.g. ``data/reference/echo/maumee-wwtp.potw.yaml``) by **deriving** a 7Q10 for the major
USGS-gaged mainstems via log-Pearson III (:mod:`watermark.hydrology.lowflow_frequency`) —
``source=derived``: a screening denominator, **not** a cited regulatory statistic.

Discipline (omit, don't guess): a discharger is screened only when its ECHO
``receiving_water`` names a gaged **mainstem directly** — an exact surface-form match in
the curated alias set, and *only* that water (a permit whose ECHO record names two
different waters is refused outright; see :func:`_match_low_flow`). A POTW on an ungaged
tributary/ditch, or with no receiving water in ECHO, is reported "no 7Q10" and left
unscreened. It is never screened against a *downstream* river's larger 7Q10 (that would
overstate dilution into a false "ok"); including a tributary needs that tributary's own
gage or fact sheet. The derived 7Q10 is the value **at the gage**, a screening proxy for
the discharge reach (which differs by drainage-area ratio) — hence ``confidence: medium``.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from watermark.config import Settings, get_settings
from watermark.hydrology.assimilative import dilution_flag
from watermark.hydrology.connectors import HydroOfflineError
from watermark.hydrology.lowflow import load_low_flows, load_permit_low_flows, normalize_permit
from watermark.hydrology.lowflow_frequency import compute_low_flow_frequency
from watermark.hydrology.model import AssimilativeCheck, ProvenancedValue
from watermark.hydrology.units import mgd_to_cfs
from watermark.logging import get_logger

log = get_logger(__name__)

_DERIVED_FILE = "low-flow-7q10.derived.yaml"
# The basin POTW inventory the screen reads is selected by the active site's basin
# (``SiteProfile.basin``); a basin with no committed inventory yet screens against an
# empty set rather than borrowing another basin's dischargers.
_BASIN_POTW_INVENTORY: dict[str, tuple[str, str]] = {
    "maumee": ("echo", "maumee-wwtp.potw.yaml"),
    "great-miami": ("echo", "great-miami-wwtp.potw.yaml"),
    "scioto": ("echo", "scioto-wwtp.potw.yaml"),
    "little-miami": ("echo", "little-miami-wwtp.potw.yaml"),
    "ohio-brush-creek": ("echo", "ohio-brush-creek-wwtp.potw.yaml"),
    "portage": ("echo", "portage-wwtp.potw.yaml"),
    "muskingum": ("echo", "muskingum-wwtp.potw.yaml"),
    "sandusky": ("echo", "sandusky-wwtp.potw.yaml"),
}
_MIN_YEARS = 20  # climatic years of record needed for a defensible LP3 7Q10

# Curated major-network mainstem gages + synthesized headwaters confluences live as
# auditable reference DATA, not code: the committed ``mainstem-gages.yaml`` (gage IDs,
# aliases, and the drainage-area rationale). Loaded + schema-validated here (so a typo or a
# missing key in the reference table fails fast with a clear error, not a KeyError deep in
# the derivation) and fed to the LP3 derivation.
_MAINSTEM_GAGES_FILE = "mainstem-gages.yaml"


class PublishedLowFlow(BaseModel):
    """A **published** (third-party) low-flow statistic at this gage.

    The counterweight to our own LP3 fit at the same gage: a USGS-published 7Q10 computed by
    someone else, over their record, which the derived value can be read against (#1458). It is
    NOT a replacement — the periods differ, often by decades — so it is carried beside the derived
    number rather than substituted for it, and the derivation copies it into the committed derived
    entry so a screening denominator never appears without it.
    """

    model_config = ConfigDict(extra="forbid")

    seven_q10_cfs: float
    one_q10_cfs: float | None = None
    thirty_q10_cfs: float | None = None
    ninety_q10_cfs: float | None = None
    harmonic_mean_cfs: float | None = None
    drainage_area_sq_mi: float | None = None
    period: str
    citation: str


class GageRegulation(BaseModel):
    """Whether a gage's low flow is anthropogenically altered, per a **cited** third party.

    ``regulated`` means the low flow at this gage is not natural streamflow — upstream storage
    releases, diversions, or wastewater discharges hold it up. That is fatal to the gage's use as
    an assimilative *denominator*, because the "river" being credited with dilution is partly the
    managed water (and, where the gage sits below the outfall, partly the discharge under test).
    A regulated gage's derived 7Q10 is demoted to ``confidence: low`` by the derivation.

    Never author this from reasoning — ``citation`` must name the instrument that classifies the
    gage (USGS SIR 2024-5075 table 1 publishes a `Regulated`/`Unregulated` column; Straub 2001
    states each station's regulation in its REMARKS), and ``remark`` carries that source's own
    words verbatim where it has them.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["regulated", "unregulated", "unclassified"]
    citation: str
    remark: str | None = None  # the source's verbatim words, where it states them


class CrossCheckGage(BaseModel):
    """A neighbouring published gage carried beside a screening gage, for context only.

    Never a denominator (it is not this mainstem's curated screening gage and no discharger is
    screened against it) — it exists so a reader can see what the SAME river reads at other
    positions, records and regulation statuses before trusting one number.
    """

    model_config = ConfigDict(extra="forbid")

    gage: str
    gage_name: str
    seven_q10_cfs: float | None = None  # 0.0 is a real published value, not a missing one
    drainage_area_sq_mi: float | None = None
    period: str | None = None
    regulation: Literal["regulated", "unregulated", "unclassified"] | None = None
    citation: str
    note: str | None = None


class MainstemGage(BaseModel):
    """One curated mainstem screening gage: USGS id + the ECHO receiving-water aliases."""

    model_config = ConfigDict(extra="forbid")

    gage: str
    aliases: list[str] = Field(min_length=1)  # a gage with no alias could never be matched
    # Basin slugs this gage may serve as a denominator for. Empty (the default) means
    # unrestricted, which is right for a tributary mainstem whose name occurs in exactly one
    # basin's inventory. A gage is scoped when its *conservatism argument* is scoped: the Ohio
    # River at Greenup is a defensible denominator for the HUC-8 whose frontage sits below it
    # and for no other, yet "OHIO RIVER" is a receiving-water name that recurs in every Ohio
    # tributary basin's inventory (#1120). Scoping is also what lets a second, differently
    # positioned Ohio River gage be registered later for another basin without the two
    # colliding on the same alias.
    basins: list[str] = Field(default_factory=list)
    note: str | None = None
    # Cited annotations (#1458). Optional per gage: absent means "not yet read against the
    # published record", which is honest, not a default of "unregulated".
    published: PublishedLowFlow | None = None
    regulation: GageRegulation | None = None
    cross_check_gages: list[CrossCheckGage] = Field(default_factory=list)


class ConfluenceComponent(BaseModel):
    """One gaged tributary summed into a synthesized headwaters-confluence 7Q10."""

    model_config = ConfigDict(extra="forbid")

    gage: str
    label: str


class HeadwatersConfluence(BaseModel):
    """A mainstem formed by two gaged tributaries, with no long-record gage at the junction."""

    model_config = ConfigDict(extra="forbid")

    # Exactly the two tributaries whose 7Q10s sum to the confluence denominator: a single-
    # tributary "confluence" is meaningless (it would just be that gage), so the schema
    # forbids YAML edits that drop one.
    components: list[ConfluenceComponent] = Field(min_length=2, max_length=2)
    aliases: list[str] = Field(min_length=1)
    note: str | None = None


class _GageTable(BaseModel):
    """The whole committed ``mainstem-gages.yaml``, structure-validated in one pass.

    Both sections are required *and non-empty*: a missing/renamed top-level key or a
    truncated (empty) section is a reference-file error, not a silently-partial screen. The
    ``meta`` block (and any future annotation keys) is ignored, but every gage/confluence
    entry is validated by its nested model.
    """

    model_config = ConfigDict(extra="ignore")

    mainstems: dict[str, MainstemGage] = Field(min_length=1)
    headwaters_confluences: dict[str, HeadwatersConfluence] = Field(min_length=1)


def _mainstem_gages_path(settings: Settings) -> Path:
    return settings.reference_dir / "hydrology" / _MAINSTEM_GAGES_FILE


def _load_gage_table(settings: Settings) -> _GageTable:
    """Read + schema-validate the committed curated gage table.

    Raises ``FileNotFoundError`` if the reference input is absent, and a Pydantic
    ``ValidationError`` if its top-level shape (or any gage/confluence entry) is malformed —
    never a silently-empty screen from a wrong-shaped or truncated file.
    """
    path = _mainstem_gages_path(settings)
    if not path.is_file():
        raise FileNotFoundError(
            f"curated mainstem-gage table missing: {path} "
            "(committed reference input for the basin low-flow screen)"
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _GageTable.model_validate(raw)


def load_mainstem_gages(*, settings: Settings) -> dict[str, MainstemGage]:
    """``{river name -> MainstemGage}`` validated from the committed reference table."""
    return _load_gage_table(settings).mainstems


def load_headwaters_confluences(*, settings: Settings) -> dict[str, HeadwatersConfluence]:
    """``{confluence name -> HeadwatersConfluence}`` validated from the committed table."""
    return _load_gage_table(settings).headwaters_confluences


def _norm(name: str) -> str:
    """Normalize a receiving-water surface form for matching (lowercase, collapse ws)."""
    return " ".join((name or "").strip().lower().split())


# --------------------------------------------------------------------- derivation


def _cited_annotations(spec: MainstemGage) -> dict[str, Any]:
    """The curated `note` / `published` / `regulation` / `cross_check_gages` overlay for an entry.

    Copied verbatim out of the curated ``mainstem-gages.yaml`` into the emitted derived entry, so
    the committed derived file carries the published counterweight beside every screening number
    it publishes and a regen reproduces those blocks byte-for-byte (#1458). The one *computed*
    thing here is the confidence demotion: a gage a cited third party calls **regulated** is not
    measuring natural low flow, so its LP3 fit drops from ``medium`` to ``low`` and says why in
    its own citation. This is the seam where a reference-table edit — not a code edit — changes
    how much weight a screening denominator carries.

    ``note`` travels the same road for the same reason (#1120): a gage's note is where the
    curated table states why *this* gage and not a nearer one, and what the choice costs — the
    reservations a reader is owed before quoting the ratio. The screen reads the derived file,
    not the curated table, so a note left behind in the input never reaches anyone the number
    reaches.
    """
    out: dict[str, Any] = {}
    if spec.regulation is not None and spec.regulation.status == "regulated":
        out["confidence"] = "low"  # replaces the base entry's `medium`, in place
        out["confidence_reason"] = (
            "the gage's low flow is REGULATED (see `regulation` below), so this LP3 fit "
            "describes managed flow, not the stream's own assimilative capacity"
        )
    if spec.published is not None:
        out["published"] = spec.published.model_dump(exclude_none=True)
    if spec.regulation is not None:
        out["regulation"] = spec.regulation.model_dump(exclude_none=True)
    if spec.cross_check_gages:
        out["cross_check_gages"] = [g.model_dump(exclude_none=True) for g in spec.cross_check_gages]
    if spec.note is not None:
        out["note"] = spec.note
    return out


def derive_basin_low_flows(
    *, settings: Settings | None = None, min_years: int = _MIN_YEARS
) -> dict[str, dict[str, Any]]:
    """Derive a 7Q10 per curated mainstem gage (LP3 over the NWIS daily record).

    Network-bound (USGS NWIS) — the regen step for the committed derived reference.
    Omits any gage with fewer than ``min_years`` complete climatic years or a
    non-positive/NaN 7Q10 (never commit an unreliable denominator).
    """
    settings = settings or get_settings()
    streams: dict[str, dict[str, Any]] = {}
    for river, spec in load_mainstem_gages(settings=settings).items():
        try:
            lff = compute_low_flow_frequency(
                site_no=spec.gage, receiving_water=river, settings=settings
            )
        except HydroOfflineError:
            # A missing offline fixture is an infra gap, not a real data absence — surface it
            # loudly (the connector names the key to record) instead of silently omitting the
            # gage into a wrong "no 7Q10" result.
            raise
        except Exception as exc:
            # NWIS returned no data (e.g. a stage-only gage, or a gap in the
            # record window) — omit-don't-guess, same discipline as min_years.
            log.warning(
                "basin.lowflow.gage_error",
                river=river,
                gage=spec.gage,
                error=str(exc).splitlines()[0],
            )
            continue
        stat = lff.stat("7Q10")
        q7 = stat.lp3_cfs.value if stat is not None else math.nan
        if lff.complete_years < min_years or math.isnan(q7) or q7 <= 0.0:
            log.warning(
                "basin.lowflow.omit",
                river=river,
                gage=spec.gage,
                years=lff.complete_years,
                q7=q7,
            )
            continue
        entry: dict[str, Any] = {
            "seven_q10_cfs": round(q7, 2),
            "source": "derived",
            "gage": spec.gage,
            "gage_name": lff.site_name,
            "period": f"{lff.period_start}..{lff.period_end}",
            "complete_years": lff.complete_years,
            "aliases": spec.aliases,
            # Emitted beside the aliases it restricts, so the committed derived file states the
            # restriction rather than leaving it in an input the screen never reads.
            **({"basins": list(spec.basins)} if spec.basins else {}),
            "citation": (
                f"LP3 7Q10 from USGS {spec.gage} ({lff.site_name}), "
                f"{lff.complete_years} climatic years {lff.period_start[:4]}-{lff.period_end[:4]} "
                f"(gage value; screening proxy for the discharge reach)"
            ),
            "confidence": "medium",
        }
        streams[river.lower()] = {**entry, **_cited_annotations(spec)}
    streams.update(_derive_confluences(settings=settings, min_years=min_years))
    log.info("basin.lowflow.derived", rivers=sorted(streams))
    return streams


def _derive_confluences(*, settings: Settings, min_years: int) -> dict[str, dict[str, Any]]:
    """Derive each synthesized headwaters-confluence 7Q10 (sum of its component gages).

    Same omit-don't-guess floor as the mainstem gages: a confluence is emitted only when
    *every* component gage clears ``min_years`` with a positive 7Q10. The sum is a
    conservative denominator (the tributaries' annual minima need not coincide); the entry
    records its components and is tagged ``confidence: low`` accordingly.
    """
    out: dict[str, dict[str, Any]] = {}
    for name, spec in load_headwaters_confluences(settings=settings).items():
        parts: list[dict[str, Any]] = []
        for component in spec.components:
            gage, label = component.gage, component.label
            try:
                lff = compute_low_flow_frequency(
                    site_no=gage, receiving_water=name, settings=settings
                )
            except HydroOfflineError:
                # Offline fixture gap — fail loud, don't silently drop the confluence.
                raise
            except Exception as exc:
                log.warning(
                    "basin.lowflow.confluence_gage_error",
                    confluence=name,
                    gage=gage,
                    error=str(exc).splitlines()[0],
                )
                parts = []
                break
            stat = lff.stat("7Q10")
            q7 = stat.lp3_cfs.value if stat is not None else math.nan
            if lff.complete_years < min_years or math.isnan(q7) or q7 <= 0.0:
                log.warning(
                    "basin.lowflow.confluence_omit",
                    confluence=name,
                    gage=gage,
                    years=lff.complete_years,
                    q7=q7,
                )
                parts = []
                break
            parts.append(
                {
                    "gage": gage,
                    "gage_name": label,
                    "seven_q10_cfs": round(q7, 2),
                    "complete_years": lff.complete_years,
                    "period_start": lff.period_start,
                    "period_end": lff.period_end,
                }
            )
        if not parts:
            continue
        total = round(sum(p["seven_q10_cfs"] for p in parts), 2)
        terms = " + ".join(f"USGS {p['gage']} {p['seven_q10_cfs']} cfs" for p in parts)
        out[name.lower()] = {
            "seven_q10_cfs": total,
            "source": "derived",
            "gage": "+".join(p["gage"] for p in parts),
            "gage_name": " + ".join(p["gage_name"] for p in parts),
            "period": f"{min(p['period_start'] for p in parts)}..{max(p['period_end'] for p in parts)}",
            "complete_years": min(p["complete_years"] for p in parts),
            "components": [
                {
                    "gage": p["gage"],
                    "gage_name": p["gage_name"],
                    "seven_q10_cfs": p["seven_q10_cfs"],
                }
                for p in parts
            ],
            "aliases": spec.aliases,
            "citation": (
                f"sum of LP3 7Q10s ({terms}) — the St. Joseph + St. Marys junction that forms "
                "the Maumee at Fort Wayne; conservative (component annual minima need not "
                "coincide, so the true confluence 7Q10 is >= this sum)"
            ),
            "confidence": "low",
        }
    return out


def _derived_path(settings: Settings) -> Path:
    return settings.reference_dir / "hydrology" / _DERIVED_FILE


def write_derived_low_flows(
    streams: dict[str, dict[str, Any]], *, settings: Settings | None = None
) -> Path:
    """Merge *streams* into the shared derived 7Q10 file and return the path.

    The file is shared across all basin onboard runs; keys are river names and
    don't collide between basins. Merging (not overwriting) ensures that a Sidney
    onboard run doesn't erase Maumee entries written by a Lima/Fort-Wayne run.
    """
    settings = settings or get_settings()
    path = _derived_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)

    existing: dict[str, Any] = {}
    if path.is_file():
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        existing = doc.get("streams") or {}

    merged = {**existing, **streams}
    doc = {
        "meta": {
            "subject": "DERIVED receiving-stream 7Q10s for the major mainstems of the network's river basins",
            "source": "USGS NWIS daily discharge -> log-Pearson III (watermark.hydrology.lowflow_frequency)",
            "discipline": (
                "DERIVED screening denominators (source=derived), NOT cited regulatory "
                "7Q10s — those live in low-flow-7q10.yaml. Each value is the 7Q10 AT THE "
                "GAGE, a proxy for a direct-discharge reach on that mainstem; a discharger "
                "on a tributary is screened only against that tributary's own cited/derived "
                "7Q10, never this one. Regenerate with `watermark derive-low-flows`."
            ),
            "cited_annotations": (
                "An entry's `note` / `published` / `regulation` / `cross_check_gages` blocks (and "
                "the `confidence_reason` a regulated gage carries) are NOT derived — they are "
                "copied verbatim from the curated data/reference/hydrology/mainstem-gages.yaml so "
                "a screening denominator is never read without the published statistic, or the "
                "reservations on the gage choice, beside it (#1458, #1120). Edit them THERE, not "
                "here; this file is regenerated. `regulation.status: regulated` is what demotes "
                "an entry's confidence to `low` — the gage is measuring managed flow (storage "
                "releases, diversions, upstream effluent), not the stream's own assimilative "
                "capacity, and where the gage sits BELOW the outfall being screened it is partly "
                "measuring that discharge itself."
            ),
            "basin_scope": (
                "An entry may carry `basins` (also copied from mainstem-gages.yaml): the basin "
                "slugs whose POTW inventories this denominator may serve. Absent means "
                "unrestricted, which is right for a name that means one river network-wide. It is "
                "set where the gage's conservatism argument is geographic and therefore local — "
                "'Ohio River' is a receiving water in every Ohio tributary basin's inventory, at "
                "reaches hundreds of river miles apart, so one gage keyed to the bare name would "
                "overstate dilution everywhere but the basin it was chosen for (#1120)."
            ),
        },
        "streams": merged,
    }
    path.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
    )
    log.info("basin.lowflow.wrote", path=str(path), rivers=len(merged), added=len(streams))
    return path


def load_derived_low_flows(*, settings: Settings | None = None) -> dict[str, ProvenancedValue]:
    """Return ``{normalized alias -> derived 7Q10 ProvenancedValue}`` (or ``{}`` if absent).

    The derived table is one shared file across every basin, which is safe for a name that
    means one river ("Maumee River" occurs in no Great Miami inventory). It is **not** safe for
    a name that means a different reach of the same river in each basin: an entry may therefore
    declare ``basins``, and one that does is served only to a site whose ``SiteProfile.basin``
    is in that list (#1120). The Ohio River is the case that forced it — every Ohio tributary
    basin has dischargers that name it, at reaches hundreds of river miles and tens of thousands
    of square miles apart, so a single gage keyed to the bare name would be a right answer for
    one basin and an overstated denominator for the rest.
    """
    from watermark.sites import active_profile

    settings = settings or get_settings()
    path = _derived_path(settings)
    if not path.is_file():
        return {}
    active_basin = active_profile(settings).basin
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, ProvenancedValue] = {}
    for name, entry in (data.get("streams") or {}).items():
        if not isinstance(entry, dict) or entry.get("seven_q10_cfs") is None:
            continue
        scope = entry.get("basins") or []
        if scope and active_basin not in scope:
            continue
        pv = ProvenancedValue(
            value=float(entry["seven_q10_cfs"]),
            unit="cfs",
            source="derived",
            citation=entry.get("citation"),
            confidence=str(entry.get("confidence", "medium")),
        )
        for alias in entry.get("aliases") or [name]:
            out[_norm(str(alias))] = pv
    return out


# --------------------------------------------------------------------- the screen


class BasinCoverage(BaseModel):
    """How much of the basin POTW inventory the screen could actually evaluate."""

    model_config = ConfigDict(extra="forbid")

    total: int
    screened: int
    violations: int
    tight: int
    ok: int
    no_receiving_water: int  # ECHO has no receiving_water for the facility
    no_7q10: int  # named receiver, but no cited/derived 7Q10 (ungaged tributary/ditch)
    no_design_flow: int  # matched a 7Q10 but ECHO has no design flow to screen


class BasinScreen(BaseModel):
    """The basin-wide assimilative screen result + its coverage."""

    model_config = ConfigDict(extra="forbid")

    coverage: BasinCoverage
    checks: list[AssimilativeCheck]


def _inventory_path(settings: Settings) -> Path:
    """The POTW inventory file for the active site's basin (``maumee-wwtp.potw.yaml`` etc.).

    Selected by ``SiteProfile.basin`` so a Great Miami site screens against the Great
    Miami inventory, never the Maumee one. An unregistered basin maps to the conventional
    ``<basin>-wwtp.potw.yaml`` name (absent file -> empty screen, never a wrong-basin one).
    """
    from watermark.sites import active_profile

    basin = active_profile(settings).basin
    rel = _BASIN_POTW_INVENTORY.get(basin, ("echo", f"{basin}-wwtp.potw.yaml"))
    return settings.reference_dir / Path(*rel)


def _load_dischargers(settings: Settings) -> list[dict[str, Any]]:
    path = _inventory_path(settings)
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(data.get("facilities") or [])


def _match_low_flow(
    receiving_water: str, lookup: dict[str, ProvenancedValue]
) -> ProvenancedValue | None:
    """A cited/derived 7Q10 iff the receiving water names ONE gaged water and nothing else.

    ECHO's ``CWPStateWaterBodyName`` is a permit-level aggregate: a multi-outfall permit lists
    every water body it discharges to, comma-separated, in an order that carries no meaning. So
    a compound does not say which of the named waters carries the design flow, and the screen
    cannot know — ``"Ohio River, Twelve Mile Creek"`` (New Richmond WWTP, 1.1 MGD) is a 62,000
    mi² river and a creek, and there is nothing in ECHO that says which one the plant's flow
    enters. The rule is therefore: split on commas and require **every** surface form to resolve
    to the same denominator; anything else is unmatched (``no_7q10``) — unscreenable, never
    unaffected.

    Reading only the first form, as this did before #1120, made the guard an artifact of list
    order: ``"Baldwin Ditch, Maumee River"`` was correctly refused only because the small water
    happened to be listed first, and the same permit written the other way round would have been
    credited with the Maumee's far larger 7Q10 — an overstated dilution reported as ``ok``.

    A compound that names ONE water twice ("Auglaize River, Auglaze River"; "Ohio River, Ohio
    RV") still matches, because the duplicate spelling is a registered alias of that gage. That
    is what the alias list in ``mainstem-gages.yaml`` is for and the only reviewed way to say
    two surface forms are one water — so an unregistered second form is, by construction, a
    second water.
    """
    forms = [f for f in (_norm(part) for part in receiving_water.split(",")) if f]
    if not forms:
        return None
    hits = [lookup.get(f) for f in forms]
    first = hits[0]
    if first is None or any(hit != first for hit in hits[1:]):
        return None
    return first


def load_dischargers(*, settings: Settings | None = None) -> list[dict[str, Any]]:
    """The active site's basin POTW inventory (EPA ECHO dischargers), or ``[]`` if absent.

    Which basin is :func:`_inventory_path`'s call, keyed on ``SiteProfile.basin`` — this is not
    the Maumee-only inventory it was before the network went multi-basin.
    """
    return _load_dischargers(settings or get_settings())


def build_low_flow_lookup(*, settings: Settings | None = None) -> dict[str, ProvenancedValue]:
    """Merged ``{normalized receiver -> 7Q10}``: cited (document) overrides derived on overlap.

    Name-keyed only. The permit-scoped cited values (#1458) are deliberately NOT folded in here:
    this lookup answers "what is the design low flow of this *stream*", which is the right
    question for the routed-network solver and the wrong one for a specific outfall.
    """
    settings = settings or get_settings()
    return {**load_derived_low_flows(settings=settings), **load_low_flows(settings=settings)}


class ScreenLowFlows(BaseModel):
    """The two indexes the discharger screen resolves a denominator through, in priority order.

    ``by_permit`` first: a fact-sheet low flow computed **at that permit's outfall** beats any
    value keyed to the river as a whole, because the river as a whole is not what the discharge
    enters. ``by_name`` is the fallback — a cited stream value where one exists, else the derived
    at-gage screening proxy. Carrying both in one object is what stops a new call site from
    silently getting the weaker one (#1458).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    by_name: dict[str, ProvenancedValue] = Field(default_factory=dict)
    by_permit: dict[str, ProvenancedValue] = Field(default_factory=dict)


def build_screen_lookup(*, settings: Settings | None = None) -> ScreenLowFlows:
    """The screen's full denominator lookup: permit-scoped cited values over name-keyed ones."""
    settings = settings or get_settings()
    return ScreenLowFlows(
        by_name=build_low_flow_lookup(settings=settings),
        by_permit=load_permit_low_flows(settings=settings),
    )


def _match_permit_low_flow(
    fac: dict[str, Any], by_permit: dict[str, ProvenancedValue]
) -> ProvenancedValue | None:
    """This facility's OWN fact-sheet 7Q10, if the committed table binds one to its permit."""
    if not by_permit:
        return None
    for key in ("npdes_id", "permit_no", "permit_id", "source_id"):
        raw = fac.get(key)
        if raw and (hit := by_permit.get(normalize_permit(str(raw)))) is not None:
            return hit
    return None


def _ratio_text(ratio: float) -> str:
    """Render a dilution ratio at the same precision the check STORES it (``round(…, 3)``).

    Two decimals silently flattens the whole violation band — Findlay's 0.009 and Lima's 0.007
    both printed as "0.01:1", so the prose figure and the artifact's own `dilution_ratio` field
    disagreed. Below 1.0 the significant digits are all to the right of the point, so keep three.
    """
    return f"{ratio:.2f}" if ratio >= 1.0 else f"{ratio:.3f}"


def screen_facility(
    fac: dict[str, Any], lookup: ScreenLowFlows
) -> tuple[AssimilativeCheck | None, str]:
    """Screen one POTW record against its own outfall's — else its receiver's — 7Q10.

    Returns ``(check, "screened")`` with a populated :class:`AssimilativeCheck`, or
    ``(None, reason)`` where ``reason`` is one of ``no_receiving_water`` / ``no_7q10`` /
    ``no_design_flow``. Shared by the basin-wide screen and the cross-site network synthesis.

    A permit-scoped cited denominator wins where one exists (#1458). The receiving-water check
    still runs first and still gates: a facility whose receiver ECHO cannot name stays
    ``no_receiving_water`` even if its permit is in the table, because the screen's own discipline
    is that an unnamed receiver is an unscreenable one.
    """
    water = fac.get("receiving_water")
    if not water or not str(water).strip():
        return None, "no_receiving_water"
    at_outfall = _match_permit_low_flow(fac, lookup.by_permit)
    q7 = at_outfall or _match_low_flow(str(water), lookup.by_name)
    if q7 is None:
        return None, "no_7q10"
    mgd = fac.get("design_flow_mgd")
    if mgd is None:
        return None, "no_design_flow"
    discharge_cfs = mgd_to_cfs(float(mgd))
    ratio = q7.value / discharge_cfs if discharge_cfs else 0.0
    flag = dilution_flag(ratio)
    name = str(water).split(",")[0].strip().title()
    check = AssimilativeCheck(
        receiving_water=name,
        discharger=str(fac.get("name") or fac.get("npdes_id") or "?"),
        design_low_flow=q7,
        discharge=ProvenancedValue.from_reference(
            round(discharge_cfs, 3),
            "cfs",
            citation=f"ECHO design flow {mgd} MGD ({fac.get('npdes_id')})",
            confidence="medium",
        ),
        dilution_ratio=round(ratio, 3),
        flag=flag,
        detail=(
            f"{name} 7Q10 {q7.value:.2f} cfs "
            f"({'cited AT THIS OUTFALL' if at_outfall is not None else q7.source}) vs discharge "
            f"{discharge_cfs:.2f} cfs -> {_ratio_text(ratio)}:1 dilution ({flag})"
        ),
    )
    return check, "screened"


def check_basin_assimilative(*, settings: Settings | None = None) -> BasinScreen:
    """Screen every basin POTW against its own outfall's — else its receiver's — 7Q10.

    Precedence: a permit-scoped cited fact-sheet value (#1458) beats a name-keyed cited one,
    which beats the derived mainstem proxy. Dischargers with no receiving water, no matchable
    7Q10, or no design flow are counted in the coverage but not screened (omit, don't guess).
    """
    settings = settings or get_settings()
    lookup = build_screen_lookup(settings=settings)

    checks: list[AssimilativeCheck] = []
    total = screened = no_rw = no_q7 = no_flow = 0
    bands = {"violation": 0, "tight": 0, "ok": 0}

    for fac in load_dischargers(settings=settings):
        total += 1
        check, status = screen_facility(fac, lookup)
        if status == "no_receiving_water":
            no_rw += 1
            continue
        if status == "no_7q10":
            no_q7 += 1
            continue
        if status == "no_design_flow":
            no_flow += 1
            continue
        assert check is not None  # status == "screened"
        bands[check.flag] += 1
        screened += 1
        checks.append(check)

    coverage = BasinCoverage(
        total=total,
        screened=screened,
        violations=bands["violation"],
        tight=bands["tight"],
        ok=bands["ok"],
        no_receiving_water=no_rw,
        no_7q10=no_q7,
        no_design_flow=no_flow,
    )
    log.info(
        "basin.screen",
        total=total,
        screened=screened,
        violations=bands["violation"],
        no_7q10=no_q7,
        no_receiving_water=no_rw,
    )
    return BasinScreen(coverage=coverage, checks=sorted(checks, key=lambda c: c.dilution_ratio))
