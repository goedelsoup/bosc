"""The entity graph: resolved parties, their relationships, and the corpus builder.

Split out of the former monolithic ``entities.py`` (#598). Holds the :class:`Entity` /
:class:`Relationship` / :class:`EntityGraph` dataclasses and :func:`build_entity_graph`,
which resolves the corpus graph and (opt-in) folds in the ``enrich_with_*`` overlays.
Re-exported from :mod:`watermark.pipeline.entities`.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from watermark.config import Settings
from watermark.logging import get_logger
from watermark.pipeline.corpus import Corpus, load_corpus
from watermark.pipeline.entities._names import (
    _base_permit,
    _parse_trustee_recital,
    _split_multi,
    _split_principal,
    classify,
    normalize_name,
)

log = get_logger(__name__)


@dataclass
class Entity:
    """A resolved party, merged from one or more raw name variants."""

    key: str
    kind: str  # government | corporate | individual | trust | facility | water
    classification: str
    variants: set[str] = field(default_factory=set)
    signals: set[str] = field(default_factory=set)
    roles: Counter[str] = field(default_factory=Counter)  # grantee/grantor/applicant/...
    parcels: set[str] = field(default_factory=set)
    addresses: set[str] = field(default_factory=set)
    sources: set[str] = field(default_factory=set)
    lei: str | None = None  # GLEIF Legal Entity Identifier, when verified (opt-in enrichment)
    uei: str | None = None  # USASpending Unique Entity Identifier, when verified
    federal_obligations: float | None = None  # all-time federal prime-award $ (USASpending)
    relation_class: str | None = None  # editorial relation to BOSC (opt-in overlay)
    relation_basis: str | None = None  # cited basis for the relation_class

    @property
    def display(self) -> str:
        """Shortest legible variant (the long legal recitals aren't useful here).

        The lexical secondary key makes the choice deterministic when two variants
        tie on length — otherwise ``min`` fell back to set-iteration order, which
        Python randomizes per process, flipping display casing (e.g. ``"Unnamed
        Tributary of Lytle Creek"`` ↔ ``"unnamed tributary of Lytle Creek"``) run
        to run and churning every mirror-derived feed (#1699). ASCII orders
        uppercase before lowercase, so the tie-break also prefers the capitalized
        spelling.
        """
        return min(self.variants, key=lambda v: (len(v), v)) if self.variants else self.key


@dataclass(frozen=True)
class Relationship:
    """A directed edge between two entity keys, traceable to one document."""

    src: str
    # conveyed_to | operates | discharges_to | registered_agent | organized_by |
    # represented_by | affiliated_with | principal_of | trustee_of | owned_by | tenant_of |
    # discussed_at
    rel: str
    dst: str
    date: str = ""
    ref: str = ""  # instrument / permit number
    source: str = ""
    relation_class: str = ""  # editorial relation to BOSC (opt-in overlay)
    relation_basis: str = ""  # cited basis for the relation_class


@dataclass
class EntityGraph:
    entities: dict[str, Entity] = field(default_factory=dict)
    relationships: list[Relationship] = field(default_factory=list)

    def get(self, name: str) -> Entity | None:
        """Look up an entity by raw name or canonical key."""
        return self.entities.get(normalize_name(name)) or self.entities.get(name)

    def _register(
        self,
        raw: str,
        *,
        role: str,
        source: str,
        parcels: tuple[str, ...] = (),
        key: str | None = None,
    ) -> str:
        # An explicit key (e.g. a permit number for a facility) merges name
        # variants that normalization alone wouldn't; otherwise key by name.
        key = key or normalize_name(raw)
        if not key:
            return key
        kind, klass, signals = classify(raw)
        ent = self.entities.get(key)
        if ent is None:
            ent = Entity(key=key, kind=kind, classification=klass)
            self.entities[key] = ent
        ent.variants.add(raw)
        ent.roles[role] += 1
        ent.sources.add(source)
        ent.parcels.update(parcels)
        # Signals accumulate across variants — a Delaware hint may appear in only
        # one spelling — so resolution is order-independent. Upgrade a corporate
        # entity to out-of-state once any variant carries a foreign hint.
        ent.signals.update(signals)
        if ent.kind == "corporate":
            ent.classification = "corporate_out_of_state" if ent.signals else "corporate_domestic"
        return key


def _register_deed_party(
    graph: EntityGraph, raw: str, *, role: str, source: str, parcels: tuple[str, ...]
) -> str:
    """Register a deed grantor/grantee, returning its canonical conveyance-endpoint key.

    The deed path used to register every party raw, so a long trustee recital became its
    own coarse node. Now, before falling back to a plain registration:

    * a **trustee recital** resolves to the *trust* (the party of record on the deed) plus
      a person node per trustee, linked ``trustee_of`` — the conveyance runs from the
      trust;
    * a **"Person, Org LLC"** party resolves to the org plus a ``principal_of`` person,
      the same de-fragmentation the permit/EPA path already applies.

    Either way the persons become individual nodes keyed by :func:`normalize_name`, so a
    deed party and an SoS organizer/principal with the same name reconcile to one node.
    """
    recital = _parse_trustee_recital(raw)
    if recital is not None:
        trust_name, trustees = recital
        trust_key = graph._register(trust_name, role=role, source=source, parcels=parcels)
        for person in trustees:
            person_key = graph._register(person, role="trustee", source=source)
            if person_key and trust_key:
                graph.relationships.append(
                    Relationship(person_key, "trustee_of", trust_key, source=source)
                )
        return trust_key

    org_raw, person_raw = _split_principal(raw)
    if person_raw is not None:
        org_key = graph._register(org_raw, role=role, source=source, parcels=parcels)
        person_key = graph._register(person_raw, role="principal", source=source)
        if person_key and org_key:
            graph.relationships.append(
                Relationship(person_key, "principal_of", org_key, source=source)
            )
        return org_key

    return graph._register(raw, role=role, source=source, parcels=parcels)


def build_entity_graph(
    corpus: Corpus | None = None,
    *,
    enrich_parcels: bool = False,
    enrich_lei: bool = False,
    enrich_rsei: bool = False,
    enrich_federal: bool = False,
    enrich_subdivisions: bool = False,
    enrich_places: bool = False,
    enrich_relation_classes: bool = False,
    settings: Settings | None = None,
) -> EntityGraph:
    """Resolve entities and relationships across deeds, NPDES permits, SoS filings.

    With ``enrich_parcels=True`` the corpus-derived graph is augmented with cited
    parcel-owner context from ``data/reference/allen-gis`` (see
    :func:`enrich_with_parcel_owners`). With ``enrich_lei=True`` the GLEIF-verified
    corporate ownership chain for the JSMC operator is folded in (see
    :func:`enrich_with_lei`) — it anchors to the parcel-derived JSMC node, so run it
    after ``enrich_parcels``. Both are opt-in so the pure corpus graph that the tests
    assert on stays unchanged.
    """
    corpus = corpus if corpus is not None else load_corpus()
    graph = EntityGraph()

    for rel, ex in corpus.deeds:
        d = ex.deed
        parcels = tuple(d.parcel_ids)
        grantees = [
            _register_deed_party(graph, g, role="grantee", source=rel, parcels=parcels)
            for g in d.grantees
        ]
        for grantor_raw in d.grantors:
            src_key = _register_deed_party(
                graph, grantor_raw, role="grantor", source=rel, parcels=parcels
            )
            for dst_key in grantees:
                if src_key and dst_key:
                    graph.relationships.append(
                        Relationship(
                            src_key,
                            "conveyed_to",
                            dst_key,
                            date=d.recording_date or "",
                            ref=d.instrument_no or "",
                            source=rel,
                        )
                    )

    for rel, pex in corpus.permits:
        p = pex.permit
        facility_key = ""
        if p.facility_name:
            # Identity of a facility is its *base* permit number (the ``*LD``/``*MD``
            # action suffix varies between a permit's draft, fact sheet, and final).
            fkey = f"npdes:{_base_permit(p.permit_no)}" if p.permit_no else None
            facility_key = graph._register(p.facility_name, role="facility", source=rel, key=fkey)
        if p.applicant:
            applicant_key = graph._register(p.applicant, role="applicant", source=rel)
            if applicant_key and facility_key:
                graph.relationships.append(
                    Relationship(
                        applicant_key, "operates", facility_key, ref=p.permit_no or "", source=rel
                    )
                )
        if p.receiving_water and facility_key:
            # "Dug Run at River Mile 3.1" and "Dug Run" are the same water.
            water_raw = re.split(r"\s+(?:at|near|@)\s+", p.receiving_water, maxsplit=1, flags=re.I)[
                0
            ]
            water_key = graph._register(water_raw, role="receiving_water", source=rel)
            if water_key:
                graph.relationships.append(
                    Relationship(
                        facility_key, "discharges_to", water_key, ref=p.permit_no or "", source=rel
                    )
                )

    for rel, sex in corpus.filings:
        f = sex.filing
        if not f.entity_name:
            continue
        ent_key = graph._register(f.entity_name, role="registrant", source=rel)
        ent = graph.entities[ent_key]
        if f.principal_address:
            ent.addresses.add(f.principal_address)
        # A foreign formation jurisdiction is a recorded signal (and, for a
        # corporate entity, upgrades it to out-of-state) — straight from the
        # filing, not inferred from the name.
        if f.jurisdiction and f.jurisdiction.strip().lower() not in ("ohio", "oh", ""):
            ent.signals.add(f.jurisdiction.strip().lower())
            if ent.kind == "corporate":
                ent.classification = "corporate_out_of_state"
        if f.registered_agent:
            agent_key = graph._register(f.registered_agent, role="registered_agent", source=rel)
            if f.agent_address:
                graph.entities[agent_key].addresses.add(f.agent_address)
            graph.relationships.append(
                Relationship(
                    ent_key,
                    "registered_agent",
                    agent_key,
                    date=f.filing_date or "",
                    ref=f.filing_id or "",
                    source=rel,
                )
            )
        if f.organizer:
            org_key = graph._register(f.organizer, role="organizer", source=rel)
            graph.relationships.append(
                Relationship(
                    ent_key,
                    "organized_by",
                    org_key,
                    date=f.filing_date or "",
                    ref=f.filing_id or "",
                    source=rel,
                )
            )

    for rel, eex in corpus.actions:
        a = eex.action
        app_key = ""
        if a.applicant:
            # "Randy Barrera, Tilted Gate LLC" -> org is the applicant entity, the
            # person becomes its principal (de-fragments the org across letters).
            org_raw, person_raw = _split_principal(a.applicant)
            app_key = graph._register(org_raw, role="epa_applicant", source=rel)
            # ``_register`` returns "" for a name that normalizes to nothing. Every other
            # use here guards on that; this one did not, so an unregisterable applicant
            # *with* an address raised KeyError and took the whole graph down instead of
            # dropping one node. One bad extraction must not blind the cross-document layer.
            if a.applicant_address and app_key:
                graph.entities[app_key].addresses.add(a.applicant_address)
            if person_raw:
                principal_key = graph._register(person_raw, role="principal", source=rel)
                if principal_key and app_key:
                    graph.relationships.append(
                        Relationship(principal_key, "principal_of", app_key, source=rel)
                    )
        # A letter may pack several contacts / firms into one field; split them so
        # each resolves to its own node. Representation/affiliation aren't permit-
        # specific, so blank ref lets repeats across letters collapse to one edge.
        contact_keys = []
        for name in _split_multi(a.contact_name or ""):
            ck = graph._register(name, role="permit_contact", source=rel)
            if ck and ck != app_key:
                contact_keys.append(ck)
                if app_key:
                    graph.relationships.append(
                        Relationship(app_key, "represented_by", ck, source=rel)
                    )
        for firm in _split_multi(a.contact_firm or ""):
            fk = graph._register(firm, role="firm", source=rel)
            # Skip a "firm" that is actually the applicant itself (model slip).
            if not fk or fk == app_key:
                continue
            for ck in contact_keys:
                graph.relationships.append(Relationship(ck, "affiliated_with", fk, source=rel))

    # The same conveyance / operation is reported by multiple artifacts; collapse
    # identical edges (keep the first, dropping exact duplicates).
    seen: set[tuple[str, str, str, str]] = set()
    unique: list[Relationship] = []
    for r in graph.relationships:
        # Collapse the permit ``*LD``/``*MD`` action suffix so the same discharge
        # reported under two permit versions is one edge; deed instruments (no
        # ``*``) are untouched, keeping genuinely distinct conveyances apart.
        edge = (r.src, r.rel, r.dst, _base_permit(r.ref))
        if edge in seen:
            continue
        seen.add(edge)
        unique.append(r)
    graph.relationships = unique

    # Shell-pattern signal: a registered agent (or an agent address) shared by
    # more than one entity. This is the strongest shell tell public SoS records
    # offer — it does not reveal beneficial ownership, only common control plumbing.
    agent_to_entities: dict[str, set[str]] = defaultdict(set)
    addr_to_entities: dict[str, set[str]] = defaultdict(set)
    for r in graph.relationships:
        if r.rel == "registered_agent":
            agent_to_entities[r.dst].add(r.src)
            for addr in graph.entities[r.dst].addresses:
                addr_to_entities[addr].add(r.src)
    for shared in (*agent_to_entities.values(), *addr_to_entities.values()):
        if len(shared) > 1:
            for ent_key in shared:
                graph.entities[ent_key].signals.add("shared_agent")

    log.info("entities.built", entities=len(graph.entities), relationships=len(graph.relationships))
    # Imported lazily: the enrich overlays import this module (Entity/EntityGraph/Relationship),
    # so a module-level import here would close the build<->enrich cycle (#598).
    from watermark.pipeline.entities._enrich import (
        _subdivision_meeting_entities,
        enrich_with_federal_awards,
        enrich_with_lei,
        enrich_with_parcel_owners,
        enrich_with_places,
        enrich_with_relation_classes,
        enrich_with_rsei_ownership,
    )

    if enrich_subdivisions:
        _subdivision_meeting_entities(graph, settings=settings)
    if enrich_parcels:
        enrich_with_parcel_owners(graph, settings=settings)
    if enrich_lei:
        enrich_with_lei(graph, settings=settings)
    if enrich_rsei:
        enrich_with_rsei_ownership(graph, settings=settings)
    if enrich_federal:
        enrich_with_federal_awards(graph, settings=settings)
    if enrich_places:
        enrich_with_places(graph, settings=settings)
    # Run last: the relation-class overlay classifies nodes/edges that every prior
    # enrichment may have added, and only ones that already exist.
    if enrich_relation_classes:
        enrich_with_relation_classes(graph, settings=settings)
    return graph
