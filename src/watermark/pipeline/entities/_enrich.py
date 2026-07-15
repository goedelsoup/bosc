"""The seven ``enrich_with_*`` overlays that fold cited reference data into the graph.

Split out of the former monolithic ``entities.py`` (#598). Each overlay reads a different
committed ``data/reference`` / ``data/entities`` file (parcels, places, GLEIF LEIs, RSEI
ownership, federal awards, relation classes, subdivision meetings) and shares the
``_add_edge`` idempotency helper. Re-exported from :mod:`watermark.pipeline.entities`.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

import yaml

from watermark.config import Settings, get_settings
from watermark.logging import get_logger
from watermark.pipeline.corpus import iter_meeting_artifacts, relpath_in_scope
from watermark.pipeline.entities._graph import Entity, EntityGraph, Relationship
from watermark.pipeline.entities._names import RELATION_CLASS_ORDER, normalize_name
from watermark.sites import active_profile, effective_corpus_scope, site_scoped_path

log = get_logger(__name__)


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

    Reads every committed ``meeting-summaries.yaml`` — Lima's flat ``<body>/meetings/`` and a
    peer's nested ``<site>/<body>/meetings/`` (:func:`~watermark.pipeline.corpus.iter_meeting_artifacts`)
    — and, per corridor party, merges it into the graph (enriching a known entity with the meeting
    as a source) and links it to the subdivision body via one ``discussed_at`` edge — connecting
    township actors to the corridor network. One-off residents/vendors stay in the summaries, not
    the graph (see :func:`_corridor_key`); the per-party meeting count lives in the entity's
    ``roles``.
    """
    settings = settings or get_settings()
    scope = effective_corpus_scope(active_profile(settings))
    seen_edges: set[tuple[str, str]] = set()
    for path in iter_meeting_artifacts(settings.extracted_dir, "meeting-summaries.yaml"):
        # Per-site (#762): a sibling site only folds in its own meetings; Lima's whole-tree-minus-
        # peers scope excludes every nested peer tree. Gate on the actual path, not the meta slug.
        rel = path.relative_to(settings.extracted_dir).as_posix()
        if not relpath_in_scope(rel, scope):
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict):
            continue
        slug = str(data.get("meta", {}).get("slug", path.parent.parent.name))
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
    # Per-site (#762): the parcel CAMA reference dir is the active profile's
    # ``gis_parcel.reference_dir`` (Lima = ``allen-gis``), so a sibling site reads its own
    # (Fort Wayne = ``fort-wayne-gis``) and never inherits Allen County's defense parcels /
    # JSMC node. A site with no parcel GIS schema gets nothing here.
    parcel_schema = active_profile(settings).gis_parcel
    if parcel_schema is None:
        return graph
    ref = settings.reference_dir / parcel_schema.reference_dir
    defense_rel = f"data/reference/{parcel_schema.reference_dir}/parcels.defense.yaml"

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
            ent.sources.add(defense_rel)

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


def enrich_with_places(graph: EntityGraph, *, settings: Settings | None = None) -> EntityGraph:
    """Fold the curated POI store in as ``place`` nodes (opt-in).

    Each ``data/entities/poi/<slug>.md`` becomes a ``place`` entity keyed by its **slug**
    (lowercase-dashed, so it never collides with the upper-cased corpus keys), carrying
    its anchor parcels and depth (``classification = place_<depth>``). The profile's
    frontmatter ``relationships`` link the place to entities the graph **already has** —
    resolved via :meth:`EntityGraph.get`; a target that isn't a known entity is logged
    and skipped, never fabricated (the same discipline as every other overlay).

    Mutates and returns ``graph``. Idempotent.
    """
    settings = settings or get_settings()
    from watermark.poi import load_pois  # local import: keep pipeline import-light

    for poi in load_pois(settings=settings):
        front = poi.front
        key = poi.slug
        ent = graph.entities.get(key) or Entity(key=key, kind="place", classification="place")
        ent.classification = f"place_{front.depth}"
        graph.entities[key] = ent
        ent.variants.add(front.name)
        ent.variants.update(front.aliases)
        ent.parcels.update(front.parcels)
        ent.roles["place"] += 1
        ent.sources.add(f"data/entities/poi/{poi.slug}.md")
        if poi.tracked:
            ent.signals.add("tracked")
        if front.kind == "composite":
            ent.signals.add("composite")
        for rel in front.relationships:
            dst = graph.get(rel.entity)
            if dst is None:
                log.warning("places.missing_target", poi=poi.slug, role=rel.role, entity=rel.entity)
                continue
            _add_edge(
                graph,
                Relationship(
                    src=key, rel=rel.role, dst=dst.key, source=f"data/entities/poi/{poi.slug}.md"
                ),
            )
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
    from watermark.gleif import load_inventory as load_lei_inventory

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
    from watermark.gleif import load_inventory as load_lei_inventory
    from watermark.hydrology import toxics
    from watermark.rsei import load_inventory as load_rsei_inventory

    rsei = load_rsei_inventory(settings)
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
    from watermark.usaspending import load_inventory as load_award_inventory

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
    # Per-site (#762): the relation-class overlay is Lima's editorial reading of its parties;
    # a sibling site reads its own ``entities/<slug>/profiles/`` (absent → a no-op overlay).
    path = (
        site_scoped_path(settings.entities_dir, settings.site, is_dir=True)
        / "profiles"
        / "relation-classes.yaml"
    )
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
