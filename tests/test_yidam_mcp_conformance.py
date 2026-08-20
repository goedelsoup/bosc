"""BOSC's MCP server against the frozen tool contract (RFC-0005).

Two things are checked here, and the second is the one that has teeth.

**The served list is derived, not restated.** `served_tool_names()` reads the vendored
contract and filters by declared capability, so a tool added upstream and not implemented
here fails rather than quietly not existing. A test that listed the five names itself would
be a second freeze — which is precisely how three servers came to share one name out of five.

**The upstream conformance cases run against this server.** `tests/fixtures/yidam-mcp/cases/`
is a verbatim copy of `prelude/sdks/parity/mcp/cases/`, so the assertions are upstream's, not
ones written to match what BOSC already did. Each case carries its own `why`, which is
surfaced on failure — the reason a case exists is usually the thing you need when it breaks.

The cases were written against yidam's own tiny fixture corpus, so they are run here for
their **shape** (fields present, filters filtering, flags flagged) over BOSC's real Lima
mirror; the identity assertions that name yidam's fixture nodes are re-expressed against
nodes this corpus actually has. Where a case asserts a rule rather than a node — the
`degraded` flag, undirected traversal, the frozen predicate's two arms — it is asserted here
in full.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from watermark.agent import yidam_tools
from watermark.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = Path(__file__).parent / "fixtures" / "yidam-mcp" / "cases"


@pytest.fixture(autouse=True)
def _lima(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve the committed Lima corpus, and never a lazily-built vector index."""
    settings = Settings(site="lima", data_dir=REPO_ROOT / "data")
    monkeypatch.setattr(yidam_tools, "get_settings", lambda: settings)
    yidam_tools.clear_mirror_cache()


async def _call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Invoke a served tool and parse its JSON envelope."""
    handler = next(t for t in yidam_tools.ALL_TOOLS if t.name == name)
    result = await handler.handler(args)
    assert not result.get("isError"), result["content"][0]["text"]
    return dict(json.loads(result["content"][0]["text"]))


def _cases() -> list[tuple[str, dict[str, Any]]]:
    return sorted(
        (f"{p.parent.name}/{p.name}", json.loads(p.read_text(encoding="utf-8")))
        for p in CASES_DIR.rglob("*.json")
    )


# --- the contract itself ---------------------------------------------------------------------
def test_the_vendored_contract_is_the_one_this_server_was_written_against() -> None:
    assert yidam_tools.contract()["contract"] == "0.1.0"
    assert (Path(__file__).parent / "fixtures" / "yidam-mcp" / "VERSION").read_text().strip() == (
        yidam_tools.contract()["contract"]
    )


def test_the_served_list_is_derived_from_the_contract() -> None:
    """Every core tool, plus the optional ones this server declares — and nothing else."""
    caps = yidam_tools.capabilities()
    expected = [
        t["name"]
        for t in yidam_tools.contract()["tools"]
        if t.get("tier", "core") == "core" or caps.get(t.get("tier", "core"))
    ]
    assert [t.name for t in yidam_tools.ALL_TOOLS] == expected
    # `graph` is declared, so `neighbors` must be served. It is the capability BOSC most
    # obviously backs — the mirror is a projected entity graph — and the one it used to lack.
    assert "neighbors" in expected


def test_capabilities_are_declared_honestly() -> None:
    caps = yidam_tools.capabilities()
    assert caps["graph"] is True
    # Both need a working yidam repository — live `ma/*` refs and elector positions. BOSC has
    # neither, and projecting its corpus would not produce them.
    assert caps["phases"] is False and caps["sangha"] is False
    # The Agent SDK's in-process servers register tools only; there is no `resources/*` channel.
    assert caps["resources"] is False
    assert isinstance(caps["retrieve"]["vector"], bool)


def test_no_tool_name_carries_the_old_prefix() -> None:
    """The regression this whole exercise exists to prevent."""
    assert not any(t.name.startswith("yidam_") for t in yidam_tools.ALL_TOOLS)
    assert yidam_tools.ALLOWED_TOOL_NAMES[0].startswith("mcp__yidam__")


# --- upstream's cases, run against this server -----------------------------------------------
@pytest.mark.parametrize("case_id,case", _cases(), ids=lambda v: v if isinstance(v, str) else "")
async def test_upstream_case_shape(case_id: str, case: dict[str, Any]) -> None:
    """Every case's *shape* assertions, over BOSC's real corpus."""
    tool = case["tool"]
    why = case["why"]
    if (cap := case.get("capability")) and not yidam_tools.capabilities().get(cap):
        pytest.skip(f"this server does not declare `{cap}`")

    call = dict(case["call"])
    # The cases name yidam's fixture nodes; re-point the id-taking ones at a node this corpus
    # has, so the shape rules are exercised rather than skipped.
    if tool in {"get_node", "neighbors"} and "id" in call:
        call["id"] = "hypothesis/water"
    if tool == "retrieve":
        call["query"] = "water"
    if tool == "list_nodes" and call.get("class"):
        call["class"] = "concept"

    body = await _call(tool, call)
    expect = case["expect"]

    for field in expect.get("fields", []):
        assert field in body, f"{tool}: missing `{field}`\n{why}"
    for name in expect.get("nonEmpty", []):
        assert body.get(name), f"{tool}: `{name}` is empty\n{why}"
    for name, keys in expect.get("each", {}).items():
        for item in body.get(name, []):
            for key in keys:
                assert key in item, f"{tool}: `{name}[]` item missing `{key}`\n{why}"
    for name, wanted in expect.get("everyItemHas", {}).items():
        for item in body.get(name, []):
            for key, value in wanted.items():
                assert item[key] == value, f"{tool}: `{name}[]` not filtered by {key}\n{why}"
    # `equals`/`equalsAt`/`count` name yidam's fixture corpus; the rules they encode are
    # asserted against this corpus in the dedicated tests below.


# --- the rules the cases encode, asserted against BOSC's corpus ------------------------------
async def test_retrieve_is_one_adaptive_tool_and_always_flags_degraded() -> None:
    """`degraded` MUST be present on every response — there is no third state."""
    body = await _call("retrieve", {"query": "water"})
    assert "degraded" in body and isinstance(body["degraded"], bool)
    assert body["results"], "the Lima mirror should match a query for 'water'"
    for hit in body["results"]:
        assert set(hit) >= {"path", "class", "label", "text", "score"}
    # ...and there is no second retrieval tool to choose between.
    names = [t.name for t in yidam_tools.ALL_TOOLS]
    assert "semantic_search" not in names and "query" not in names


async def test_retrieve_reports_degraded_true_without_a_built_index() -> None:
    """The arm every server hits first. Answering without the flag would claim a vector space
    this server does not have — and BOSC used to *build one on the spot* to avoid saying so."""
    if yidam_tools.vector_ready():
        pytest.skip("a vector index is built for this site; the degraded arm is not the one hit")
    body = await _call("retrieve", {"query": "water"})
    assert body["degraded"] is True


async def test_get_node_returns_the_unified_model_not_a_yaml_render() -> None:
    body = await _call("get_node", {"id": "hypothesis/water"})
    assert set(body) >= {"id", "class", "label", "description", "content", "links"}
    assert body["id"] == "hypothesis/water"
    assert body["class"] == "hypothesis"
    for link in body["links"]:
        assert set(link) == {"target", "relationship"}
    # BOSC's projected provenance still travels — in `content`, where the contract reserves it.
    assert "site:" in body["content"] or "scope:" in body["content"]


async def test_get_node_tolerates_a_repository_path() -> None:
    """An id is written by hand at least as often as it is copied: a path read out of
    `retrieve` or `open_questions` must be passable straight into `get_node`."""
    body = await _call("get_node", {"id": ".yidam/corpus/hypothesis/water.yml"})
    assert body["id"] == "hypothesis/water"


async def test_list_nodes_filters_and_carries_the_typed_fields() -> None:
    whole = await _call("list_nodes", {})
    assert whole["nodes"]
    for node in whole["nodes"]:
        assert set(node) >= {"id", "class", "label", "description"}
    concepts = await _call("list_nodes", {"class": "concept"})
    assert concepts["nodes"]
    assert all(n["class"] == "concept" for n in concepts["nodes"])
    assert len(concepts["nodes"]) < len(whole["nodes"])


async def test_neighbors_walks_edges_in_both_directions() -> None:
    """Half the interesting connections are inbound — the same reason the corpus has an
    `orphan-in` check. A directed walk silently loses that half."""
    mirror = yidam_tools._mirror()
    # The site anchor is the hub every class links *into*, so it is the node whose neighbourhood
    # is almost entirely inbound.
    anchor = next(
        n for n in mirror.nodes if n.node_class == "artifact" and n.id.endswith("site-lima")
    )
    body = await _call("neighbors", {"id": anchor.id})
    assert body["id"] == anchor.id
    assert body["neighbors"], "the site anchor is the hub; it cannot have no neighbours"
    directions = {n["direction"] for n in body["neighbors"]}
    assert "in" in directions, "inbound edges were dropped — the walk is directed"
    for hit in body["neighbors"]:
        assert set(hit) >= {"id", "label", "description", "relationship", "direction", "depth"}
        assert hit["depth"] == 1


async def test_neighbors_reports_each_node_once_at_its_shortest_hop() -> None:
    mirror = yidam_tools._mirror()
    anchor = next(n for n in mirror.nodes if n.id.endswith("site-lima"))
    deep = await _call("neighbors", {"id": anchor.id, "depth": 3})
    ids = [n["id"] for n in deep["neighbors"]]
    assert len(ids) == len(set(ids)), "a node was reported twice"
    assert anchor.id not in ids, "the start node is not its own neighbour"
    by_depth = [n["depth"] for n in deep["neighbors"]]
    assert by_depth == sorted(by_depth), "breadth-first: shortest hop first"


async def test_open_questions_predicate_is_frozen_at_two_arms() -> None:
    """No server may add an arm. BOSC's third — a structured `claim_tag` — is gone; the tag is
    in the serialized text now, so the two arms already cover it."""
    body = await _call("open_questions", {})
    assert body["open_questions"]
    for item in body["open_questions"]:
        assert set(item) == {"id", "label", "path"}

    mirror = yidam_tools._mirror()
    served = {q["id"] for q in body["open_questions"]}
    # Recompute with the *contract's* two arms only, independently of the implementation.
    import yaml

    expected = {
        n.id
        for n in mirror.nodes
        if n.label.startswith("?")
        or "[open]" in yaml.safe_dump(n.to_dict(), sort_keys=False, allow_unicode=True)
    }
    assert served == expected


async def test_a_missing_node_is_a_tool_error_not_a_crash() -> None:
    handler = next(t for t in yidam_tools.ALL_TOOLS if t.name == "get_node")
    result = await handler.handler({"id": "no/such-node"})
    assert result.get("isError") is True
    assert "not found" in result["content"][0]["text"]
