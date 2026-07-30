"""Tests for the ``corpus-nodes`` retrieval feed (#1575, epic #1560 workstream D2).

The projector tests are pure over a hand-built :class:`Mirror` (no corpus load): they pin the
evidence-tag normalization (only the real `[verified]`/`[inference]`/`[reference]`/`[open]` tags
survive, brackets stripped; a structural node asserts none), the concept-slug `ref` extraction from
the `concept:<slug>` source ref, the undirected 1-hop `neighbors` resolution (out-links plus
in-links, self excluded), and that `text` is the canonical `node_text` (so the lexical feed and the
semantic index tokenize the same content). One integration test exports a real Lima bundle and
asserts the feed always emits, at the bumped contract version, with a searchable text per node.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from watermark.site.corpus_mirror import Mirror, MirrorLink, MirrorNode, node_text
from watermark.site.corpus_nodes import build_corpus_nodes

REPO_ROOT = Path(__file__).resolve().parent.parent

_CV = "1.44.0"


def _mirror() -> Mirror:
    """A tiny connected mirror: a concept, an entity that names it, an open question, a relation."""
    return Mirror(
        site="lima",
        nodes=[
            MirrorNode(
                "concept",
                "dilution",
                label="Dilution",
                description="Mixing of an effluent with receiving water.",
                meta={"scope": "network", "kind": "term", "aliases": ["dilution ratio"]},
                source_refs=["concept:dilution"],
                links=[MirrorLink("7q10.yml", "related")],  # sibling concept
            ),
            MirrorNode(
                "concept",
                "7q10",
                label="7Q10",
                description="The design low flow.",
                meta={"scope": "network"},
                source_refs=["concept:7q10"],
                links=[MirrorLink("dilution.yml", "related")],
            ),
            MirrorNode(
                "artifact",
                "acme",
                label="Acme LLC",
                description="A permittee whose dilution factor is contested.",
                meta={"scope": "site", "kind": "entity"},
                links=[MirrorLink("../concept/dilution.yml", "concerns")],
            ),
            MirrorNode(
                "question",
                "open-flow",
                label="What is the design low flow?",
                meta={"scope": "site", "claim_tag": "open"},
                links=[MirrorLink("../concept/7q10.yml", "raises")],
            ),
            MirrorNode(
                "question",
                "lead-permit",
                label="Chase the permit's dilution basis",
                meta={"scope": "site", "lead_kind": "permit", "claim_tag": "[inference]"},
                links=[MirrorLink("../artifact/acme.yml", "about")],
            ),
        ],
    )


def _by_id(rows: list[Any]) -> dict[str, Any]:
    return {r.id: r for r in rows}


def test_ref_is_the_concept_slug_for_concept_nodes_and_none_otherwise() -> None:
    rows = _by_id(build_corpus_nodes(_mirror()))
    assert rows["concept/dilution"].ref == "dilution"
    assert rows["concept/7q10"].ref == "7q10"
    assert rows["artifact/acme"].ref is None
    assert rows["question/open-flow"].ref is None


def test_evidence_normalizes_only_real_tags_and_strips_brackets() -> None:
    rows = _by_id(build_corpus_nodes(_mirror()))
    assert rows["question/open-flow"].evidence == "open"  # claim_tag "open"
    assert rows["question/lead-permit"].evidence == "inference"  # "[inference]" → stripped
    # A structural node (a concept, an entity) asserts no evidence — the palette is never spent.
    assert rows["concept/dilution"].evidence is None
    assert rows["artifact/acme"].evidence is None


def test_kind_matches_the_corpus_index_display_kind() -> None:
    rows = _by_id(build_corpus_nodes(_mirror()))
    assert rows["concept/dilution"].kind == "concept"
    assert rows["artifact/acme"].kind == "entity"
    assert rows["question/open-flow"].kind == "open-question"
    assert rows["question/lead-permit"].kind == "lead"  # a question with a lead_kind is a lead


def test_neighbors_are_undirected_resolved_and_self_excluded() -> None:
    rows = _by_id(build_corpus_nodes(_mirror()))
    # dilution ↔ 7q10 (mutual `related`); acme → dilution adds acme as dilution's in-neighbor.
    assert rows["concept/dilution"].neighbors == ["artifact/acme", "concept/7q10"]
    # acme links out to dilution and is linked in by the lead — undirected picks up both directions.
    assert rows["artifact/acme"].neighbors == ["concept/dilution", "question/lead-permit"]
    # No node ever lists itself.
    for row in rows.values():
        assert row.id not in row.neighbors


def test_text_is_the_canonical_node_text() -> None:
    mirror = _mirror()
    rows = _by_id(build_corpus_nodes(mirror))
    node = next(n for n in mirror.nodes if n.id == "concept/dilution")
    assert rows["concept/dilution"].text == node_text(node)
    # The text carries the label + description so the lexical scorer has something to match.
    assert "Dilution" in rows["concept/dilution"].text
    assert "effluent" in rows["concept/dilution"].text


def test_rows_are_sorted_by_id() -> None:
    rows = build_corpus_nodes(_mirror())
    assert [r.id for r in rows] == sorted(r.id for r in rows)


# --- integration: a real Lima bundle -------------------------------------------------------
# `lima_bundle` is conftest's session-wide, cross-worker export (#1773) — this module reads one
# feed off it, so it must never pay for an export of its own.
def _manifest(bundle: Path) -> dict[str, Any]:
    return json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))


def test_feed_always_emitted_at_contract_version(lima_bundle: Path) -> None:
    manifest = _manifest(lima_bundle)
    assert manifest["contract_version"] == _CV
    ref = next(f for f in manifest["feeds"] if f["name"] == "corpus-nodes")
    assert ref["media_type"] == "application/x-ndjson"
    assert ref["count"] > 0  # the mirror is never empty
    rows = [
        json.loads(line)
        for line in (lima_bundle / ref["path"]).read_text().splitlines()
        if line.strip()
    ]
    assert len(rows) == ref["count"]
    # Every node carries a searchable text and its display kind; concept nodes carry a ref.
    assert all(r["text"] and r["kind"] for r in rows)
    concept_rows = [r for r in rows if r["kind"] == "concept"]
    assert concept_rows and all(r["ref"] for r in concept_rows)
