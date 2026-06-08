"""Fold subdivision meeting participants into the entity graph (opt-in enrichment)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from bosc.config import Settings
from bosc.pipeline.corpus import Corpus
from bosc.pipeline.entities import build_entity_graph


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


def test_foldin_is_opt_in(tmp_path: Path) -> None:
    settings = _seed(tmp_path, [{"date": "2026-02-09", "parties": ["Bistrozzi LLC"]}])
    # Without the flag, the meeting summaries are not read at all.
    graph = build_entity_graph(Corpus(), settings=settings)
    assert graph.get("American Township") is None
    assert graph.get("Bistrozzi") is None
