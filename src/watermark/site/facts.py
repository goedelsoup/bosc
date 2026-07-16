"""Build the normalized ``facts`` feed (#1587) — a projection over the bundle's provenanced values.

The facts feed turns a fact question into a tiny retrieval + arithmetic instead of a whole-record
pull: one flat, queryable ``(subject, predicate, value, unit, status, evidence)`` table over every
numeric fact the corpus already carries. Like :mod:`watermark.site.catalog_index`, it is a **post-pass
projection** — it mints no values, copies no payloads, and re-keys each :class:`ProvenancedValue`
already assembled into the economics / greenops / hydrology / air feeds (plus the derived facility
:class:`~watermark.facility.power.PowerBasis`) into a :class:`~watermark.site.feeds.FactItem`.

Design (see ``docs/facts-feed.md``):

* ``value``/``unit`` are copied verbatim from the source ``ProvenancedValue`` (no rounding, no
  invention). ``status`` is the evidence-discipline tag (:func:`watermark.provenance.evidence_tag`)
  derived from the value's ``source_kind`` — ``document``/``connector`` → ``verified``, ``reference``
  → ``reference``, ``assumption``/``derived`` → ``inference``.
* ``subject`` is a stable ``<kind>:<id>`` key (mirroring the catalog handle grammar) with a human
  ``subject_label``; granularity rides on the subject (the county, the sector, the scenario) so the
  ``predicate`` vocabulary stays a small set of clean snake_case field names.
* ``evidence`` keeps the source's free-text citation verbatim; ``page`` stays ``null`` where the
  source ``ProvenancedValue`` carries none — never fabricated (chain of custody).

v1 projects the exported ``ProvenancedValue`` feeds + ``PowerBasis``. ``rsei`` (bare floats +
out-of-band ``meta``), ``records.fields`` (untyped payloads), and ``aggregate_facts`` (#1588) are
deferred follow-ups; each new source is one projector function.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, TypeGuard

from watermark.config import Settings
from watermark.logging import get_logger
from watermark.provenance import SourceKind, evidence_tag
from watermark.site.feeds import FactEvidence, FactItem, FactStatus
from watermark.sites import active_profile

log = get_logger(__name__)

# A serialized ProvenancedValue: {value, unit, source, citation, confidence, asof, low, high}.
# The `source` is a SourceKind literal (the discriminator we key `status` off).
_PV = Mapping[str, Any]
# A bare repo-relative artifact path used verbatim as a citation (e.g.
# "data/reference/hydrology/low-flow-7q10.yaml") — lifted into `evidence.source` so the frontend
# can link it. A citation with spaces (a formula/rationale) is NOT a path and stays text-only.
_PATH_RE = re.compile(r"^(?:data|history)/\S+$")


def _is_pv(value: object) -> TypeGuard[Mapping[str, Any]]:
    """True for a serialized :class:`ProvenancedValue` dict (``value`` + ``unit`` + ``source``).

    A :data:`~typing.TypeGuard` so a caller's ``feed.get(...)`` (typed ``Any | None``) narrows to a
    ``Mapping`` after the check — the projectors read the PV fields off the narrowed value.
    """
    return isinstance(value, Mapping) and "value" in value and "unit" in value and "source" in value


def _status(source_kind: SourceKind, value: object) -> FactStatus:
    """The evidence tag for a projected value — ``open`` when the fact is unquantified."""
    return evidence_tag(source_kind) if value is not None else "open"


def _fact(
    *,
    subject: str,
    subject_label: str,
    subject_kind: str,
    predicate: str,
    pv: _PV,
    feed: str,
) -> FactItem:
    """Project one serialized ``ProvenancedValue`` into a :class:`FactItem` (verbatim value)."""
    source_kind: SourceKind = pv["source"]
    citation = pv.get("citation")
    source = citation if isinstance(citation, str) and _PATH_RE.match(citation) else None
    return FactItem(
        subject=subject,
        subject_label=subject_label,
        subject_kind=subject_kind,
        predicate=predicate,
        value=pv.get("value"),
        unit=pv.get("unit"),
        status=_status(source_kind, pv.get("value")),
        low=pv.get("low"),
        high=pv.get("high"),
        evidence=FactEvidence(
            source=source,
            source_kind=source_kind,
            page=None,  # ProvenancedValue carries no structured page — never invented (#1587)
            citation=citation,
            confidence=pv.get("confidence", "medium"),
            asof=pv.get("asof"),
        ),
        feed=feed,
    )


# --- per-feed projectors -------------------------------------------------------
# Each takes the assembled feed payload (an object dict, or a list of row dicts) + the site slug and
# returns the facts it carries. A projector never re-loads the corpus — it reads what export already
# assembled. Absent/empty feeds are skipped by the caller, so a projector may assume a present payload.


def _project_economics_baseline(feed: Mapping[str, Any], site: str) -> list[FactItem]:
    """County-level QCEW/ACS totals + per-NAICS-sector employment (subject = county / sector)."""
    facts: list[FactItem] = []
    fips = str(feed.get("fips") or "")
    area = str(feed.get("area_name") or fips)
    county = f"county:{fips}"
    latest = feed.get("latest") or {}
    for pred in ("total_employment", "establishments", "avg_annual_pay", "avg_weekly_wage"):
        pv = latest.get(pred)
        if _is_pv(pv):
            facts.append(
                _fact(
                    subject=county,
                    subject_label=area,
                    subject_kind="county",
                    predicate=pred,
                    pv=pv,
                    feed="economics-baseline",
                )
            )
    mhi = feed.get("median_household_income")
    if _is_pv(mhi):
        facts.append(
            _fact(
                subject=county,
                subject_label=area,
                subject_kind="county",
                predicate="median_household_income",
                pv=mhi,
                feed="economics-baseline",
            )
        )
    for sector in latest.get("sectors") or []:
        naics = str(sector.get("naics") or "")
        label = str(sector.get("sector_name") or naics)
        for pred in (
            "annual_avg_employment",
            "establishments",
            "avg_annual_pay",
            "avg_weekly_wage",
            "location_quotient",
        ):
            pv = sector.get(pred)
            if _is_pv(pv):
                facts.append(
                    _fact(
                        subject=f"sector:{fips}:{naics}",
                        subject_label=f"{label} ({area})",
                        subject_kind="sector",
                        predicate=pred,
                        pv=pv,
                        feed="economics-baseline",
                    )
                )
    return facts


def _project_consumer_energy(feed: Mapping[str, Any], site: str) -> list[FactItem]:
    """Latest EIA price/sales per series (subject = state; predicate = ``<fuel>_<metric>``)."""
    facts: list[FactItem] = []
    area = str(feed.get("area") or "")
    label = str(feed.get("area_name") or area)
    for series in feed.get("prices") or []:
        pv = series.get("value")
        if not _is_pv(pv):
            continue
        fuel = str(series.get("fuel") or "").strip().lower().replace(" ", "_")
        metric = str(series.get("metric") or "").strip().lower().replace(" ", "_")
        predicate = f"{fuel}_{metric}".strip("_") or str(series.get("series_id") or "series")
        facts.append(
            _fact(
                subject=f"state:{area.lower()}",
                subject_label=label,
                subject_kind="state",
                predicate=predicate,
                pv=pv,
                feed="consumer-energy",
            )
        )
    return facts


def _project_flat_object(
    feed: Mapping[str, Any],
    *,
    subject: str,
    subject_label: str,
    subject_kind: str,
    feed_name: str,
) -> list[FactItem]:
    """Every top-level ``ProvenancedValue`` field of an object feed (demand-pressure, energy-burden).

    The predicate is the field name; the subject is the whole object's (the facility, the household).
    """
    return [
        _fact(
            subject=subject,
            subject_label=subject_label,
            subject_kind=subject_kind,
            predicate=key,
            pv=pv,
            feed=feed_name,
        )
        for key, pv in feed.items()
        if _is_pv(pv)
    ]


def _project_greenops(feed: Mapping[str, Any], site: str) -> list[FactItem]:
    """The platform's own compute/water footprint headline + water draw (subject = the platform)."""
    facts: list[FactItem] = []
    subject, label, kind = "platform:bosc", "Watermark / BOSC platform", "platform"
    for stat in feed.get("headline") or []:
        pv = stat.get("value")
        key = str(stat.get("key") or "")
        if _is_pv(pv) and key:
            facts.append(
                _fact(
                    subject=subject,
                    subject_label=label,
                    subject_kind=kind,
                    predicate=key,
                    pv=pv,
                    feed="greenops",
                )
            )
    water = feed.get("water") or {}
    for key in ("direct", "indirect", "budget_cap"):
        pv = water.get(key)
        if _is_pv(pv):
            facts.append(
                _fact(
                    subject=subject,
                    subject_label=label,
                    subject_kind=kind,
                    predicate=f"water_{key}",
                    pv=pv,
                    feed="greenops",
                )
            )
    return facts


def _project_hydrology_scenarios(rows: Sequence[Mapping[str, Any]], site: str) -> list[FactItem]:
    """Per-scenario water-balance headline (subject = the scenario, labelled by receiving water)."""
    facts: list[FactItem] = []
    for row in rows:
        scenario = row.get("scenario") or {}
        name = str(scenario.get("name") or "scenario")
        receiving = str(row.get("receiving_water_name") or "")
        subject = f"hydrology-scenario:{name}"
        label = f"{name} — {receiving}" if receiving else name
        top = {
            "consumptive_loss": row.get("consumptive_loss"),
            "receiving_7q10": row.get("receiving_7q10"),
            "receiving_live": row.get("receiving_live"),
        }
        basis = {
            "cooling_demand": scenario.get("cooling_demand"),
            "consumptive_fraction": scenario.get("consumptive_fraction"),
        }
        for predicate, pv in {**top, **basis}.items():
            if _is_pv(pv):
                facts.append(
                    _fact(
                        subject=subject,
                        subject_label=label,
                        subject_kind="hydrology-scenario",
                        predicate=predicate,
                        pv=pv,
                        feed="hydrology-scenarios",
                    )
                )
    return facts


def _project_air_scenarios(rows: Sequence[Mapping[str, Any]], site: str) -> list[FactItem]:
    """Per-scenario genset rating + per-pollutant annual tonnage (subject = the air scenario)."""
    facts: list[FactItem] = []
    for row in rows:
        scenario = row.get("scenario") or {}
        name = str(scenario.get("name") or "scenario")
        subject = f"air-scenario:{name}"
        label = f"{name} genset fleet"
        engine = row.get("engine_mw")
        if _is_pv(engine):
            facts.append(
                _fact(
                    subject=subject,
                    subject_label=label,
                    subject_kind="air-scenario",
                    predicate="engine_mw",
                    pv=engine,
                    feed="air-scenarios",
                )
            )
        for tonnage in row.get("emissions") or []:
            pv = tonnage.get("tpy")
            pollutant = str(tonnage.get("pollutant") or "").strip().lower().replace(" ", "_")
            if _is_pv(pv) and pollutant:
                facts.append(
                    _fact(
                        subject=subject,
                        subject_label=label,
                        subject_kind="air-scenario",
                        predicate=f"{pollutant}_tpy",
                        pv=pv,
                        feed="air-scenarios",
                    )
                )
    return facts


def _project_power_basis(settings: Settings, site: str, facility_label: str) -> list[FactItem]:
    """The derived facility power basis (#87) — genset count/rating, IT load, PUE, facility draw.

    ``PowerBasis`` is derived on the fly (:func:`watermark.facility.power.derive_power_basis`), not
    an exported feed, so it is projected directly here; it is the source of the issue's motivating
    ``genset_count x genset_rating`` example. Facility-gated: ``None`` for a site with no documented
    facility (exactly like ``economics-demand-pressure``)."""
    from watermark.facility.power import derive_power_basis

    basis = derive_power_basis(settings=settings)
    if basis is None:
        return []
    subject = f"facility:{site}"
    facts: list[FactItem] = []
    for predicate in (
        "genset_count",
        "genset_rating",
        "backup_power",
        "it_load",
        "pue",
        "facility_draw",
        "cooling_share_high",
        "implied_pue_from_backup",
    ):
        pv_model = getattr(basis, predicate, None)
        if pv_model is None:
            continue  # a facility with no disclosed gensets leaves the backup/genset facts None
        facts.append(
            _fact(
                subject=subject,
                subject_label=facility_label,
                subject_kind="facility",
                predicate=predicate,
                pv=pv_model.model_dump(mode="json"),
                feed="facility-power",
            )
        )
    return facts


def build_facts(
    payloads_by_feed: Mapping[str, Any],
    *,
    settings: Settings,
) -> list[FactItem]:
    """Project the assembled feeds' provenanced values into the normalized facts table.

    ``payloads_by_feed`` maps a feed name to its parsed payload (an object dict, or a list of row
    dicts) — the just-assembled feeds, so no corpus re-load. A ``(subject, predicate)`` collision
    keeps the first fact (projectors are ordered document-anchored first) and drops the rest, counted
    and logged — never two conflicting values for one key.
    """
    profile = active_profile(settings)
    facility_label = (
        f"{profile.place} data center" if profile.place else f"{settings.site} facility"
    )

    collected: list[FactItem] = []
    # PowerBasis first: its facility facts are document-anchored (the air permit), so on any
    # predicate clash with a downstream derived feed the verified fact wins the dedup below.
    collected.extend(_project_power_basis(settings, settings.site, facility_label))

    obj = payloads_by_feed
    if isinstance(obj.get("economics-baseline"), Mapping):
        collected.extend(_project_economics_baseline(obj["economics-baseline"], settings.site))
    if isinstance(obj.get("consumer-energy"), Mapping):
        collected.extend(_project_consumer_energy(obj["consumer-energy"], settings.site))
    if isinstance(obj.get("economics-demand-pressure"), Mapping):
        collected.extend(
            _project_flat_object(
                obj["economics-demand-pressure"],
                subject=f"facility:{settings.site}",
                subject_label=facility_label,
                subject_kind="facility",
                feed_name="economics-demand-pressure",
            )
        )
    if isinstance(obj.get("energy-burden"), Mapping):
        burden = obj["energy-burden"]
        area = str(burden.get("area") or "")
        area_label = str(burden.get("area_name") or area)
        collected.extend(
            _project_flat_object(
                burden,
                subject=f"household:{area.lower()}",
                subject_label=f"Household in {area_label}",
                subject_kind="household",
                feed_name="energy-burden",
            )
        )
    if isinstance(obj.get("greenops"), Mapping):
        collected.extend(_project_greenops(obj["greenops"], settings.site))
    if isinstance(obj.get("hydrology-scenarios"), Sequence):
        collected.extend(_project_hydrology_scenarios(obj["hydrology-scenarios"], settings.site))
    if isinstance(obj.get("air-scenarios"), Sequence):
        collected.extend(_project_air_scenarios(obj["air-scenarios"], settings.site))

    # Dedup on (subject, predicate): keep first (document-anchored order), drop + count the rest.
    facts: list[FactItem] = []
    seen: set[tuple[str, str]] = set()
    dropped = 0
    for fact in collected:
        key = (fact.subject, fact.predicate)
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        facts.append(fact)

    facts.sort(key=lambda f: (f.subject, f.predicate))
    log.info("facts.projected", site=settings.site, facts=len(facts), dropped=dropped)
    return facts
