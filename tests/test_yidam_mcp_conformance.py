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
from watermark.site import corpus_mirror

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
    assert yidam_tools.contract()["contract"] == "0.12.0"
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
    # `ontology` backs the CLASS CONTRACT — what a class declares it may link to. The mirror
    # writes a `<class>.ont.yml` per class and each declares only `class:` + `description:`, so
    # there is an ontology and it says nothing about edges. Declaring true would pass 22 cases
    # by accident; #2132 is where it changes.
    assert caps["ontology"] is False
    # `check_citation` resolves into a tonpa dependency. BOSC pins none.
    assert caps["dependencies"] is False
    assert isinstance(caps["retrieve"]["vector"], bool)
    # Null exactly when `vector` is true — the same value every call's `degraded_reason` carries,
    # answered at connect time instead of one failed search later.
    assert (caps["retrieve"]["reason"] is None) is caps["retrieve"]["vector"]


def test_every_core_tool_in_the_contract_has_a_handler() -> None:
    """The guarantee the derived list exists for, asserted rather than inferred.

    `ALL_TOOLS` is built at import, so a missing core handler is an ImportError and this module
    never loads — which is a real failure but an illegible one. Naming it here means the next
    contract bump reports *which* tool is unimplemented instead of a `KeyError` in a traceback.
    """
    core = [t["name"] for t in yidam_tools.contract()["tools"] if t.get("tier", "core") == "core"]
    served = {t.name for t in yidam_tools.ALL_TOOLS}
    assert set(core) <= served, f"core tools with no handler: {sorted(set(core) - served)}"


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
    if tool == "list_nodes" and call.get("class"):
        call["class"] = "concept"
    if tool == "claims" and call.get("node"):
        call["node"] = "hypothesis/water"
    # Re-point IDENTITY, never behaviour. A case asserting `nonEmpty: [results]` needs a query
    # this corpus matches; every other retrieve case is *about* an empty answer — a blank query,
    # or words no corpus uses — and rewriting its query would turn the case into a test of
    # something else that passes.
    if tool == "retrieve" and "results" in case["expect"].get("nonEmpty", []):
        call["query"] = "water"
    # A case whose EXPECTATION names a fixture class cannot be re-pointed without rewriting the
    # assertion, which is grading a second implementation. Skip it by name and assert the rule
    # it encodes against this corpus below.
    for wanted in case["expect"].get("everyItemHas", {}).values():
        if (klass := wanted.get("class")) and klass not in yidam_tools.CLASSES:
            pytest.skip(f"case pins the fixture class `{klass}`; the rule is asserted separately")
    if (klass := call.get("class")) and tool == "retrieve" and klass not in yidam_tools.CLASSES:
        pytest.skip(f"case pins the fixture class `{klass}`; the rule is asserted separately")

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


async def test_open_questions_predicate_is_frozen_at_three_arms() -> None:
    """No server may add a fourth arm, and none may skip one.

    Three at contract 0.12.0 — a `?` label, an `[open]` claim in the body, and an open tag in a
    property the class declared `type: claim`. The third is the arm this repository reported as
    missing (goedelsoup/yidam#127) and upstream added; it reads both spellings.

    The third arm changes nothing here and that is the point of asserting it. `_ont_yaml`
    declares no properties, so a conforming read of the declaration finds none — and BOSC's
    `claim_tag` is reached by arm two regardless, because `_claim_token` writes the bracketed
    token into the serialized text. A two-arm and a three-arm server return the identical set
    over a corpus that declares nothing, which is exactly what the contract says. The recompute
    below carries the arm anyway, so that the day #2132 declares the property, this test is
    already asking the right question.
    """
    body = await _call("open_questions", {})
    assert body["open_questions"]
    for item in body["open_questions"]:
        assert set(item) == {"id", "label", "path"}

    mirror = yidam_tools._mirror()
    served = {q["id"] for q in body["open_questions"]}
    # Recompute with the *contract's* three arms, independently of the implementation.
    import yaml

    declared = yidam_tools._CLAIM_PROPERTY

    def is_open(node: Any) -> bool:
        if node.label.startswith("?"):
            return True
        if "[open]" in yaml.safe_dump(node.to_dict(), sort_keys=False, allow_unicode=True):
            return True
        # Both spellings, and only a property a class declared. `_ont_yaml` declares none, so
        # this arm is empty today — asserted, not assumed.
        return str(node.meta.get(declared, "")).strip().strip("[]") == "open" and bool(
            _declared_claim_properties(node.node_class)
        )

    assert served == {n.id for n in mirror.nodes if is_open(n)}


def _declared_claim_properties(node_class: str) -> list[str]:
    """The properties ``node_class`` declares as `type: claim` — read from the ontology the
    mirror actually writes, so this answers `[]` until #2132 declares one."""
    import yaml as _yaml

    ont = _yaml.safe_load(corpus_mirror._ont_yaml(node_class)) or {}
    return [p["name"] for p in ont.get("properties", []) if p.get("type") == "claim"]


async def test_an_unknown_class_is_rejected_not_absent_and_not_an_error() -> None:
    """The rule the two skipped `retrieve` cases encode, re-expressed for a corpus that *does*
    declare its classes.

    Upstream's fixture declares none, so there `gage` is simply a filter that matches nothing —
    `rejected: null`, `absence: null`. BOSC writes a `<class>.ont.yml` per class, so it can tell
    a wrong class from an empty one, and the contract's answer for that case is a **rejection**:
    a bad request, not an empty result. They are different repairs — fix the call, versus the
    corpus has nothing — and `rejected` and `absence` are mutually exclusive because of it.

    Not an `isError` either, which is what this used to be. A rejection the agent can read
    carries the valid class list; a tool error carries a string and a dead end.
    """
    body = await _call("retrieve", {"query": "water", "class": "nosuchclass"})
    assert body["rejected"] is not None and body["rejected"]["code"] == "unknown-class"
    assert body["absence"] is None
    assert body["results"] == []
    # ...and a class this corpus does declare filters rather than rejecting.
    good = await _call("retrieve", {"query": "water", "class": "concept"})
    assert good["rejected"] is None
    assert all(hit["class"] == "concept" for hit in good["results"])


async def test_retrieve_says_which_kind_of_nothing() -> None:
    """`absence` is null when there is an answer, and names the cause when there is not."""
    answered = await _call("retrieve", {"query": "water"})
    assert answered["results"] and answered["absence"] is None

    blank = await _call("retrieve", {"query": "   "})
    assert blank["absence"]["code"] == "query-no-terms"
    assert blank["absence"]["instances"] > 0, "a blank query must still report the corpus size"
    assert blank["rejected"] is None and blank["results"] == []

    unused = await _call("retrieve", {"query": "hydropeaking zzzznotaword"})
    assert unused["absence"]["code"] == "no-term-match"


async def test_degraded_reason_is_null_exactly_when_not_degraded() -> None:
    """`no_index`, never `no_vector_support` — the corpus is missing the artefact, which is the
    repair either way, and pinning the nearer cause keeps every build answering identically."""
    body = await _call("retrieve", {"query": "water"})
    assert (body["degraded_reason"] is None) is (body["degraded"] is False)
    if body["degraded"]:
        assert body["degraded_reason"] == "no_index"


async def test_claims_serves_the_tag_or_nothing() -> None:
    """There is no untagged arm. An unmarked sentence is prose, and `get_node` is where prose
    lives — inventing a fourth standing would turn every aside into a weakly-evidenced claim."""
    body = await _call("claims", {})
    assert body["claims"], "the Lima mirror carries tagged claims"
    for claim in body["claims"]:
        assert set(claim) >= {"text", "standing", "node", "class", "scope", "sources"}
        assert claim["standing"] in yidam_tools.STANDINGS
    # Every claim is anchored on a node that exists — no claim invented from nowhere.
    ids = {n.id for n in yidam_tools._mirror().nodes}
    assert {c["node"] for c in body["claims"]} <= ids


async def test_claims_total_counts_what_k_dropped() -> None:
    """An agent told `here are 5 claims` and one told `here are 5 of 41` can take different next
    actions, and only the second can decide to ask for more."""
    everything = await _call("claims", {})
    assert everything["total"] > 1, "this corpus needs more than one claim to make the point"
    capped = await _call("claims", {"k": 1})
    assert capped["returned"] == 1 and len(capped["claims"]) == 1
    assert capped["total"] == everything["total"], "`total` was computed after truncating"


async def test_claims_filters_by_standing_and_agrees_with_open_questions() -> None:
    """`what does this corpus take as X` is the query an agent should make before it writes.

    The `open` arm is cross-checked against `open_questions`, which is a different predicate over
    the same tags: every node with an open claim must be a node the frozen predicate flags. A
    server whose two answers disagree has two vocabularies and no way to notice.
    """
    for standing in yidam_tools.STANDINGS:
        body = await _call("claims", {"standing": standing})
        assert all(c["standing"] == standing for c in body["claims"])

    opens = await _call("claims", {"standing": "open"})
    flagged = {q["id"] for q in (await _call("open_questions", {}))["open_questions"]}
    assert {c["node"] for c in opens["claims"]} <= flagged


async def test_claim_tags_carries_both_spellings_and_no_fourth_standing() -> None:
    body = await _call("claim_tags", {})
    assert len(body["tags"]) == 3, "an `untagged` or `implicit` fourth is a different vocabulary"
    for tag in body["tags"]:
        assert set(tag) >= {"standing", "in_prose", "in_property", "meaning"}
        # Prose is scanned for the bracketed form only; a declared property takes the bare one.
        assert tag["in_prose"] == f"[{tag['standing']}]"
        assert tag["in_property"] == tag["standing"]
    assert body["note"]


async def test_check_subject_is_total_and_never_an_error() -> None:
    """An unrecognized verb is a finding in the payload, not a failed call. A tool that failed
    harder than the gate would assert a verdict nobody agreed to, and an agent would learn to
    stop asking."""
    handler = next(t for t in yidam_tools.ALL_TOOLS if t.name == "check_subject")
    for subject in ["frobnicate: nothing", "", "no colon here", "establish: a thing"]:
        result = await handler.handler({"subject": subject})
        assert not result.get("isError"), subject
        body = json.loads(result["content"][0]["text"])
        assert body["kind"] in {"epistemic", "operational"}, "every subject gets a kind"
        assert all(v["severity"] == "warn" for v in body["violations"])
        assert body["vocabulary"], "the closed list travels with the verdict"


async def test_check_subject_reads_a_scope_suffix_as_its_own_finding() -> None:
    """It costs twice: `vendor(yidam)` is in no list, AND classification falls through to
    epistemic, filing an operational commit as a change in understanding. A caller told only
    `recognized: false` would go looking for a verb that is already correct."""
    scoped = await _call("check_subject", {"subject": "vendor(yidam): prelude into .yidam"})
    assert scoped["recognized"] is False
    assert [v["rule"] for v in scoped["violations"]] == ["scope-suffix"]

    bare = await _call("check_subject", {"subject": "vendor: prelude into .yidam"})
    assert bare["recognized"] is True and bare["kind"] == "operational"
    assert bare["violations"] == []


async def test_a_missing_node_is_a_tool_error_not_a_crash() -> None:
    handler = next(t for t in yidam_tools.ALL_TOOLS if t.name == "get_node")
    result = await handler.handler({"id": "no/such-node"})
    assert result.get("isError") is True
    assert "not found" in result["content"][0]["text"]
