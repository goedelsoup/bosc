"""Entity resolution — a small cross-document graph of who relates to whom.

Phase C item 5. Parties appear across deeds, NPDES permits, and SoS business
filings under inconsistent spellings ("BISTROZZI LLC" vs "Bistrozzi LLC, a
Delaware Limited Liability Company"). This module normalizes them to a canonical
key, merges the variants into one :class:`Entity`, classifies each (government /
corporate / individual / trust / facility / water), and records the relationships
between them (conveyances, utility operation, discharge, plus — from SoS filings —
who organized an LLC and its registered agent). A registered agent shared by more
than one entity is flagged with a ``shared_agent`` signal.

Classification follows the *conservative* posture of Periplus's owner-
classification rationale (see ``docs/reference/periplus/`` / the ``../gis`` fork):
prefer a plain corporate/individual label over a "shell" accusation; record
shell-adjacent signals (e.g. a Delaware registration) as evidence, not verdicts.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from typing import Any, Literal, get_args

import yaml

from bosc.config import Settings, get_settings
from bosc.logging import get_logger
from bosc.pipeline.corpus import Corpus, load_corpus

log = get_logger(__name__)

# Legal-form tokens stripped from the *key* (kept in the display name).
_LEGAL_SUFFIXES = frozenset(
    {
        "LLC",
        "LLP",
        "LP",
        "INC",
        "CORP",
        "CORPORATION",
        "CO",
        "COMPANY",
        "LTD",
        "LIMITED",
        "LIABILITY",
        "PLLC",
        "TRUST",
    }
)
_CORPORATE_TOKENS = frozenset(
    {"LLC", "LLP", "LP", "INC", "CORP", "CORPORATION", "COMPANY", "LTD", "PLLC"}
)
# Phrases that mark a government / public body (matched on the raw upper string).
_GOV_PHRASES = (
    "PORT AUTHORITY",
    "BOARD OF COMMISSIONERS",
    "COMMISSIONERS",
    "STATE OF OHIO",
    "CITY OF",
    "VILLAGE OF",
    "SANITARY ENGINEER",
    "BOARD OF EDUCATION",
    "BOARD OF TOWNSHIP",
    "COUNTY ENGINEER",
    "LAND BANK",
    "HOUSING AUTHORITY",
)
# Out-of-state incorporation hints — a shell-adjacent *signal*, never a verdict.
_FOREIGN_HINTS = ("DELAWARE", "WYOMING", "NEVADA")
_FACILITY_HINTS = ("WWTP", "TREATMENT PLANT", "TREATMENT WORKS", "WASTEWATER")
_WATER_HINTS = ("RUN", "RIVER", "CREEK", "DITCH", "DRAIN", "LAKE")


def _base_permit(permit_no: str) -> str:
    """Strip the ``*LD`` / ``*MD`` action suffix to a stable facility id."""
    return permit_no.split("*", 1)[0].strip()


def _looks_like_person(s: str) -> bool:
    """Heuristic: 2-4 capitalized name tokens, no corporate/government markers.

    "Randy Barrera", "Scott J. Ziance" -> True; "Bistrozzi LLC", "NEFF FARMS",
    "Allen County Board of Commissioners" -> False.
    """
    s = s.strip()
    if not s:
        return False
    up = s.upper()
    if any(re.search(rf"\b{re.escape(t)}\b", up) for t in _CORPORATE_TOKENS):
        return False
    if "COUNTY" in up or "TRUST" in up or " AND " in f" {up} ":
        return False
    tokens = s.split()
    if not 2 <= len(tokens) <= 4:
        return False
    # Each token is an initial ("J.") or a Capitalized word with a lowercase tail
    # ("Randy") — ALL-CAPS tokens ("NEFF", "FARMS") are rejected as org-like.
    return all(re.fullmatch(r"[A-Z]\.?|[A-Z][a-z][a-zA-Z.'-]*", t) for t in tokens)


def _split_principal(raw: str) -> tuple[str, str | None]:
    """Split a "Person, Org LLC" applicant into ``(org, person)``.

    The model sometimes records an applicant as "Randy Barrera, Tilted Gate LLC".
    Resolve the org as the primary entity and the person as its principal. Returns
    ``(raw, None)`` when the string isn't that pattern (e.g. "Bistrozzi LLC, a
    Delaware limited liability company" — the part before the comma isn't a
    person, so it is left intact).
    """
    if "," not in raw:
        return raw, None
    before, after = (p.strip() for p in raw.split(",", 1))
    after_is_org = bool(
        re.search(r"\b(?:LLC|LLP|LP|INC|CORP|CORPORATION|COMPANY|LTD|PLLC)\b", after.upper())
    )
    if (
        _looks_like_person(before)
        and after_is_org
        and not after.lower().startswith(("a ", "an ", "the "))
    ):
        return after, before
    return raw, None


def _split_multi(raw: str) -> list[str]:
    """Split a field that the model packed with multiple values into parts.

    Splits only on ``;`` and newlines — *not* commas, because a firm name carries
    internal commas ("Vorys, Sater, Seymour, and Pease"). ``"Heather Dardinger;
    Scott J. Ziance"`` -> two names.
    """
    return [p.strip() for p in re.split(r"[;\n]", raw) if p.strip()]


def normalize_name(raw: str) -> str:
    """Canonical key: uppercased, descriptive clause and legal suffixes removed.

    ``"Bistrozzi LLC, a Delaware Limited Liability Company"`` and ``"BISTROZZI
    LLC"`` both reduce to ``"BISTROZZI"``; ``"Scott J. Ziance"`` and ``"Scott
    Ziance"`` both reduce to ``"SCOTT ZIANCE"`` (interior single-letter initials
    are dropped) so name variants resolve to one entity.
    """
    head = raw.upper().split(",", 1)[0]  # drop the post-comma descriptive clause
    head = re.sub(r"[^\w\s&]", " ", head)
    tokens = head.split()
    while tokens and tokens[0] == "THE":
        tokens.pop(0)
    while tokens and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    # Drop interior single-letter initials (a middle initial is matching noise);
    # keep the first and last token so "C T" (CT Corporation) is left intact.
    if len(tokens) > 2:
        tokens = [tokens[0], *[t for t in tokens[1:-1] if len(t) > 1], tokens[-1]]
    return " ".join(tokens)


def classify(raw: str) -> tuple[str, str, tuple[str, ...]]:
    """Return ``(kind, classification, signals)`` for a party name.

    Conservative: a name is only ``corporate_out_of_state`` (not "shell") when an
    out-of-state hint is present, and that hint is also surfaced as a signal.
    """
    up = raw.upper()
    signals = tuple(h.lower() for h in _FOREIGN_HINTS if h in up)

    if any(h in up for h in _FACILITY_HINTS):
        return "facility", "facility", signals
    is_county_body = bool(re.search(r"\bCOUNTY\b", up)) and "FARM" not in up
    if any(p in up for p in _GOV_PHRASES) or is_county_body:
        return "government", "government_local", signals
    if "TRUST" in up or "TRUSTEE" in up:
        return "trust", "trust", signals
    if any(re.search(rf"\b{re.escape(t)}\b", up) for t in _CORPORATE_TOKENS):
        klass = "corporate_out_of_state" if signals else "corporate_domestic"
        return "corporate", klass, signals
    if any(re.search(rf"\b{h}\b", up) for h in _WATER_HINTS):
        return "water", "receiving_water", signals
    return "individual", "individual", signals


# How a corpus-verified party relates to Project BOSC — an editorial classification
# layered onto the graph (see enrich_with_relation_classes). Ordered by proximity to
# the project for grouped rendering. This is a reading of an ALREADY-verified party,
# never a license to add one (Google stays an annotation, off-graph).
RelationClass = Literal[
    "bosc_relation",  # Project BOSC itself / its campus facilities
    "direct_approval",  # a body that voted/permitted the project
    "direct_manage",  # operates/builds the campus or its forcemains/sewer linkage
    "direct_beneficiary",  # named recipient of the public benefit (abatement, revenue)
    "possible_end_user",  # demand-fit only; connection unestablished (rare on-graph)
    "environmental_beneficiary",  # a receiving water / body bearing the externality
    "govt_relation",  # known tie to another government entity
]
RELATION_CLASS_ORDER: tuple[str, ...] = get_args(RelationClass)


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
        """Shortest legible variant (the long legal recitals aren't useful here)."""
        return min(self.variants, key=len) if self.variants else self.key


@dataclass(frozen=True)
class Relationship:
    """A directed edge between two entity keys, traceable to one document."""

    src: str
    # conveyed_to | operates | discharges_to | registered_agent | organized_by |
    # represented_by | affiliated_with | principal_of | owned_by | tenant_of | discussed_at
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


def build_entity_graph(
    corpus: Corpus | None = None,
    *,
    enrich_parcels: bool = False,
    enrich_lei: bool = False,
    enrich_rsei: bool = False,
    enrich_federal: bool = False,
    enrich_subdivisions: bool = False,
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
            graph._register(g, role="grantee", source=rel, parcels=parcels) for g in d.grantees
        ]
        for grantor_raw in d.grantors:
            src_key = graph._register(grantor_raw, role="grantor", source=rel, parcels=parcels)
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
            if a.applicant_address:
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
    # Run last: the relation-class overlay classifies nodes/edges that every prior
    # enrichment may have added, and only ones that already exist.
    if enrich_relation_classes:
        enrich_with_relation_classes(graph, settings=settings)
    return graph


# --- Subdivision meeting participants (opt-in fold-in) ---------------------

# Curated corridor actors. A meeting party is folded in ONLY if it already resolves
# to a corpus entity or names one of these — a generic org suffix is deliberately
# not enough, because corridor-flagged meetings also transact routine township
# business (road-sealing, marketing, excavating vendors) that isn't the project.
_CORRIDOR_ACTORS = (
    "GOOGLE",
    "AMAZON",
    "BISTROZZI",
    "HUME",
    "TURNER CONSTRUCTION",
    "GENERAL DYNAMICS",
    "ECONOMIC DEVELOPMENT",  # AEDG
    "PORT AUTHORITY",
    "LEIS",  # Cindy Leis runs AEDG + the Port Authority
)
# The econ-dev shield appears under many meeting spellings; collapse to stable keys.
_CANONICAL_ACTORS: tuple[tuple[str, str], ...] = (
    ("ECONOMIC DEVELOPMENT", "ALLEN ECONOMIC DEVELOPMENT GROUP"),
    ("PORT AUTHORITY", "PORT AUTHORITY OF ALLEN COUNTY"),
)
_FORCE_GOV = {sub_key for _, sub_key in _CANONICAL_ACTORS}


def _clean_party(raw: str) -> str:
    """Strip a parenthetical and any trailing role/affiliation after a dash.

    "Paul Basinger (Trustee)" -> "Paul Basinger";
    "Cindy Leis - Allen Economic Development Group" -> "Cindy Leis".
    """
    no_paren = re.sub(r"\s*\([^)]*\)", "", raw)
    head = re.split(r"\s+[\u2013\u2014-]\s+", no_paren, maxsplit=1)[0]
    return re.sub(r"\s+", " ", head).strip()


def _corridor_key(name: str, graph: EntityGraph) -> str | None:
    """Graph key to fold a meeting party under, or ``None`` to skip it.

    Matches on the normalized key (so an incidental affiliation in a person's name
    doesn't misfire). Canonicalizes the econ-dev shield's spellings; otherwise keeps
    the party only if it already resolves to a corpus entity or names a curated
    corridor actor.
    """
    key = normalize_name(name)
    if not key:
        return None
    for needle, canon in _CANONICAL_ACTORS:
        if needle in key:
            return canon
    if key in graph.entities or any(a in key for a in _CORRIDOR_ACTORS):
        return key
    return None


def _actor_identity(needle: str) -> tuple[str, str]:
    """``(display_name, graph_key)`` for a curated corridor-actor needle."""
    for n, canon in _CANONICAL_ACTORS:
        if n == needle:
            return canon, normalize_name(canon)
    return needle.title(), normalize_name(needle)


def _narrative_actors(meeting: dict[str, Any]) -> list[str]:
    """Curated corridor-actor needles named in a meeting's grounded narrative.

    The structured ``parties`` list is the committee roster; a project *principal*
    (Google) is often named only in the summary/relevance prose — e.g. "project BOSC
    (Google data center)" — and would otherwise never link. Scan that prose, but admit
    ONLY the curated :data:`_CORRIDOR_ACTORS` (whole-word), never a new generic party,
    so the parties-path selectivity is preserved.
    """
    parts: list[str] = [
        str(meeting.get("summary") or ""),
        str(meeting.get("corridor_relevance") or ""),
    ]
    decisions = meeting.get("decisions")
    if isinstance(decisions, list):
        parts.extend(str(d) for d in decisions)
    blob = " ".join(parts).upper()
    return [n for n in _CORRIDOR_ACTORS if re.search(rf"\b{re.escape(n)}\b", blob)]


def _subdivision_meeting_entities(graph: EntityGraph, *, settings: Settings | None = None) -> None:
    """Fold corridor-relevant meeting participants into the graph (opt-in).

    Reads every committed ``<slug>/meetings/meeting-summaries.yaml`` and, per corridor
    party, merges it into the graph (enriching a known entity with the meeting as a
    source) and links it to the subdivision body via one ``discussed_at`` edge —
    connecting township actors to the corridor network. One-off residents/vendors stay
    in the summaries, not the graph (see :func:`_corridor_key`); the per-party meeting
    count lives in the entity's ``roles``.
    """
    settings = settings or get_settings()
    seen_edges: set[tuple[str, str]] = set()
    for path in sorted(settings.extracted_dir.glob("*/meetings/meeting-summaries.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict):
            continue
        slug = str(data.get("meta", {}).get("slug", path.parent.parent.name))
        rel = f"{slug}/meetings/meeting-summaries.yaml"
        sub_name = slug.replace("-", " ").title()
        sub_key = normalize_name(sub_name)
        sub_registered = False
        for meeting in data.get("meetings", []):
            if not isinstance(meeting, dict):
                continue
            date = str(meeting.get("date") or "")
            # Fold candidates from the structured roster AND the grounded prose; the
            # latter catches a principal (Google) named only in the summary.
            candidates: list[tuple[str, str]] = []
            for raw in meeting.get("parties", []):
                name = _clean_party(str(raw))
                key = _corridor_key(name, graph)
                if key:
                    candidates.append((name, key))
            for needle in _narrative_actors(meeting):
                candidates.append(_actor_identity(needle))
            for name, key in candidates:
                if key == sub_key:  # a body naming itself as a party is not a relationship
                    continue
                if not sub_registered:
                    graph._register(sub_name, role="meeting_body", source=rel)
                    sub = graph.entities[sub_key]
                    sub.kind, sub.classification = "government", "government_local"
                    sub_registered = True
                graph._register(name, role="meeting_participant", source=rel, key=key)
                if key in _FORCE_GOV:
                    ent = graph.entities[key]
                    ent.kind, ent.classification = "government", "government_local"
                if (key, sub_key) not in seen_edges:
                    seen_edges.add((key, sub_key))
                    graph.relationships.append(
                        Relationship(key, "discussed_at", sub_key, date=date, ref=date, source=rel)
                    )


def enrich_with_parcel_owners(
    graph: EntityGraph, *, settings: Settings | None = None
) -> EntityGraph:
    """Augment a corpus-built graph with cited parcel-owner context (committed data).

    Two additions, both from ``data/reference/allen-gis`` (verbatim county CAMA):

    1. **The federally-held JSMC / Lima Army Tank Plant land** — it appears in no
       deed in the corpus, so it is invisible to the corpus-only graph, yet it is
       the documented Allen County defense-industry footprint. Added as a single
       ``government_military`` node (owner ``UNITED STATES``) carrying its parcels,
       situs addresses, and an ``army_controlled`` signal.
    2. **CAMA situs addresses** for parcels the corpus already tracks — attached to
       the existing grantee/grantor nodes that hold those parcel ids (Bistrozzi and
       its grantors are already corpus-derived; this just grounds their addresses).

    Mutates and returns ``graph``. Idempotent.
    """
    settings = settings or get_settings()
    ref = settings.reference_dir / "allen-gis"

    defense = ref / "parcels.defense.yaml"
    if defense.is_file():
        data = yaml.safe_load(defense.read_text(encoding="utf-8")) or {}
        army = data.get("army_controlled") or []
        if army:
            key = normalize_name("UNITED STATES")
            ent = graph.entities.get(key) or Entity(
                key=key, kind="government", classification="government_military"
            )
            graph.entities[key] = ent
            for p in army:
                for variant in (p.get("owner"), p.get("deeded_owner")):
                    if variant:
                        ent.variants.add(str(variant))
                if p.get("parcel_no"):
                    ent.parcels.add(str(p["parcel_no"]))
                if p.get("situs_address"):
                    ent.addresses.add(str(p["situs_address"]))
            ent.roles["parcel_owner"] += len(army)
            ent.signals.update({"army_controlled", "defense_land"})
            ent.sources.add("data/reference/allen-gis/parcels.defense.yaml")

    cited = ref / "parcels.cited.yaml"
    if cited.is_file():
        data = yaml.safe_load(cited.read_text(encoding="utf-8")) or {}
        by_pid = {
            re.sub(r"\D", "", str(p.get("parcel_no"))): p
            for p in (data.get("parcels") or [])
            if p.get("parcel_no")
        }
        for ent in graph.entities.values():
            for pid in ent.parcels:
                rec = by_pid.get(re.sub(r"\D", "", str(pid)))
                if rec and rec.get("situs_address"):
                    ent.addresses.add(str(rec["situs_address"]))
    return graph


_GLEIF_SOURCE = "data/reference/gleif/lei-records.yaml"


def _add_edge(graph: EntityGraph, rel: Relationship) -> None:
    """Append a relationship unless an identical (src, rel, dst) edge already exists."""
    if not any(
        r.src == rel.src and r.rel == rel.rel and r.dst == rel.dst for r in graph.relationships
    ):
        graph.relationships.append(rel)


def enrich_with_lei(graph: EntityGraph, *, settings: Settings | None = None) -> EntityGraph:
    """Fold the GLEIF-verified corporate ownership chain into the graph (committed data).

    Pinned, verified-only enrichment from ``data/reference/gleif/lei-records.yaml``:

    1. **Attach LEIs to corpus matches** — any committed LEI record whose legal name
       resolves to an entity already in the graph gets its 20-char ``lei`` stamped on
       that node (currently none of the corridor parents are corpus parties, but the
       attach is generic).
    2. **The JSMC operator chain** — fold in **General Dynamics Land Systems** (the
       JSMC operator and Allen County's RSEI #3 facility) and its GLEIF-reported
       **ultimate parent**. ``owned_by`` is verified straight from GLEIF; a
       ``tenant_of`` edge ties the operator to the parcel-derived **UNITED STATES /
       JSMC** node (an *operator inference* from RSEI + county CAMA, not a deed). Both
       carry the defense classification — not a shell "signal", so they aren't
       mislabeled as common-control plumbing.

    Mutates and returns ``graph``. Idempotent. No-op if the LEI reference is absent.
    """
    settings = settings or get_settings()
    from bosc.gleif import load_inventory as load_lei_inventory

    inv = load_lei_inventory(settings.reference_dir)
    if inv is None:
        return graph

    us_key = normalize_name("UNITED STATES")
    for rec in inv.records:
        key = normalize_name(rec.legal_name)
        if not key:
            continue
        is_jsmc_operator = "GENERAL DYNAMICS" in rec.legal_name.upper() and (
            "LAND SYSTEMS" in rec.legal_name.upper()
        )
        existing = graph.entities.get(key)
        # Only fold in *new* nodes for the JSMC operator chain or its parents; other
        # corridor parents (Ford, Dana, …) aren't corpus parties, so adding them would
        # be free-floating noise — they live on the LEI/RSEI pages instead.
        if existing is None and not is_jsmc_operator:
            continue
        ent = existing or Entity(
            key=key,
            kind="corporate",
            classification="corporate_defense" if is_jsmc_operator else "corporate_domestic",
        )
        graph.entities[key] = ent
        ent.variants.add(rec.legal_name)
        ent.lei = rec.lei
        ent.sources.add(_GLEIF_SOURCE)
        if is_jsmc_operator:
            ent.roles["jsmc_operator"] += 1

        # The GLEIF-reported ultimate parent -> a verified ownership edge.
        parent = rec.ultimate_parent or rec.direct_parent
        if parent is not None:
            pkey = normalize_name(parent.name)
            pent = graph.entities.get(pkey) or Entity(
                key=pkey, kind="corporate", classification="corporate_defense"
            )
            graph.entities[pkey] = pent
            pent.variants.add(parent.name)
            pent.lei = parent.lei
            pent.sources.add(_GLEIF_SOURCE)
            _add_edge(
                graph,
                Relationship(
                    key,
                    "owned_by",
                    pkey,
                    ref=f"GLEIF {rec.lei} → {parent.lei}",
                    source=_GLEIF_SOURCE,
                ),
            )

        # Anchor the operator to the Army-owned JSMC land (operator inference).
        if is_jsmc_operator and us_key in graph.entities:
            _add_edge(
                graph,
                Relationship(
                    key,
                    "tenant_of",
                    us_key,
                    ref="RSEI + Allen CAMA (operator inference)",
                    source=_GLEIF_SOURCE,
                ),
            )
    return graph


_RSEI_SOURCE = "data/reference/rsei/inventory.yaml"
_USASPENDING_SOURCE = "data/reference/usaspending/awards.yaml"
_LEI_WATCHLIST_REL = ("profiles", "lei-watchlist.yaml")


def enrich_with_rsei_ownership(
    graph: EntityGraph, *, settings: Settings | None = None
) -> EntityGraph:
    """Fold the GLEIF-resolved corporate parents + their Allen County RSEI facilities in.

    Uses the curated ``rsei_parents`` crosswalk in ``lei-watchlist.yaml`` (the exact RSEI
    ``parent_name`` strings each GLEIF legal entity owns, incl. RSEI's spellings/typos and
    pre-merger names). For each RSEI facility whose ``parent_name`` is in the crosswalk, a
    ``facility`` node and its ``corporate_parent`` node (LEI-stamped) are added with a
    verified ``owned_by`` edge — the industrial-ownership layer behind the toxic
    dischargers (ties the toxics screen to who owns them). The JSMC operator chain is left
    to :func:`enrich_with_lei`. Idempotent; no-op if the references are absent.
    """
    settings = settings or get_settings()
    from bosc.gleif import load_inventory as load_lei_inventory
    from bosc.hydrology import toxics
    from bosc.rsei import load_inventory as load_rsei_inventory

    rsei = load_rsei_inventory(settings.reference_dir)
    lei_inv = load_lei_inventory(settings.reference_dir)
    if rsei is None or lei_inv is None:
        return graph
    wl_path = settings.entities_dir.joinpath(*_LEI_WATCHLIST_REL)
    if not wl_path.is_file():
        return graph
    spec = yaml.safe_load(wl_path.read_text(encoding="utf-8")) or {}

    lei_by_name = {normalize_name(r.legal_name): r for r in lei_inv.records}
    # crosswalk: RSEI parent_name (upper) -> the GLEIF record for that legal entity
    crosswalk: dict[str, Any] = {}
    for ent in spec.get("entities") or []:
        rec = lei_by_name.get(normalize_name(ent["name"]))
        if rec is None or "LAND SYSTEMS" in ent["name"].upper():  # GDLS handled by enrich_with_lei
            continue
        for pn in ent.get("rsei_parents") or []:
            crosswalk[pn.strip().upper()] = rec

    # facilities flagged as toxic water dischargers (ties to the toxics screen)
    try:
        flagged = {
            s.facility.upper()
            for s in toxics.build_screen(settings).screens
            if s.flag in ("critical", "elevated")
        }
    except FileNotFoundError:
        flagged = set()

    for fac in rsei.facilities:
        rec = crosswalk.get((fac.parent_name or "").strip().upper())
        if rec is None:
            continue
        fkey = normalize_name(fac.name)
        pkey = normalize_name(rec.legal_name)
        if not fkey or not pkey:
            continue
        toxic = fac.name.upper() in flagged

        # The RSEI facility shares the parent's exact legal name (the plant is named
        # after the company) -> one node, no self-edge: stamp it as the parent.
        if fkey == pkey:
            ent = graph.entities.get(pkey) or Entity(
                key=pkey, kind="corporate", classification="corporate_parent"
            )
            graph.entities[pkey] = ent
            ent.variants.update({fac.name, rec.legal_name})
            ent.roles["rsei_facility"] += 1
            ent.lei = rec.lei
            ent.sources.update({_RSEI_SOURCE, _GLEIF_SOURCE})
            if toxic:
                ent.signals.add("toxic_water_discharger")
            continue

        fent = graph.entities.get(fkey) or Entity(
            key=fkey, kind="facility", classification="industrial_facility"
        )
        graph.entities[fkey] = fent
        fent.variants.add(fac.name)
        fent.roles["rsei_facility"] += 1
        fent.sources.add(_RSEI_SOURCE)
        if toxic:
            fent.signals.add("toxic_water_discharger")

        pent = graph.entities.get(pkey)
        if pent is None:
            pent = Entity(key=pkey, kind="corporate", classification="corporate_parent")
            graph.entities[pkey] = pent
        pent.variants.add(rec.legal_name)
        pent.lei = rec.lei
        pent.sources.add(_GLEIF_SOURCE)

        _add_edge(
            graph,
            Relationship(
                fkey, "owned_by", pkey, ref=f"RSEI parent / GLEIF {rec.lei}", source=_RSEI_SOURCE
            ),
        )
    return graph


def enrich_with_federal_awards(
    graph: EntityGraph, *, settings: Settings | None = None
) -> EntityGraph:
    """Stamp USASpending all-time federal obligations onto matching graph nodes.

    Only **existing** nodes are enriched (matched by LEI, else by normalized legal name) —
    a verified corridor party (GDLS, GD Corp, the Amazon corridor recipient) gets its
    ``uei`` + ``federal_obligations`` stamped. Context/open recipients with no corpus node
    (Amazon Web Services, Google) are intentionally **not** added — they live on the
    USASpending reference page, not the graph, so the federal layer never overclaims.
    Run after :func:`enrich_with_lei`. Idempotent; no-op if the reference is absent.
    """
    settings = settings or get_settings()
    from bosc.usaspending import load_inventory as load_award_inventory

    inv = load_award_inventory(settings.reference_dir)
    if inv is None:
        return graph

    by_lei = {e.lei: e for e in graph.entities.values() if e.lei}
    for rec in inv.records:
        ent = by_lei.get(rec.lei) if rec.lei else None
        if ent is None:
            ent = graph.entities.get(normalize_name(rec.recipient_name)) or graph.entities.get(
                normalize_name(rec.watchlist_name)
            )
        if ent is None:
            continue  # context/open recipient with no corpus node — stays off-graph
        ent.uei = rec.uei
        ent.federal_obligations = rec.total_obligations
        ent.sources.add(_USASPENDING_SOURCE)
    return graph


_RELATION_CLASSES_SOURCE = "data/entities/profiles/relation-classes.yaml"


def enrich_with_relation_classes(
    graph: EntityGraph, *, settings: Settings | None = None
) -> EntityGraph:
    """Stamp a curated relation-class onto EXISTING graph nodes/edges (committed overlay).

    Reads ``data/entities/profiles/relation-classes.yaml`` — an *editorial* reading of
    how each already-resolved party relates to Project BOSC (direct approval/manage/
    beneficiary, environmental beneficiary, government relation, ...). This is purely
    additive annotation: every ``key`` / ``(src, rel, dst)`` it names must already exist
    in the graph, and any that doesn't is **dropped with a warning** — so the overlay can
    never introduce a node (Google stays an annotation, off-graph). Unknown class strings
    are rejected. Idempotent; no-op if the overlay is absent.
    """
    settings = settings or get_settings()
    path = settings.entities_dir / "profiles" / "relation-classes.yaml"
    if not path.is_file():
        return graph
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def _valid(cls: str, where: str) -> bool:
        if cls not in RELATION_CLASS_ORDER:
            log.warning("entities.relation_class.unknown", value=cls, where=where)
            return False
        return True

    def _resolve_key(name: str) -> str:
        """Canonical graph key for a name/variant/literal key, or normalized fallback."""
        ent = graph.get(name)
        return ent.key if ent is not None else normalize_name(name)

    for item in data.get("entities") or []:
        cls = str(item.get("relation_class", ""))
        ent = graph.get(str(item.get("key", "")))
        if ent is None:
            log.warning("entities.relation_class.missing_entity", key=item.get("key"))
            continue
        if not _valid(cls, f"entity {item.get('key')}"):
            continue
        ent.relation_class = cls
        ent.relation_basis = str(item.get("basis", "")) or None

    # Edges are frozen dataclasses — rebuild the list, replacing matched ones.
    edge_overlays = data.get("edges") or []
    if edge_overlays:
        wanted: dict[tuple[str, str, str], tuple[str, str]] = {}
        for item in edge_overlays:
            cls = str(item.get("relation_class", ""))
            if not _valid(cls, f"edge {item.get('src')}-{item.get('rel')}-{item.get('dst')}"):
                continue
            ekey = (
                _resolve_key(str(item.get("src", ""))),
                str(item.get("rel", "")),
                _resolve_key(str(item.get("dst", ""))),
            )
            wanted[ekey] = (cls, str(item.get("basis", "")))
        matched: set[tuple[str, str, str]] = set()
        rebuilt: list[Relationship] = []
        for r in graph.relationships:
            ekey = (r.src, r.rel, r.dst)
            if ekey in wanted:
                cls, basis = wanted[ekey]
                rebuilt.append(replace(r, relation_class=cls, relation_basis=basis))
                matched.add(ekey)
            else:
                rebuilt.append(r)
        graph.relationships = rebuilt
        for ekey in wanted.keys() - matched:
            log.warning("entities.relation_class.missing_edge", edge=ekey)

    classified = sum(1 for e in graph.entities.values() if e.relation_class)
    log.info("entities.relation_classes", classified=classified)
    return graph
