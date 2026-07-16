"""Tests for the yidam corpus-mirror MCP backend (#1563).

The backend serves the projected yidam mirror (``yidam://corpus/*``) to the research agent as
in-process tools. The pure serving functions are unit-tested over a hand-built mirror; the tools
and the ``open-questions`` parity are exercised against the real Lima mirror (offline read of the
committed corpus).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from watermark.agent import yidam_tools
from watermark.config import Settings
from watermark.site.corpus_mirror import (
    Mirror,
    MirrorLink,
    MirrorNode,
    build_mirror,
    render_open_questions,
    write_mirror,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _tiny_mirror() -> Mirror:
    """A minimal, graph-check-clean mirror: an anchor, one hypothesis, one open lead."""
    anchor = MirrorNode(
        "artifact",
        "site-demo",
        label="Demo",
        description="A demo watershed-point site.",
        meta={"site": "demo", "scope": "site", "kind": "site"},
        links=[MirrorLink("../hypothesis/water.yml", "assessed-under")],
    )
    hyp = MirrorNode(
        "hypothesis",
        "water",
        label="H1 · Water",
        description="The data-center boom is a water story.",
        meta={"site": "demo", "scope": "network", "number": "H1"},
        links=[MirrorLink("../artifact/site-demo.yml", "assessed-at")],
    )
    lead = MirrorNode(
        "question",
        "lead-cooling",
        label="Cooling-water intake for the campus",
        description="Investigate the cooling-water source and volume.",
        meta={"site": "demo", "claim_tag": "open", "lead_kind": "water"},
        links=[MirrorLink("../artifact/site-demo.yml", "on-site")],
    )
    return Mirror(site="demo", nodes=[anchor, hyp, lead])


# --- pure serving functions -----------------------------------------------------------------
def test_node_uri_and_normalize_id_round_trip() -> None:
    mirror = _tiny_mirror()
    hyp = mirror.nodes[1]
    assert yidam_tools.node_uri(hyp) == "yidam://corpus/hypothesis/water"
    # URI, bare id, a `.yml`-suffixed / slash-wrapped path, and a rendered cross-class link
    # target (`../<class>/<name>.yml`) all normalize to the canonical id.
    for raw in (
        "yidam://corpus/hypothesis/water",
        "hypothesis/water",
        "/hypothesis/water/",
        "hypothesis/water.yml",
        "../hypothesis/water.yml",
    ):
        assert yidam_tools.normalize_id(raw) == "hypothesis/water"


def test_find_node_accepts_uri_bare_id_and_unique_name() -> None:
    mirror = _tiny_mirror()
    hyp = mirror.nodes[1]
    assert yidam_tools.find_node(mirror, "yidam://corpus/hypothesis/water") is hyp
    assert yidam_tools.find_node(mirror, "hypothesis/water") is hyp
    assert yidam_tools.find_node(mirror, "water") is hyp  # unique bare name
    # A rendered cross-class link target resolves to its node.
    assert yidam_tools.find_node(mirror, "../hypothesis/water.yml") is hyp
    assert yidam_tools.find_node(mirror, "no/such-node") is None


def test_list_nodes_orders_and_filters_by_class() -> None:
    mirror = _tiny_mirror()
    assert [n.id for n in yidam_tools.list_nodes(mirror)] == [
        "artifact/site-demo",
        "hypothesis/water",
        "question/lead-cooling",
    ]
    only_q = yidam_tools.list_nodes(mirror, node_class="question")
    assert [n.id for n in only_q] == ["question/lead-cooling"]


def test_query_ranks_label_over_meta_and_honours_class_filter() -> None:
    mirror = _tiny_mirror()
    hits = yidam_tools.query_nodes(mirror, "cooling water")
    assert hits and hits[0].id == "question/lead-cooling"  # label + description both match
    # A class filter that excludes the only match yields nothing.
    assert yidam_tools.query_nodes(mirror, "cooling", node_class="hypothesis") == []
    # An empty query matches nothing (no accidental full dump).
    assert yidam_tools.query_nodes(mirror, "   ") == []


def test_query_limit_is_validated_not_max_of_one() -> None:
    mirror = _tiny_mirror()
    # A non-positive limit returns nothing (not a silent single result via max(1, limit)).
    assert yidam_tools.query_nodes(mirror, "site", limit=0) == []
    assert yidam_tools.query_nodes(mirror, "site", limit=-5) == []
    # A positive limit truncates; the cap bounds even an absurd request.
    assert len(yidam_tools.query_nodes(mirror, "site", limit=1)) == 1
    assert (
        len(yidam_tools.query_nodes(mirror, "site", limit=10_000)) <= yidam_tools._MAX_QUERY_RESULTS
    )


def test_open_question_nodes_flags_the_claim_tag_marker() -> None:
    mirror = _tiny_mirror()
    opens = yidam_tools.open_question_nodes(mirror)
    assert [n.id for n in opens] == ["question/lead-cooling"]


# --- the tools (async handlers, MCP content shape) ------------------------------------------
@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    yidam_tools.clear_mirror_cache()


async def test_tools_serve_the_tiny_mirror(monkeypatch: pytest.MonkeyPatch) -> None:
    mirror = _tiny_mirror()
    monkeypatch.setattr(yidam_tools, "_mirror", lambda settings=None: mirror)

    listed = (await yidam_tools.yidam_list_nodes.handler({}))["content"][0]["text"]
    assert "## hypothesis" in listed and "yidam://corpus/artifact/site-demo" in listed

    filtered = (await yidam_tools.yidam_list_nodes.handler({"node_class": "question"}))["content"][
        0
    ]["text"]
    assert "lead-cooling" in filtered and "site-demo" not in filtered

    bad = (await yidam_tools.yidam_list_nodes.handler({"node_class": "bogus"}))["content"][0][
        "text"
    ]
    assert "Unknown node_class" in bad

    read = (await yidam_tools.yidam_read_node.handler({"id": "yidam://corpus/hypothesis/water"}))[
        "content"
    ][0]["text"]
    assert read.startswith("# yidam://corpus/hypothesis/water")
    assert "class: hypothesis" in read and "assessed-at" in read

    miss = (await yidam_tools.yidam_read_node.handler({"id": "no/such"}))["content"][0]["text"]
    assert "No corpus node" in miss

    q = (await yidam_tools.yidam_query.handler({"query": "cooling"}))["content"][0]["text"]
    assert "yidam://corpus/question/lead-cooling" in q
    assert (await yidam_tools.yidam_query.handler({"query": ""}))["content"][0][
        "text"
    ] == "Pass a non-empty 'query'."

    opens = (await yidam_tools.yidam_open_questions.handler({}))["content"][0]["text"]
    assert "Cooling-water intake for the campus" in opens


async def test_read_node_follows_a_rendered_cross_class_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The agent follows links straight from a node's rendered YAML: a cross-class edge reads
    # `../artifact/site-demo.yml`. Feeding that verbatim back to read_node must resolve to the
    # canonical id, not 404.
    mirror = _tiny_mirror()
    monkeypatch.setattr(yidam_tools, "_mirror", lambda settings=None: mirror)

    hyp = (await yidam_tools.yidam_read_node.handler({"id": "hypothesis/water"}))["content"][0][
        "text"
    ]
    target = re.search(r"target:\s*(\.\./artifact/\S+\.yml)", hyp)
    assert target, "the hypothesis node should render a `../artifact/...` link"

    followed = (await yidam_tools.yidam_read_node.handler({"id": target.group(1)}))["content"][0][
        "text"
    ]
    assert followed.startswith("# yidam://corpus/artifact/site-demo")
    assert "label: Demo" in followed


def test_mirror_is_built_once_and_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}
    mirror = _tiny_mirror()

    def _fake_build(settings: object) -> Mirror:
        calls["n"] += 1
        return mirror

    monkeypatch.setattr(yidam_tools, "build_mirror", _fake_build)
    settings = Settings(site="lima", data_dir=REPO_ROOT / "data")
    assert yidam_tools._mirror(settings) is mirror
    assert yidam_tools._mirror(settings) is mirror
    assert calls["n"] == 1  # second call served from cache


# --- against the real Lima mirror (offline read of the committed corpus) --------------------
def test_serves_the_real_lima_mirror_end_to_end() -> None:
    settings = Settings(site="lima", data_dir=REPO_ROOT / "data")
    mirror = build_mirror(settings)
    assert mirror.site == "lima" and len(mirror.nodes) > 20

    anchor = yidam_tools.find_node(mirror, "artifact/site-lima")
    assert anchor is not None and anchor.label
    # The site anchor links out to the network hypothesis lenses (the always-present spine).
    assert any("hypothesis/" in link.target for link in anchor.links)

    # A keyword query returns real, readable hits.
    hits = yidam_tools.query_nodes(mirror, "water", limit=5)
    assert hits and all(h.label for h in hits)


def test_open_questions_parity_with_the_disk_render(tmp_path: Path) -> None:
    # The in-memory open set must equal what `yidam open-questions` renders over the written
    # mirror — same predicate, projected vs. walked.
    settings = Settings(site="lima", data_dir=REPO_ROOT / "data")
    mirror = build_mirror(settings)
    write_mirror(mirror, tmp_path)

    disk_render = render_open_questions(tmp_path)
    disk_paths = set(re.findall(r"\(([^)]+\.yml)\)", disk_render))
    mem_paths = {f"{n.node_class}/{n.name}.yml" for n in yidam_tools.open_question_nodes(mirror)}
    assert mem_paths == disk_paths
    assert mem_paths  # Lima has open leads / [open] claims, so this is non-trivial
