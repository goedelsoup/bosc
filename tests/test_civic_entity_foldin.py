"""Fold subdivision meeting participants into the entity graph (opt-in enrichment)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from watermark.config import Settings
from watermark.pipeline.corpus import Corpus
from watermark.pipeline.entities import build_entity_graph


def _seed(tmp: Path, meetings: list[dict[str, Any]]) -> Settings:
    settings = Settings(data_dir=tmp)
    p = settings.extracted_dir / "american-township" / "meetings" / "meeting-summaries.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        yaml.safe_dump({"meta": {"slug": "american-township"}, "meetings": meetings}), "utf-8"
    )
    return settings


def test_foldin_links_corridor_parties_and_skips_residents(tmp_path: Path) -> None:
    settings = _seed(
        tmp_path,
        [
            {
                "date": "2026-02-09",
                "parties": [
                    "Bistrozzi LLC",
                    "Google",
                    "Turner Construction",
                    "Cindy Leis - Allen Economic Development Group",  # dash affiliation
                    "Allen Economic Development Group",  # canonicalizes with above's org
                    "Blacktop Sealing Inc.",  # routine vendor -> excluded
                    "Jane Q. Public (resident)",
                    "Paul Basinger (Trustee)",
                ],
            },
            {"date": "2026-02-23", "parties": ["Bistrozzi LLC"]},  # recurrence
        ],
    )
    graph = build_entity_graph(Corpus(), enrich_subdivisions=True, settings=settings)

    # The subdivision body is a government node.
    sub = graph.get("American Township")
    assert sub is not None and sub.kind == "government" and sub.classification == "government_local"

    # Corridor orgs / named actors are folded in and linked to the township.
    for name in ("Bistrozzi", "Google", "Turner Construction"):
        ent = graph.get(name)
        assert ent is not None, name
        assert any(
            r.rel == "discussed_at" and r.src == ent.key and r.dst == sub.key
            for r in graph.relationships
        ), name

    # Cindy Leis (dash-affiliation stripped) is her own node, NOT merged into AEDG.
    leis = graph.get("Cindy Leis")
    assert leis is not None and leis.key == "CINDY LEIS"
    # The econ-dev shield canonicalizes to one government node.
    aedg = graph.entities.get("ALLEN ECONOMIC DEVELOPMENT GROUP")
    assert aedg is not None and aedg.kind == "government"

    # Routine vendors and one-off residents/officials are NOT in the resolved graph.
    assert graph.get("Blacktop Sealing") is None
    assert graph.get("Jane Public") is None
    assert graph.get("Paul Basinger") is None

    # Recurrence collapses to one edge but accrues the meeting count in roles.
    bist = graph.get("Bistrozzi")
    assert bist is not None and bist.roles["meeting_participant"] == 2
    assert sum(1 for r in graph.relationships if r.rel == "discussed_at" and r.src == bist.key) == 1
    assert "american-township/meetings/meeting-summaries.yaml" in bist.sources


def test_foldin_links_principal_named_only_in_prose_and_skips_self(tmp_path: Path) -> None:
    # The roster lists committee members + the body itself; the project principal
    # (Google) is named only in the grounded prose — as in the real LACRPC 2026-04-23
    # minutes. Google must still link, and the body naming itself must NOT self-loop.
    settings = Settings(data_dir=tmp_path)
    p = settings.extracted_dir / "lacrpc" / "meetings" / "meeting-summaries.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        yaml.safe_dump(
            {
                "meta": {"slug": "lacrpc"},
                "meetings": [
                    {
                        "date": "2026-04-23",
                        "parties": [
                            "Doug Post, Amanda Township",  # one-off official -> excluded
                            "LACRPC (Lima-Allen County Regional Planning Commission)",  # self
                        ],
                        "corridor_relevance": "Presentation discussed project BOSC (Google "
                        "data center), phased investment and a payment to Elida Schools.",
                        "summary": "Open discussion about data centers.",
                    }
                ],
            }
        ),
        "utf-8",
    )
    graph = build_entity_graph(Corpus(), enrich_subdivisions=True, settings=settings)
    sub = graph.get("Lacrpc")
    assert sub is not None
    google = graph.get("Google")
    assert google is not None
    assert any(
        r.rel == "discussed_at" and r.src == google.key and r.dst == sub.key
        for r in graph.relationships
    )
    # No self-loop from the body naming itself, and the one-off official is excluded.
    assert not any(
        r.rel == "discussed_at" and r.src == sub.key and r.dst == sub.key
        for r in graph.relationships
    )
    assert graph.get("Doug Post") is None


def test_foldin_is_opt_in(tmp_path: Path) -> None:
    settings = _seed(tmp_path, [{"date": "2026-02-09", "parties": ["Bistrozzi LLC"]}])
    # Without the flag, the meeting summaries are not read at all.
    graph = build_entity_graph(Corpus(), settings=settings)
    assert graph.get("American Township") is None
    assert graph.get("Bistrozzi") is None


def test_a_peer_is_not_measured_against_limas_curated_corridor_actors(tmp_path: Path) -> None:
    """The curated actor needles are Allen County's, and a peer must not be read through them
    (#1839).

    They are substring matches on Lima's project actors. Hancock County's *Economic Development
    Advisory Board* contains "ECONOMIC DEVELOPMENT" and was folded into Lima's ALLEN ECONOMIC
    DEVELOPMENT GROUP — putting a Lima entity in Findlay's committed feed, with a `discussed_at`
    edge to Allen Township that came from the phrase "Cooperative Economic Development
    Agreement" in a set of township minutes about a tax-sharing deal with the City of Findlay.
    A peer now folds in only parties that already resolve to its own corpus.
    """
    settings = Settings(data_dir=tmp_path, site="findlay")
    p = (
        settings.extracted_dir
        / "findlay"
        / "allen-township"
        / "meetings"
        / "meeting-summaries.yaml"
    )
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        yaml.safe_dump(
            {
                "meta": {"slug": "allen-township"},
                "meetings": [
                    {
                        "date": "2025-12-02",
                        "parties": ["Economic Development Advisory Board", "One Power Company"],
                        "summary": "A draft Cooperative Economic Development Agreement.",
                        "corridor_relevance": "One Power Company is named as the plaintiff.",
                        "decisions": ["Update the Cooperative Economic Development Agreement."],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    graph = build_entity_graph(Corpus(), enrich_subdivisions=True, settings=settings)

    assert "ALLEN ECONOMIC DEVELOPMENT GROUP" not in graph.entities
    assert not [r for r in graph.relationships if "ECONOMIC DEVELOPMENT" in r.src]
    # Nothing here resolves to Findlay's (empty) corpus, so no party is folded in at all —
    # the honest default. The body itself is only registered once a party links to it.
    assert "ONE POWER COMPANY" not in graph.entities


def test_lima_still_folds_its_own_curated_actors(tmp_path: Path) -> None:
    """The reference build keeps the curated list — gating is per site, not a removal (#1839)."""
    settings = _seed(
        tmp_path,
        [{"date": "2026-02-09", "parties": ["Allen Economic Development Group"], "summary": ""}],
    )
    graph = build_entity_graph(Corpus(), enrich_subdivisions=True, settings=settings)
    assert "ALLEN ECONOMIC DEVELOPMENT GROUP" in graph.entities
