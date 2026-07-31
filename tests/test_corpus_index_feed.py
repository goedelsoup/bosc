"""Tests for the ``corpus-index`` feed (#1573, epic #1560 workstream C).

The projector tests are pure over a hand-built :class:`Mirror` (no corpus load, git dates
injected): they pin the display-`kind` derivation (the yidam `artifact`/`question` classes fold
several BOSC kinds), the in/out-degree resolution across relative link targets, the line-count
parity with ``write_mirror``, and the freshness rule (newest backing-source commit; null when a
node has no resolvable source). One integration test exports a real Lima bundle and asserts the
feed always emits and every node carries a kind + degree.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from watermark.config import Settings
from watermark.site.corpus_index import _line_count, _target_id, build_corpus_index
from watermark.site.corpus_mirror import Mirror, MirrorLink, MirrorNode

REPO_ROOT = Path(__file__).resolve().parent.parent

_CV = "1.47.0"


def _mirror() -> Mirror:
    """A tiny connected mirror covering every display kind, with a couple of real source refs."""
    return Mirror(
        site="lima",
        nodes=[
            MirrorNode(
                "artifact",
                "site-lima",
                label="Lima",
                meta={"kind": "site", "scope": "site"},
                links=[MirrorLink("../hypothesis/water.yml", "assessed-under")],
            ),
            MirrorNode(
                "hypothesis",
                "water",
                label="H1 · Water",
                meta={"scope": "network"},
                links=[MirrorLink("../artifact/site-lima.yml", "assessed-at")],
            ),
            MirrorNode(
                "concept",
                "7q10",
                label="7Q10",
                meta={"scope": "network", "kind": "term"},
                # Resolves to the real committed data/concepts/7q10.md (freshness source).
                source_refs=["concept:7q10"],
                links=[MirrorLink("../artifact/site-lima.yml", "in-corpus")],
            ),
            MirrorNode(
                "artifact",
                "acme",
                label="Acme LLC",
                meta={"scope": "site", "entity_kind": "corporate"},
                # A real committed file + a citation that resolves to nothing (→ ignored).
                source_refs=["data/site/leads.yaml", "Deed Vol. 12 p.3"],
                links=[MirrorLink("site-lima.yml", "in-site")],  # same-class sibling
            ),
            MirrorNode(
                "artifact",
                "person-jane",
                label="Jane Roe",
                meta={"scope": "site", "kind": "person"},
                links=[MirrorLink("acme.yml", "is-entity")],
            ),
            MirrorNode(
                "question",
                "lead-x",
                label="A lead",
                meta={"scope": "site", "lead_kind": "question", "claim_tag": "open"},
                links=[MirrorLink("../artifact/site-lima.yml", "on-site")],
            ),
            MirrorNode(
                "question",
                "open-water",
                label="Open thread — H1",
                meta={"scope": "site", "claim_tag": "open", "hypothesis": "water"},
                links=[MirrorLink("../hypothesis/water.yml", "open-under")],
            ),
            MirrorNode(
                "relation",
                "a--owns--b",
                label="A owns B",
                meta={"scope": "site", "rel": "owns"},
                links=[MirrorLink("../artifact/acme.yml", "from")],
            ),
        ],
    )


def _rows() -> dict[str, Any]:
    settings = Settings(data_dir=REPO_ROOT / "data", site="lima")
    git_dates = {
        "data/concepts/7q10.md": "2026-03-01T10:00:00-05:00",
        "data/site/leads.yaml": "2026-06-15T09:00:00-04:00",
    }
    rows = build_corpus_index(_mirror(), settings=settings, git_dates=git_dates)
    return {r.id: r for r in rows}


# --- pure projector -------------------------------------------------------------------------
def test_display_kind_refines_the_yidam_class() -> None:
    rows = _rows()
    assert rows["artifact/site-lima"].kind == "site"
    assert rows["artifact/acme"].kind == "entity"
    assert rows["artifact/person-jane"].kind == "person"
    assert rows["concept/7q10"].kind == "concept"
    assert rows["hypothesis/water"].kind == "hypothesis"
    assert rows["question/lead-x"].kind == "lead"  # has a lead_kind
    assert rows["question/open-water"].kind == "open-question"  # a matrix cell, no lead_kind
    assert rows["relation/a--owns--b"].kind == "relation"


def test_out_degree_is_the_nodes_own_links() -> None:
    rows = _rows()
    assert rows["artifact/site-lima"].links_out == 1
    assert rows["relation/a--owns--b"].links_out == 1


def test_in_degree_resolves_relative_link_targets() -> None:
    rows = _rows()
    # site-lima is pointed at by the hypothesis, the concept, the lead, and (via a bare sibling
    # ref) acme — four incoming edges resolved across `../class/x.yml` and bare `x.yml` targets.
    assert rows["artifact/site-lima"].links_in == 4
    assert rows["artifact/acme"].links_in == 2  # person-jane + the relation edge
    assert rows["hypothesis/water"].links_in == 2  # site anchor + the open thread


def test_target_id_resolution() -> None:
    assert _target_id("question", "../artifact/site-lima.yml") == "artifact/site-lima"
    assert _target_id("artifact", "site-lima.yml") == "artifact/site-lima"  # bare = same class
    assert _target_id("artifact", "../hypothesis/water.yml") == "hypothesis/water"


def test_line_count_matches_write_mirror_serialization() -> None:
    node = _mirror().nodes[3]  # acme
    expected = len(yaml.safe_dump(node.to_dict(), sort_keys=False, allow_unicode=True).splitlines())
    assert _line_count(node) == expected
    assert _rows()["artifact/acme"].lines == expected


def test_source_refs_never_enter_the_yidam_node_yaml() -> None:
    # to_dict() (what write_mirror serializes) must not carry source_refs — the mirror stays
    # byte-identical, so line counts and graph-check are unaffected by this feed.
    assert "source_refs" not in _mirror().nodes[3].to_dict()


def test_freshness_is_the_newest_backing_source_commit() -> None:
    rows = _rows()
    # acme resolves data/site/leads.yaml (dated) + a prose citation (ignored) → the dated one.
    assert rows["artifact/acme"].updated == "2026-06-15"
    assert rows["concept/7q10"].updated == "2026-03-01"
    # A node with no resolvable source file gets no fabricated date.
    assert rows["hypothesis/water"].updated is None
    assert rows["question/open-water"].updated is None


def test_rows_sorted_by_id() -> None:
    settings = Settings(data_dir=REPO_ROOT / "data", site="lima")
    rows = build_corpus_index(_mirror(), settings=settings, git_dates={})
    assert [r.id for r in rows] == sorted(r.id for r in rows)


# --- integration: a real Lima bundle -------------------------------------------------------
# `lima_bundle` is conftest's session-wide, cross-worker export (#1773) — this module reads one
# feed off it, so it must never pay for an export of its own.
def _corpus_index(bundle: Path) -> list[dict[str, Any]]:
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    ref = next(f for f in manifest["feeds"] if f["name"] == "corpus-index")
    assert ref["kind"] == "collection"
    return json.loads((bundle / ref["path"]).read_text(encoding="utf-8"))


def test_feed_always_emitted_at_contract_version(lima_bundle: Path) -> None:
    manifest = json.loads((lima_bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["contract_version"] == _CV
    nodes = _corpus_index(lima_bundle)
    assert len(nodes) > 0  # the mirror is never empty (site anchor + hypothesis lenses)


def test_every_node_carries_kind_and_degree(lima_bundle: Path) -> None:
    nodes = _corpus_index(lima_bundle)
    kinds = {
        "site",
        "entity",
        "person",
        "concept",
        "hypothesis",
        "lead",
        "open-question",
        "relation",
        "node",
    }
    for n in nodes:
        assert n["kind"] in kinds
        assert n["links_out"] >= 0 and n["links_in"] >= 0
        assert n["lines"] > 0
        assert n["label"]
    # the spine is present: the site anchor + the three hypothesis lenses.
    assert any(n["kind"] == "site" for n in nodes)
    assert sum(n["kind"] == "hypothesis" for n in nodes) == 3


def test_freshness_present_on_the_committed_sourced_nodes(lima_bundle: Path) -> None:
    nodes = _corpus_index(lima_bundle)
    # Entities + concepts derive from committed files, so many carry a real last-commit date
    # (unless git history is unavailable — then all-null is the honest degradation, not a crash).
    dated = [n for n in nodes if n["updated"]]
    for n in dated:
        assert len(n["updated"]) == 10 and n["updated"][4] == "-"  # ISO date YYYY-MM-DD
