"""Tests for cross-document entity resolution."""

from __future__ import annotations

import os
import subprocess
import sys

from watermark.config import Settings
from watermark.models import (
    BusinessFiling,
    Deed,
    DeedExtraction,
    EpaExtraction,
    EpaPermitAction,
    NpdesExtraction,
    NpdesPermit,
    SosExtraction,
)
from watermark.pipeline.corpus import Corpus
from watermark.pipeline.entities import (
    _base_permit,
    _looks_like_person,
    _parse_trustee_recital,
    _split_multi,
    _split_principal,
    build_entity_graph,
    classify,
    enrich_with_federal_awards,
    enrich_with_lei,
    enrich_with_parcel_owners,
    enrich_with_rsei_ownership,
    normalize_name,
)


def test_normalize_merges_legal_variants() -> None:
    assert normalize_name("BISTROZZI LLC") == "BISTROZZI"
    assert normalize_name("Bistrozzi LLC, a Delaware Limited Liability Company") == "BISTROZZI"
    assert (
        normalize_name("THE PORT AUTHORITY OF ALLEN COUNTY, OHIO")
        == "PORT AUTHORITY OF ALLEN COUNTY"
    )


def test_normalize_drops_middle_initial_but_keeps_two_token_orgs() -> None:
    # "Scott J. Ziance" and "Scott Ziance" resolve to one person.
    assert normalize_name("Scott J. Ziance") == normalize_name("Scott Ziance") == "SCOTT ZIANCE"
    # A two-token org ("C T Corporation") keeps both letters — no interior to drop.
    assert normalize_name("C T Corporation") == "C T"


def test_split_multi_splits_on_semicolons_not_firm_commas() -> None:
    assert _split_multi("Heather Dardinger; Scott J. Ziance") == [
        "Heather Dardinger",
        "Scott J. Ziance",
    ]
    # A firm name with internal commas stays whole.
    assert _split_multi("EMH&T; Vorys, Sater, Seymour, and Pease") == [
        "EMH&T",
        "Vorys, Sater, Seymour, and Pease",
    ]
    assert _split_multi("EMH&T") == ["EMH&T"]


def test_base_permit_strips_action_suffix() -> None:
    assert _base_permit("2PK00002*MD") == "2PK00002"
    assert _base_permit("2PK00002*LD") == "2PK00002"
    assert _base_permit("2PH00006") == "2PH00006"


def test_classify_is_conservative() -> None:
    assert classify("THE PORT AUTHORITY OF ALLEN COUNTY, OHIO")[:2] == (
        "government",
        "government_local",
    )
    assert classify("Allen County Board of Commissioners")[0] == "government"
    kind, klass, signals = classify("Bistrozzi LLC, a Delaware Limited Liability Company")
    assert (kind, klass) == ("corporate", "corporate_out_of_state")
    assert "delaware" in signals
    assert classify("NEFF FARMS, INC.")[:2] == ("corporate", "corporate_domestic")
    assert classify("American II Wastewater Treatment Plant")[0] == "facility"
    assert classify("Kyle C. Brenneman, Co-Trustee of the Living Trust")[0] == "trust"
    assert classify("James W. Neighbors")[0] == "individual"
    # A corporate token wins over the water-name heuristic.
    assert classify("Pike Run Farms LLC")[0] == "corporate"
    # Government bodies that used to fall through to ``individual`` (#1660): a federal military
    # department is ``government_military``; a regional planning commission is ``government_local``.
    assert classify("United States Department of the Air Force")[:2] == (
        "government",
        "government_military",
    )
    assert classify("Miami Valley Regional Planning Commission")[:2] == (
        "government",
        "government_local",
    )
    # …but the military phrase is specific: a corporate name carrying "Air Force" is not swept in.
    assert classify("Air Force Federal Credit Union")[0] == "individual"
    assert classify("United States Steel Corporation")[0] == "corporate"


def test_looks_like_person() -> None:
    assert _looks_like_person("Randy Barrera")
    assert _looks_like_person("Scott J. Ziance")
    assert not _looks_like_person("Bistrozzi LLC")
    assert not _looks_like_person("NEFF FARMS")
    assert not _looks_like_person("Allen County Board of Commissioners")
    assert not _looks_like_person("Kyle C. Brenneman and Sarah N. Brenneman")


def test_split_principal() -> None:
    assert _split_principal("Randy Barrera, Tilted Gate LLC") == (
        "Tilted Gate LLC",
        "Randy Barrera",
    )
    assert _split_principal("Timothy Chadwick, Tilted Gate, LLC") == (
        "Tilted Gate, LLC",
        "Timothy Chadwick",
    )
    # Not the pattern: a bare org, or an org followed by a descriptive clause.
    assert _split_principal("Bistrozzi LLC") == ("Bistrozzi LLC", None)
    assert _split_principal("Bistrozzi LLC, a Delaware limited liability company") == (
        "Bistrozzi LLC, a Delaware limited liability company",
        None,
    )
    assert _split_principal("THE PORT AUTHORITY OF ALLEN COUNTY, OHIO")[1] is None
    # A comma before a corporate designator is punctuation inside one name, not a separator
    # between a person and an org. Splitting these produced the organization "Inc." — which
    # normalizes to the empty key, crashing the graph build where the applicant carried an
    # address and silently dropping the applicant where it did not (issue 1380).
    assert _split_principal("Amazon Data Services, Inc.") == ("Amazon Data Services, Inc.", None)
    assert _split_principal("Amazon Web Services, Inc.") == ("Amazon Web Services, Inc.", None)
    assert _split_principal("George J. Igel & Co., Inc.") == ("George J. Igel & Co., Inc.", None)
    assert _split_principal("Tilted Gate, LLC") == ("Tilted Gate, LLC", None)
    # The designator run is bounded by the NEXT comma, so a trailing descriptive clause does
    # not resurrect the bad split: only "Inc." is weighed here, not "a Delaware corporation".
    # (The "a "/"an "/"the " guard never fires for this one — the clause is not leading.)
    assert _split_principal("Amazon Data Services, Inc., a Delaware corporation") == (
        "Amazon Data Services, Inc., a Delaware corporation",
        None,
    )
    # Exercises the ``CO`` bare-suffix token specifically: "Marcus Moan" passes the person
    # check and "Co., Inc." is org-like, so only ``CO`` being a recognized suffix token keeps
    # this whole — drop it from _CORPORATE_SUFFIX_TOKENS and this splits.
    assert _split_principal("Marcus Moan, Co., Inc.") == ("Marcus Moan, Co., Inc.", None)


def _deed(
    rel: str, *, no: str, grantor: str, grantee: str, parcels: list[str]
) -> tuple[str, DeedExtraction]:
    return rel, DeedExtraction(
        doc_id=no,
        source_path=f"/x/{no}.pdf",
        kind="deed",
        dpi=200,
        deed=Deed(
            instrument_no=no,
            recording_date="2025-08-13",
            grantors=[grantor],
            grantees=[grantee],
            parcel_ids=parcels,
        ),
    )


def test_parse_trustee_recital() -> None:
    trust, persons = _parse_trustee_recital(
        "Kyle C. Brenneman and Sarah N. Brenneman, Co-Trustees of the Kyle C. Brenneman "
        "Living Trust dated March 30, 2023, and any amendments thereto"
    ) or ("", [])
    assert trust == "Kyle C. Brenneman Living Trust"  # date/amendments boilerplate stripped
    assert persons == ["Kyle C. Brenneman", "Sarah N. Brenneman"]
    # A single trustee, no trailing recital.
    assert _parse_trustee_recital("Jane A. Doe, Trustee of the Doe Family Trust") == (
        "Doe Family Trust",
        ["Jane A. Doe"],
    )
    # Not a trustee recital — a plain org/person is left untouched.
    assert _parse_trustee_recital("NEFF FARMS, INC.") is None
    assert _parse_trustee_recital("James W. Neighbors") is None
    # "Trustee of" but the named instrument isn't a trust → don't guess a split.
    assert _parse_trustee_recital("Jane Doe, Trustee of the Doe Foundation") is None


def test_deed_trustee_recital_splits_into_trust_and_trustees() -> None:
    # The Brenneman recital that used to form one coarse trust-classified node now resolves
    # to the trust (the party of record) + its trustee persons, linked `trustee_of`.
    corpus = Corpus(
        deeds=[
            _deed(
                "recorder/t.deed.yaml",
                no="T1",
                grantor=(
                    "Kyle C. Brenneman and Sarah N. Brenneman, Co-Trustees of the Kyle C. "
                    "Brenneman Living Trust dated March 30, 2023, and any amendments thereto"
                ),
                grantee="BISTROZZI LLC",
                parcels=["P1"],
            ),
        ]
    )
    graph = build_entity_graph(corpus)

    trust = graph.get("Kyle C. Brenneman Living Trust")
    kyle = graph.get("Kyle C. Brenneman")
    sarah = graph.get("Sarah N. Brenneman")
    assert trust is not None and trust.kind == "trust"
    assert kyle is not None and kyle.kind == "individual"
    assert sarah is not None and sarah.kind == "individual"

    rels = {(r.src, r.rel, r.dst) for r in graph.relationships}
    assert (kyle.key, "trustee_of", trust.key) in rels
    assert (sarah.key, "trustee_of", trust.key) in rels
    # The conveyance runs from the trust, not from a coarse multi-person recital node.
    assert (trust.key, "conveyed_to", "BISTROZZI") in rels
    assert graph.get("Kyle C. Brenneman and Sarah N. Brenneman") is None


def test_deed_person_reconciles_with_sos_organizer() -> None:
    # A trustee named in a deed and the same person organizing an SoS LLC resolve to ONE
    # node carrying both threads — the deeds-side ↔ SoS person reconciliation the issue
    # asks for (enabled by splitting the recital into person nodes).
    corpus = Corpus(
        deeds=[
            _deed(
                "recorder/z.deed.yaml",
                no="Z1",
                grantor="Scott J. Ziance, Trustee of the Ziance Family Trust",
                grantee="BISTROZZI LLC",
                parcels=["P1"],
            ),
        ],
        filings=[
            _filing(
                "permits/b.sos.yaml",
                name="Bistrozzi Addition LLC",
                agent="C T Corporation",
                agent_addr="4400 East Commons Way",
                organizer="Scott Ziance",  # no middle initial — still the same person
                juris="Delaware",
            ),
        ],
    )
    graph = build_entity_graph(corpus)

    ziance = graph.get("Scott Ziance")
    assert ziance is not None and ziance.kind == "individual"
    assert ziance.roles["trustee"] == 1  # the deeds thread
    assert ziance.roles["organizer"] == 1  # the SoS thread — same reconciled node
    rels = {(r.src, r.rel, r.dst) for r in graph.relationships}
    trust = graph.get("Ziance Family Trust")
    assert trust is not None and (ziance.key, "trustee_of", trust.key) in rels
    assert ("BISTROZZI ADDITION", "organized_by", "SCOTT ZIANCE") in rels


def _permit(
    rel: str, *, no: str, facility: str, applicant: str, water: str
) -> tuple[str, NpdesExtraction]:
    return rel, NpdesExtraction(
        doc_id=no,
        source_path=f"/x/{rel}",
        kind="npdes",
        dpi=150,
        permit=NpdesPermit(
            permit_no=no, facility_name=facility, applicant=applicant, receiving_water=water
        ),
    )


def test_build_graph_resolves_and_links() -> None:
    corpus = Corpus(
        deeds=[
            _deed(
                "recorder/a.deed.yaml",
                no="I1",
                grantor="NEFF FARMS, INC.",
                grantee="BISTROZZI LLC",
                parcels=["P1"],
            ),
            _deed(
                "recorder/b.deed.yaml",
                no="I2",
                grantor="Pike Run Farms LLC",
                grantee="Bistrozzi LLC, a Delaware Limited Liability Company",
                parcels=["P2"],
            ),
        ],
        permits=[
            # Same base permit, different action suffix + name spelling.
            _permit(
                "oepa/p1.npdes.yaml",
                no="2PK00002*LD",
                facility="Shawnee II WWTP",
                applicant="Allen County Board of Commissioners",
                water="Ottawa River",
            ),
            _permit(
                "oepa/p2.npdes.yaml",
                no="2PK00002*MD",
                facility="Shawnee II Wastewater Treatment Works",
                applicant="Allen County Board of Commissioners",
                water="Ottawa River at River Mile 5",
            ),
        ],
    )
    graph = build_entity_graph(corpus)

    # The two Bistrozzi spellings resolve to one grantee with both parcels.
    bistrozzi = graph.get("BISTROZZI LLC")
    assert bistrozzi is not None
    assert bistrozzi.roles["grantee"] == 2
    assert bistrozzi.parcels == {"P1", "P2"}
    assert "delaware" in bistrozzi.signals

    # The facility merges across the *LD/*MD suffix into a single entity.
    facilities = [e for e in graph.entities.values() if e.kind == "facility"]
    assert len(facilities) == 1
    assert facilities[0].roles["facility"] == 2

    rels = {(r.src, r.rel, r.dst) for r in graph.relationships}
    assert ("NEFF FARMS", "conveyed_to", "BISTROZZI") in rels
    assert ("PIKE RUN FARMS", "conveyed_to", "BISTROZZI") in rels
    # "Ottawa River" and "Ottawa River at River Mile 5" collapse to one water node.
    discharges = [r for r in graph.relationships if r.rel == "discharges_to"]
    assert len(discharges) == 1


def test_display_breaks_length_ties_deterministically() -> None:
    # Two casings of the same water tie on length. The old `min(variants, key=len)`
    # fell back to set-iteration order, which Python randomizes per process
    # (PYTHONHASHSEED) — so the display flipped run to run and churned every mirror
    # feed (#1699). A set literal can't reproduce that here (iteration order is fixed
    # for the life of one process), so resolve the display in fresh subprocesses under
    # distinct seeds and assert one stable winner: the lexical tie-break picks the
    # capitalized spelling (ASCII orders uppercase before lowercase) every time.
    snippet = (
        "from watermark.pipeline.entities import Entity\n"
        "e = Entity(key='k', kind='water', classification='water')\n"
        "e.variants = {'unnamed tributary of Lytle Creek', 'Unnamed Tributary of Lytle Creek'}\n"
        "print(e.display)\n"
    )
    winners = set()
    for seed in ("0", "1", "2", "7", "42", "1000"):
        proc = subprocess.run(
            [sys.executable, "-c", snippet],
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONHASHSEED": seed},
        )
        winners.add(proc.stdout.strip())
    assert winners == {"Unnamed Tributary of Lytle Creek"}


def test_parcel_enrichment_adds_jsmc_node(hydro_settings: Settings) -> None:
    # Enrichment is opt-in: the corpus-only graph is unchanged...
    base = build_entity_graph()
    assert base.get("UNITED STATES") is None
    # ...and adding parcel context surfaces the federally-held JSMC tank-plant land.
    enriched = build_entity_graph(enrich_parcels=True, settings=hydro_settings)
    jsmc = enriched.get("UNITED STATES")
    assert jsmc is not None
    assert jsmc.kind == "government" and jsmc.classification == "government_military"
    assert {"army_controlled", "defense_land"} <= jsmc.signals
    assert len(jsmc.parcels) == 5
    assert any("BUCKEYE" in a for a in jsmc.addresses)
    assert len(enriched.entities) == len(base.entities) + 1


def test_parcel_enrichment_is_idempotent(hydro_settings: Settings) -> None:
    graph = build_entity_graph(enrich_parcels=True, settings=hydro_settings)
    n = len(graph.entities)
    enrich_with_parcel_owners(graph, settings=hydro_settings)  # second pass
    assert len(graph.entities) == n


def test_lei_enrichment_folds_in_ownership_chain(hydro_settings: Settings) -> None:
    # Opt-in: the corpus-only graph carries no LEI.
    base = build_entity_graph()
    assert all(e.lei is None for e in base.entities.values())

    graph = build_entity_graph(enrich_parcels=True, enrich_lei=True, settings=hydro_settings)
    gdls = graph.get("General Dynamics Land Systems Inc.")
    assert gdls is not None
    assert gdls.lei == "875500ULXB4CYQSJVA03"
    assert gdls.classification == "corporate_defense"
    # Verified ownership edge to the GLEIF ultimate parent (also LEI-stamped).
    parent = graph.get("GENERAL DYNAMICS CORPORATION")
    assert parent is not None and parent.lei == "9C1X8XOOTYY2FNYTVH06"
    assert any(
        r.rel == "owned_by" and r.src == gdls.key and r.dst == parent.key
        for r in graph.relationships
    )
    # Operator inference anchors the contractor to the Army-owned JSMC land.
    us = graph.get("UNITED STATES")
    assert us is not None
    assert any(
        r.rel == "tenant_of" and r.src == gdls.key and r.dst == us.key for r in graph.relationships
    )


def test_lei_enrichment_is_idempotent(hydro_settings: Settings) -> None:
    graph = build_entity_graph(enrich_parcels=True, enrich_lei=True, settings=hydro_settings)
    n_ent, n_rel = len(graph.entities), len(graph.relationships)
    enrich_with_lei(graph, settings=hydro_settings)  # second pass
    assert len(graph.entities) == n_ent
    assert len(graph.relationships) == n_rel


def test_rsei_ownership_folds_in_industrial_owners(hydro_settings: Settings) -> None:
    """Each Allen County RSEI facility links `owned_by` its GLEIF-resolved parent."""
    graph = build_entity_graph(enrich_lei=True, enrich_rsei=True, settings=hydro_settings)
    # Lima Refining (a toxic discharger) -> Cenovus (via Husky), LEI-stamped.
    refinery = graph.get("LIMA REFINING CO")
    cenovus = graph.get("Cenovus Energy Inc.")
    assert refinery is not None and refinery.classification == "industrial_facility"
    assert "toxic_water_discharger" in refinery.signals
    assert cenovus is not None and cenovus.lei == "254900LJGL2N2XEMD470"
    assert any(
        r.rel == "owned_by" and r.src == refinery.key and r.dst == cenovus.key
        for r in graph.relationships
    )
    # Shell owns the Equilon terminal; Ford owns the Lima Engine Plant.
    assert graph.get("Shell plc") is not None
    assert graph.get("EQUILON LIMA TERMINAL") is not None


def test_rsei_ownership_no_self_loop_when_facility_is_parent(hydro_settings: Settings) -> None:
    """INEOS facility == INEOS parent name: one node, no self-referential edge."""
    graph = build_entity_graph(enrich_lei=True, enrich_rsei=True, settings=hydro_settings)
    ineos = graph.get("INEOS USA LLC")
    assert ineos is not None and ineos.lei == "549300TWZ86K81VO8O17"
    assert not any(r.rel == "owned_by" and r.src == r.dst == ineos.key for r in graph.relationships)


def test_federal_awards_stamp_existing_nodes_only(hydro_settings: Settings) -> None:
    """USASpending obligations land on GDLS/GD Corp/Amazon; AWS & Google stay off-graph."""
    graph = build_entity_graph(
        enrich_parcels=True, enrich_lei=True, enrich_federal=True, settings=hydro_settings
    )
    gdls = graph.get("General Dynamics Land Systems Inc.")
    assert gdls is not None
    assert gdls.uei == "HAWKSQF848W7"
    assert gdls.federal_obligations is not None and gdls.federal_obligations > 1e10
    # Matched by LEI onto the GLEIF parent node.
    gd_corp = graph.get("GENERAL DYNAMICS CORPORATION")
    assert gd_corp is not None and gd_corp.uei == "VF58HFRNGEL8"
    # Context/open recipients are NOT added as nodes (no overclaim).
    assert graph.get("Amazon Web Services, Inc.") is None
    assert graph.get("Google LLC") is None


def test_federal_and_rsei_enrichment_idempotent(hydro_settings: Settings) -> None:
    graph = build_entity_graph(
        enrich_lei=True, enrich_rsei=True, enrich_federal=True, settings=hydro_settings
    )
    n_ent, n_rel = len(graph.entities), len(graph.relationships)
    enrich_with_rsei_ownership(graph, settings=hydro_settings)
    enrich_with_federal_awards(graph, settings=hydro_settings)
    assert len(graph.entities) == n_ent
    assert len(graph.relationships) == n_rel


def _filing(
    rel: str, *, name: str, agent: str, agent_addr: str, organizer: str, juris: str
) -> tuple[str, SosExtraction]:
    return rel, SosExtraction(
        doc_id=name,
        source_path=f"/x/{rel}",
        kind="sos",
        dpi=200,
        filing=BusinessFiling(
            entity_name=name,
            entity_type="foreign LLC",
            jurisdiction=juris,
            filing_date="2025-10-01",
            registered_agent=agent,
            agent_address=agent_addr,
            organizer=organizer,
        ),
    )


def test_sos_filings_link_organizer_agent_and_flag_shared_agent() -> None:
    corpus = Corpus(
        filings=[
            _filing(
                "permits/m.sos.yaml",
                name="Magenta Capital LLC",
                agent="Corporation Service Company",
                agent_addr="1160 Dublin Rd",
                organizer="Michael Montfort",
                juris="Delaware",
            ),
            _filing(
                "permits/t.sos.yaml",
                name="Tilted Gate LLC",
                agent="Corporation Service Company",
                agent_addr="1160 Dublin Rd",
                organizer="Michael Montfort",
                juris="Delaware",
            ),
            _filing(
                "permits/b.sos.yaml",
                name="Bistrozzi Addition LLC",
                agent="C T Corporation",
                agent_addr="4400 East Commons Way",
                organizer="Scott J. Ziance",
                juris="Delaware",
            ),
        ]
    )
    graph = build_entity_graph(corpus)

    # The Delaware foreign filing upgrades each LLC to out-of-state.
    magenta = graph.get("Magenta Capital LLC")
    assert magenta is not None
    assert magenta.classification == "corporate_out_of_state"
    assert "delaware" in magenta.signals

    # Magenta + Tilted share an agent → both flagged; Bistrozzi Addition is not.
    assert "shared_agent" in graph.get("Magenta Capital LLC").signals
    assert "shared_agent" in graph.get("Tilted Gate LLC").signals
    assert "shared_agent" not in graph.get("Bistrozzi Addition LLC").signals

    # One organizer (Montfort) appears on two filings.
    montfort = graph.get("Michael Montfort")
    assert montfort is not None and montfort.roles["organizer"] == 2

    rels = {(r.src, r.rel, r.dst) for r in graph.relationships}
    assert ("MAGENTA CAPITAL", "organized_by", "MICHAEL MONTFORT") in rels
    assert ("TILTED GATE", "registered_agent", "CORPORATION SERVICE") in rels


def test_epa_action_links_to_same_applicant_entity() -> None:
    # A deed grantee and an EPA-permit applicant with the same name resolve to ONE
    # entity carrying both roles — the land thread and the regulatory thread meet.
    corpus = Corpus(
        deeds=[
            _deed(
                "recorder/a.deed.yaml",
                no="I1",
                grantor="Neff Farms",
                grantee="BISTROZZI LLC",
                parcels=["P1"],
            ),
        ],
        actions=[
            (
                "permits/pti.epa.yaml",
                EpaExtraction(
                    doc_id="e",
                    source_path="/x/pti.pdf",
                    kind="epa",
                    dpi=150,
                    action=EpaPermitAction(
                        agency="Ohio EPA",
                        program="Surface Water Permit-to-Install",
                        permit_no="DSWPTI-260294",
                        action="approved",
                        action_date="2026-04-07",
                        applicant="Bistrozzi LLC",
                        project_name="BOSC-1A",
                        contact_name="Scott Ziance",
                        contact_firm="Vorys",
                    ),
                ),
            ),
        ],
    )
    graph = build_entity_graph(corpus)
    bistrozzi = graph.get("BISTROZZI LLC")
    assert bistrozzi is not None
    assert bistrozzi.roles["grantee"] == 1
    assert bistrozzi.roles["epa_applicant"] == 1  # same node, both threads
    rels = {(r.src, r.rel, r.dst) for r in graph.relationships}
    assert ("BISTROZZI", "represented_by", "SCOTT ZIANCE") in rels
    assert ("SCOTT ZIANCE", "affiliated_with", "VORYS") in rels


def _epa(rel: str, *, applicant: str) -> tuple[str, EpaExtraction]:
    return rel, EpaExtraction(
        doc_id=rel,
        source_path=f"/x/{rel}",
        kind="epa",
        dpi=150,
        action=EpaPermitAction(
            agency="USACE",
            program="Section 404",
            applicant=applicant,
            action="application",
            action_date="2026-04-01",
        ),
    )


def test_epa_multi_value_contacts_split_into_separate_nodes() -> None:
    rel = "permits/x.epa.yaml"
    corpus = Corpus(
        actions=[
            (
                rel,
                EpaExtraction(
                    doc_id="x",
                    source_path=f"/x/{rel}",
                    kind="epa",
                    dpi=150,
                    action=EpaPermitAction(
                        agency="USACE",
                        program="Section 404",
                        applicant="Tilted Gate LLC",
                        action="application",
                        action_date="2026-04-01",
                        contact_name="Heather Dardinger; Scott J. Ziance",
                        contact_firm="EMH&T; Vorys, Sater, Seymour, and Pease",
                    ),
                ),
            ),
        ]
    )
    graph = build_entity_graph(corpus)
    # Two distinct contacts, not one conflated node.
    assert graph.get("Heather Dardinger") is not None
    assert graph.get("Scott Ziance") is not None  # middle initial dropped
    assert graph.get("Heather Dardinger; Scott J. Ziance") is None
    rels = {(r.src, r.rel, r.dst) for r in graph.relationships}
    # The firm with internal commas resolves to VORYS, not a combined junk node.
    assert ("HEATHER DARDINGER", "affiliated_with", "VORYS") in rels
    assert ("SCOTT ZIANCE", "affiliated_with", "EMH&T") in rels


def test_person_org_applicant_splits_into_principal_edge() -> None:
    # Two letters name the applicant as "<person>, Tilted Gate LLC" with different
    # people; both must resolve to ONE Tilted Gate org with two principal edges.
    corpus = Corpus(
        actions=[
            _epa("permits/a.epa.yaml", applicant="Randy Barrera, Tilted Gate LLC"),
            _epa("permits/b.epa.yaml", applicant="Timothy Chadwick, Tilted Gate, LLC"),
        ]
    )
    graph = build_entity_graph(corpus)
    tilted = graph.get("Tilted Gate LLC")
    assert tilted is not None and tilted.kind == "corporate"
    assert tilted.roles["epa_applicant"] == 2  # de-fragmented, not split across variants
    rels = {(r.src, r.rel, r.dst) for r in graph.relationships}
    assert ("RANDY BARRERA", "principal_of", "TILTED GATE") in rels
    assert ("TIMOTHY CHADWICK", "principal_of", "TILTED GATE") in rels
    # The person node is an individual, not the conflated corporate "Person, LLC".
    barrera = graph.get("Randy Barrera")
    assert barrera is not None and barrera.kind == "individual"
