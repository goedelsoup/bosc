"""Tests for the yidam corpus-mirror MCP backend (#1563).

The backend serves the projected yidam mirror (``yidam://corpus/*``) to the research agent as
in-process tools. The pure serving functions are unit-tested over a hand-built mirror; the tools
and the ``open-questions`` parity are exercised against the real Lima mirror (offline read of the
committed corpus).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from watermark.agent import yidam_tools
from watermark.config import Settings
from watermark.site import yidam_cli
from watermark.site.corpus_mirror import (
    Mirror,
    MirrorLink,
    MirrorNode,
    build_mirror,
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
        meta={"site": "demo", "claim_tag": "[open]", "lead_kind": "water"},
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


def test_open_question_nodes_uses_the_frozen_two_arm_predicate() -> None:
    """`? ` label OR an `[open]` claim in the serialized text — and no third arm.

    BOSC used to carry one keyed on the structured `claim_tag`. The mirror now serializes the
    bracketed token (`corpus_mirror._claim_token`), so the tag IS the text and the second arm
    already covers it; the contract forbids widening the predicate beyond these two."""
    mirror = _tiny_mirror()
    opens = yidam_tools.open_question_nodes(mirror)
    assert [n.id for n in opens] == ["question/lead-cooling"]


# --- the tools (async handlers, MCP content shape) ------------------------------------------
@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    yidam_tools.clear_mirror_cache()


async def _call(name: str, args: dict[str, object]) -> dict[str, Any]:
    """Invoke a served tool and parse its JSON envelope (the contract's shape)."""
    handler = next(t for t in yidam_tools.ALL_TOOLS if t.name == name)
    result = await handler.handler(args)
    assert not result.get("isError"), result["content"][0]["text"]
    return dict(json.loads(result["content"][0]["text"]))


async def test_tools_serve_the_tiny_mirror(monkeypatch: pytest.MonkeyPatch) -> None:
    mirror = _tiny_mirror()
    monkeypatch.setattr(yidam_tools, "_mirror", lambda settings=None: mirror)

    listed = await _call("list_nodes", {})
    assert {n["id"] for n in listed["nodes"]} >= {"artifact/site-demo", "hypothesis/water"}
    assert all(set(n) >= {"id", "class", "label", "description"} for n in listed["nodes"])

    filtered = await _call("list_nodes", {"class": "question"})
    assert [n["id"] for n in filtered["nodes"]] == ["question/lead-cooling"]

    handler = next(t for t in yidam_tools.ALL_TOOLS if t.name == "list_nodes")
    bad = await handler.handler({"class": "bogus"})
    assert bad.get("isError") and "unknown class" in bad["content"][0]["text"]

    node = await _call("get_node", {"id": "yidam://corpus/hypothesis/water"})
    assert node["id"] == "hypothesis/water" and node["class"] == "hypothesis"
    assert "assessed-at" in {link["relationship"] for link in node["links"]}

    get_node = next(t for t in yidam_tools.ALL_TOOLS if t.name == "get_node")
    miss = await get_node.handler({"id": "no/such"})
    assert miss.get("isError") and "not found" in miss["content"][0]["text"]

    hits = await _call("retrieve", {"query": "cooling"})
    assert hits["degraded"] is True  # no index built for the tiny mirror
    assert hits["results"][0]["path"] == ".yidam/corpus/question/lead-cooling.yml"

    # A blank query is an ABSENCE, not an error (contract 0.4.0). It used to be `isError`, and
    # the change is the tool doing its job: an agent that passed an empty string gets back the
    # size of the corpus it failed to search, which it can act on. A refusal is a dead end.
    empty = await _call("retrieve", {"query": "  "})
    assert empty["absence"]["code"] == "query-no-terms"
    assert empty["absence"]["instances"] == len(mirror.nodes)
    assert empty["rejected"] is None and empty["results"] == []

    opens = await _call("open_questions", {})
    assert [q["label"] for q in opens["open_questions"]] == ["Cooling-water intake for the campus"]
    assert opens["open_questions"][0]["path"] == ".yidam/corpus/question/lead-cooling.yml"


async def test_get_node_follows_a_rendered_cross_class_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The agent follows links straight out of a node's `links[]`: a cross-class edge reads
    # `../artifact/site-demo.yml`. Feeding that verbatim back to get_node must resolve to the
    # canonical id, not 404.
    mirror = _tiny_mirror()
    monkeypatch.setattr(yidam_tools, "_mirror", lambda settings=None: mirror)

    hyp = await _call("get_node", {"id": "hypothesis/water"})
    target = next(
        link["target"] for link in hyp["links"] if link["target"].startswith("../artifact/")
    )
    followed = await _call("get_node", {"id": target})
    assert followed["id"] == "artifact/site-demo" and followed["label"] == "Demo"


async def test_neighbors_walks_the_tiny_mirror_both_ways(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`question/lead-cooling` links *to* the anchor and is pointed at by nothing, so reaching
    it from the anchor at all requires walking that edge backwards — the half a directed
    implementation silently loses. The hypothesis, which the anchor links out to, is reached
    the easy way; both must appear."""
    mirror = _tiny_mirror()
    monkeypatch.setattr(yidam_tools, "_mirror", lambda settings=None: mirror)

    body = await _call("neighbors", {"id": "artifact/site-demo"})
    assert body["id"] == "artifact/site-demo"
    reached = {n["id"]: n for n in body["neighbors"]}
    assert reached["question/lead-cooling"]["direction"] == "in"
    assert reached["hypothesis/water"]["direction"] == "out"
    assert all(n["depth"] == 1 for n in body["neighbors"])


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


# --- the vector arm of `retrieve` (#1564), served through the MCP backend -------------------
async def test_retrieve_uses_the_vector_arm_when_an_index_is_built(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from tests.test_yidam_index import _BagProvider

    mirror = _tiny_mirror()
    monkeypatch.setattr(yidam_tools, "_mirror", lambda settings=None: mirror)
    monkeypatch.setattr(yidam_tools, "default_index_dir", lambda settings=None: tmp_path / "index")
    monkeypatch.setattr(
        "watermark.retrieval.embeddings.get_provider", lambda settings: _BagProvider()
    )

    # Build it deliberately — `retrieve` must NOT create one as a side effect of being called.
    yidam_tools._index().build(mirror)
    assert yidam_tools.vector_ready()

    body = await _call("retrieve", {"query": "cooling water intake"})
    assert body["degraded"] is False
    assert body["results"][0]["path"] == ".yidam/corpus/question/lead-cooling.yml"


async def test_retrieve_degrades_rather_than_building_an_index_on_demand(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The behaviour the frozen contract rules out.

    The old `semantic_search` embedded the whole mirror on first call, so an agent's first
    search silently answered from a vector space that had not existed a moment earlier — and
    one whose weights differ from yidam's (RFC-0006). Now it says `degraded: true` and leaves
    the index to `mise run corpus-vector-index`.
    """
    mirror = _tiny_mirror()
    monkeypatch.setattr(yidam_tools, "_mirror", lambda settings=None: mirror)
    monkeypatch.setattr(yidam_tools, "default_index_dir", lambda settings=None: tmp_path / "index")

    body = await _call("retrieve", {"query": "cooling"})
    assert body["degraded"] is True
    assert not (tmp_path / "index").exists(), "retrieve built an index as a side effect"


async def test_retrieve_answers_a_bad_call_instead_of_refusing_it() -> None:
    """Neither arm is an `isError` any more, and the two are deliberately different shapes.

    A blank query is an `absence` — the corpus was searchable and the call brought nothing to
    search it with. An undeclared class is a `rejected` — the call named something this corpus
    does not have. Different repairs, and `rejected`/`absence` are mutually exclusive because
    of it. Both carry enough for the caller to fix the call without a second round trip.
    """
    retrieve = next(t for t in yidam_tools.ALL_TOOLS if t.name == "retrieve")

    empty = json.loads((await retrieve.handler({"query": "  "}))["content"][0]["text"])
    assert empty["absence"]["code"] == "query-no-terms" and empty["rejected"] is None

    bad = json.loads(
        (await retrieve.handler({"query": "x", "class": "bogus"}))["content"][0]["text"]
    )
    assert bad["rejected"]["code"] == "unknown-class" and bad["absence"] is None
    assert "bogus" in bad["rejected"]["detail"], "the rejection must name what was rejected"


# --- against the real Lima mirror (offline read of the committed corpus) --------------------
def test_serves_the_real_lima_mirror_end_to_end() -> None:
    settings = Settings(site="lima", data_dir=REPO_ROOT / "data")
    mirror = build_mirror(settings)
    assert mirror.site == "lima" and len(mirror.nodes) > 20

    anchor = yidam_tools.find_node(mirror, "artifact/site-lima")
    assert anchor is not None and anchor.label
    # The site anchor links out to the network hypothesis nodes (the always-present spine).
    assert any("hypothesis/" in link.target for link in anchor.links)

    # A keyword query returns real, readable hits.
    hits = yidam_tools.query_nodes(mirror, "water", limit=5)
    assert hits and all(h.label for h in hits)


@pytest.mark.skipif(not yidam_cli.usable(), reason="no yidam binary that speaks --format json")
def test_open_questions_conformance_with_the_real_binary(tmp_path: Path) -> None:
    """BOSC's in-memory open-question predicate must return the same set as ``yidam
    open-questions`` over the same mirror.

    This is the conformance test the Python replica could never be: it runs the *actual*
    upstream rule (a raw-text scan for the literal ``[open]``, plus a ``?``-prefixed label)
    rather than a re-implementation of it that claimed faithfulness in a docstring. It is what
    caught, and now guards, the divergence that had the binary reporting 2 open questions where
    BOSC reported 26 — the mirror was storing a bare ``open`` where the token was required.

    Skipped when the binary is absent so an offline checkout still runs green; CI installs it,
    so the gate is real there (``.github/workflows/ci.yml``, the ``corpus`` job).
    """
    settings = Settings(site="lima", data_dir=REPO_ROOT / "data")
    mirror = build_mirror(settings)
    corpus = tmp_path / ".yidam" / "corpus"
    write_mirror(mirror, corpus)

    report = yidam_cli.run_report("open-questions", root=tmp_path)
    binary_paths = {
        str(q["node"]).split(".yidam/corpus/", 1)[-1] for q in report.payload["open_questions"]
    }
    mem_paths = {f"{n.node_class}/{n.name}.yml" for n in yidam_tools.open_question_nodes(mirror)}
    assert mem_paths == binary_paths
    assert mem_paths  # Lima has open leads / [open] claims, so this is non-trivial


# --- the CLI's --site flag must survive importing this module ------------------------------
def test_importing_the_cli_never_resolves_settings() -> None:
    """`watermark --site <slug>` is silently ignored if anything calls `get_settings()` while
    the CLI is being imported.

    The global `--site` callback writes `WATERMARK_SITE` and then resolves settings — but
    `get_settings` is `lru_cache`d, so an import-time call caches the DEFAULT site first and
    the flag becomes decorative. It regressed exactly that way: `ALL_TOOLS` was built at module
    scope from `capabilities()`, which asked whether a vector index existed *for the active
    site*, and `watermark --site west-union corpus-mirror` wrote Lima's mirror without a word.

    Silently serving one site's corpus under another site's flag is the worst failure this
    repo has, so the invariant is asserted rather than remembered.
    """
    import importlib
    import subprocess
    import sys

    probe = (
        "import watermark.config as c\n"
        "orig = c.get_settings\n"
        "calls = []\n"
        "c.get_settings = lambda *a, **k: (calls.append(1), orig(*a, **k))[1]\n"
        "import watermark.cli  # noqa: F401\n"
        "print(len(calls))\n"
    )
    # A subprocess, because this test suite has already imported the CLI: the question is what
    # a *fresh* interpreter does, which is what the `watermark` entry point actually is.
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "0", (
        "something calls get_settings() while `watermark.cli` is imported, so the cached "
        "Settings resolve the DEFAULT site and `--site` is ignored"
    )
    importlib.invalidate_caches()


def test_served_tool_names_needs_no_settings() -> None:
    """The narrow invariant behind the test above: the served list is a function of the static
    capabilities alone. `retrieve.vector` describes an index's state, not whether a tool
    exists, so deciding the list must never reach for the active site."""
    import inspect

    assert not inspect.signature(yidam_tools.served_tool_names).parameters
    assert "neighbors" in yidam_tools.served_tool_names()
