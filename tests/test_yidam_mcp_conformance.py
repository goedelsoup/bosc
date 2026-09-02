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
from dataclasses import replace
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
    # `ontology` backs the CLASS CONTRACT — what a class declares it may link to. Since #2132
    # each class declares its properties and the relationships it licenses, so this is now
    # backed rather than declined, and all four ontology tools are served.
    assert caps["ontology"] is True
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
    # A case whose CALL or EXPECTATION names a fixture class cannot be re-pointed without
    # rewriting the assertion, which is grading a second implementation. Skip it by name and
    # assert the rule it encodes against this corpus below.
    for wanted in case["expect"].get("everyItemHas", {}).values():
        if (klass := wanted.get("class")) and klass not in yidam_tools.CLASSES:
            pytest.skip(f"case pins the fixture class `{klass}`; the rule is asserted separately")
    if (klass := call.get("class")) and klass not in yidam_tools.CLASSES:
        pytest.skip(f"case pins the fixture class `{klass}`; the rule is asserted separately")
    # `edge_policy` is a property of the CORPUS, not of the server. Upstream's fixture leaves it
    # unstated, so an undeclared relationship there runs with a diagnostic; BOSC declares
    # `exhaustive` on all five classes — truthfully, because its mirror is generated — so the
    # same query is rejected. Both arms are the contract; only one is reachable here, and it is
    # asserted below along with the other.
    if case_id == "query/undeclared-relationship-is-a-diagnostic.json":
        pytest.skip("case needs a non-exhaustive `edge_policy`; both arms are asserted separately")
    # `everyItemHas: {edges: {target: concept}}` is a fact about YIDAM'S FIXTURE — there,
    # `concept` happens to link only to concepts. It is not a rule a conforming server can keep:
    # the contract must admit a corpus whose class links to more than one other, and the case's
    # own `why` is about DIRECTION, not about targets being uniform. BOSC's `concept` licenses
    # `related` → `concept` and the `in-corpus` fallback → `artifact`, so it spans two. This
    # passed before the fallback edges were declared only because the corpus coincided with the
    # fixture. The rule it carries is asserted over both classes below.
    if case_id == "licensed_edges/declares-edges.json":
        pytest.skip("case pins the fixture's single-target vocabulary; the rule is asserted below")

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
                # An INTEGER here is a cardinality of yidam's fixture corpus, not a shape rule —
                # `rows: 4` says that fixture holds four concepts, and this one holds seventy
                # seven. It is the same fact `count` carries, which this runner already declines
                # to assert for the same reason; the rule (every row prices the SAME rows) is
                # asserted against this corpus below. Every other value is a shape and is checked.
                if isinstance(value, int) and not isinstance(value, bool):
                    continue
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
    # ...and there is no second RETRIEVAL tool to choose between. `query` is served (#2132) and
    # is not one: it walks named, directed relationships and takes no free text, so a caller
    # never has to decide which vector space it is in — which is the decision the split pair
    # forced and the reason the contract keeps `retrieve` adaptive.
    names = [t.name for t in yidam_tools.ALL_TOOLS]
    assert "semantic_search" not in names
    retrieval = [n for n in names if n in {"retrieve", "semantic_search", "search", "vector"}]
    assert retrieval == ["retrieve"]


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


async def test_query_walks_by_type_where_neighbors_cannot() -> None:
    """The reason `query` exists beside `neighbors`.

    `neighbors` chains edges in both directions and filters on neither relationship nor
    direction — it carries both out as labels and reads neither as an input. A server offering
    only that has typed its graph and left no way to walk by the types.
    """
    body = await _call("query", {"query": "concept -related-> concept", "limit": 5})
    assert body["rejected"] is None and body["absence"] is None
    assert body["matched"] > 0
    assert body["returned"] == len(body["results"]) <= 5
    # `limit` bounds the PROJECTION, not the traversal.
    assert body["matched"] > body["returned"]
    for row in body["results"]:
        assert set(row) >= {"node", "class", "label", "origin"}
        assert row["origin"] is None, "a local node is attributed to no package"

    # The same relationship, walked backwards, is a different question with a real answer.
    back = await _call("query", {"query": "concept <-related- concept"})
    assert back["rejected"] is None and back["matched"] > 0


#: The absence each deliberately-unauthored fallback edge produces — and they are NOT the same
#: code, which is the point of splitting them. Nothing in the corpus authors `in-corpus`, so a
#: traversal of it is `relationship-unauthored`: the ontology promised a relationship the corpus
#: has never written. `in-site` **is** authored — by 61 `artifact` nodes — just not by any
#: `relation`, so the same query from `relation` is `no-edge-from-here`: the name is real and
#: nothing that reached this step has one. A caller repairs those two differently, which is why
#: a server that collapsed them would be useless in exactly the case they exist for.
_FALLBACK_ABSENCE = {
    ("concept", "in-corpus"): "relationship-unauthored",
    ("relation", "in-site"): "no-edge-from-here",
}


async def test_every_declared_edge_traverses_and_lands_on_its_declared_class() -> None:
    """The ontology is a promise about the corpus; this is the test that it is kept.

    A relationship a class licenses and no instance authors comes back from a traversal exactly
    as a mistyped name would — which is why the absence codes split the two. Walking every
    declared edge is how a projection bug in `resolve_link_target` surfaces as a failure here
    rather than as a quietly empty answer somewhere downstream.
    """
    for owner, ont in corpus_mirror.ONTOLOGY.items():
        for edge in ont.edges:
            body = await _call("query", {"query": f"{owner} -{edge.relationship}-> {edge.target}"})
            assert body["rejected"] is None, f"{owner} -{edge.relationship}->: {body['rejected']}"
            if edge.fallback:
                # A path the projection can take and this corpus has not: the traversal is
                # legal and finds nothing, which is an ABSENCE and not a rejection.
                assert body["matched"] == 0
                assert body["absence"]["code"] == _FALLBACK_ABSENCE[owner, edge.relationship]
                continue
            assert body["matched"] > 0, (
                f"`{owner}` declares `{edge.relationship}` and no instance authors it — "
                f"the ontology reached past the corpus, or the projection stopped writing it. "
                f"If the path is a deliberate fallback, mark the edge `fallback=True`."
            )
            for row in body["results"]:
                assert row["class"] == edge.target

    # The marking is a licence to be unauthored, not a licence to be forgotten: it must stay
    # rare and deliberate, or the invariant above quietly stops covering the vocabulary.
    marked = {
        (owner, e.relationship)
        for owner, ont in corpus_mirror.ONTOLOGY.items()
        for e in ont.edges
        if e.fallback
    }
    assert marked == set(_FALLBACK_ABSENCE), (
        "a new unauthored edge was declared — confirm it is a reachable projection path, "
        "not an ontology reaching past its corpus, then record which absence it produces"
    )


async def test_a_mistyped_class_is_rejected_with_the_near_miss() -> None:
    """Without an ontology every class name is accepted and a misspelling comes back as zero
    results — the one failure this tool exists to prevent."""
    body = await _call("query", {"query": "concpet"})
    assert body["rejected"]["code"] == "unknown-class"
    assert "concept" in body["rejected"]["message"], "a rejection without the near miss is a shrug"
    assert body["absence"] is None, "a typo is not a true negative"
    assert body["results"] == []


async def test_an_unlicensed_relationship_is_rejected_because_this_corpus_is_closed() -> None:
    """BOSC declares `edge_policy: exhaustive` on every class, and it is entitled to.

    The mirror is **generated**, so its relationship vocabulary is closed by construction: a
    relationship outside the declaration is a bug in `corpus_mirror`, not a coinage somebody
    made deliberately. That is exactly what an exhaustive policy turns into an error.
    """
    assert all(o.edge_policy == "exhaustive" for o in corpus_mirror.ONTOLOGY.values())
    body = await _call("query", {"query": "concept -enables-> concept"})
    assert body["rejected"]["code"] == "unlicensed-edge"

    # A hop that IS licensed but lands somewhere else is its own code, because the repair is
    # different: the relationship is right and the destination is wrong.
    wrong = await _call("query", {"query": "concept -related-> artifact"})
    assert wrong["rejected"]["code"] == "edge-target-class"


async def test_an_undeclared_relationship_only_runs_when_the_policy_is_not_exhaustive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The arm this corpus cannot reach, asserted rather than assumed.

    A non-empty `edges:` says *these relationships exist*, not *and no others may*. Reading
    every declaration as exhaustive refuses legal queries against every corpus written before
    `edge_policy` existed — upstream measured 210 such errors on a compliant corpus. So under
    any other policy an undeclared relationship is a DIAGNOSTIC on a query that runs, and
    `rejected` stays null.
    """
    from watermark.agent import corpus_query

    open_concept = replace(corpus_mirror.ONTOLOGY["concept"], edge_policy="characteristic")
    monkeypatch.setitem(corpus_query.ONTOLOGY, "concept", open_concept)

    steps, parse_rejection = corpus_query.parse("concept -leads-to-> concept")
    assert parse_rejection is None
    rejection, diagnostics = corpus_query.typecheck(steps)
    assert rejection is None, "a warning is not a rejection"
    assert [d.code for d in diagnostics] == ["undeclared-relationship"]
    assert diagnostics[0].level == "warn"


async def test_a_well_formed_query_that_matches_nothing_is_an_absence_not_a_rejection() -> None:
    """`rejected` says the query is wrong; `absence` says the query is right and the corpus is
    quiet. Both keys are present on every response and at most one is non-null — a server that
    merged them would tell a caller its mistake was a true negative."""
    body = await _call("query", {"query": "hypothesis[status=nosuchstatus]"})
    assert body["rejected"] is None
    assert body["absence"]["code"] == "predicate-unsatisfied"
    # `instances` is the DENOMINATOR the message is about — none of three and none of nine
    # hundred are different facts about a corpus.
    assert body["absence"]["instances"] > 0
    assert body["absence"]["elsewhere"] == [], "no dependency is installed to point at"


async def test_a_star_step_narrows_to_the_classes_that_declare_the_property() -> None:
    body = await _call("query", {"query": "*[claim_tag=open]"})
    assert body["rejected"] is None and body["matched"] > 0
    assert body["steps"][0]["class"] == "*"
    # `claim_tag` is declared by `question` alone, so `*` is one class here, not five.
    assert body["steps"][0]["classes"] == ["question"]
    assert [d["level"] for d in body["diagnostics"]] == ["info"]
    assert all(row["class"] == "question" for row in body["results"])

    # ...and it agrees with the tool that answers a WIDER question the same way. The frozen
    # `open_questions` predicate has three arms — a `?` label, `[open]` in the body, and an
    # open tag in a declared claim field — and this query is only the third of them, on the
    # one class declaring `claim_tag`. The two were equal until #2134 projected `record`
    # nodes, which carry their claim profile in the body and so arrive through the SECOND
    # arm; an equality here would have been asserting a corpus coincidence as a rule.
    opens = await _call("open_questions", {})
    matched = {row["node"] for row in body["results"]}
    listed = {q["id"] for q in opens["open_questions"]}
    assert matched <= listed, "a claim-tagged open question the predicate does not list"
    assert len(opens["open_questions"]) >= body["matched"]
    # And the difference is the other arms, never a `question` the query should have found.
    assert all(not node.startswith("question/") for node in listed - matched)


async def test_the_anchor_carries_degraded_and_only_the_entry_step_may_have_one() -> None:
    """`degraded` lives on the anchor, never at the top level: a query with no anchor performed
    no retrieval, and a `false` up there would read as retrieval having succeeded."""
    body = await _call("query", {"query": 'concept~"water quality"', "anchor_k": 2})
    assert body["rejected"] is None
    assert body["anchor"]["step"] == 0 and body["anchor"]["k"] == 2
    assert (body["anchor"]["degraded_reason"] is None) is (body["anchor"]["degraded"] is False)
    assert len(body["anchor"]["entries"]) <= 2

    later = await _call("query", {"query": 'concept -related-> concept~"x"'})
    assert later["rejected"]["code"] == "anchor-not-entry"


async def test_estimate_prices_the_same_rows_at_every_projection_and_returns_none() -> None:
    """Cheap for the caller, not for the server. A conforming server MUST NOT return rows."""
    body = await _call("estimate", {"query": "concept"})
    assert body["projections"] and body["basis"] == "chars/4"
    assert "results" not in body, "a quote that returns the rows is the call, not a quote"
    rows = {p["rows"] for p in body["projections"]}
    assert len(rows) == 1, "every projection must price the SAME match set"
    # Cheapest first, and `tokens` is `chars // 4` throughout — one approximation, named.
    assert [p["chars"] for p in body["projections"]] == sorted(
        p["chars"] for p in body["projections"]
    )
    assert all(p["tokens"] == p["chars"] // 4 for p in body["projections"])
    # `fits` is null exactly when no budget was quoted.
    assert all(p["fits"] is None for p in body["projections"])

    budgeted = await _call("estimate", {"query": "concept", "budget": 1})
    assert all(p["fits"] is False for p in budgeted["projections"])


async def test_a_pack_says_why_in_its_own_text_when_it_is_empty() -> None:
    """A pack travels WITHOUT the envelope around it, so an empty one that says nothing is a
    context window asserting the corpus has no view — the invention the field exists to
    prevent. A server carrying the reason in `absence` alone passes every JSON assertion and
    hands a model a blank page."""
    body = await _call("pack", {"query": "concpet"})
    assert body["rejected"]["code"] == "unknown-class"
    assert body["text"], "an empty pack must still say why"
    assert "concept" in body["text"]

    full = await _call("pack", {"query": "hypothesis"})
    assert full["written"] == full["reachable"] and full["omitted"] == 0
    assert full["budget"]["tokens"] is None and full["budget"]["basis"] == "chars/4"

    # A budget changes what is WRITTEN and never what was reachable.
    tight = await _call("pack", {"query": "hypothesis", "budget": 1})
    assert tight["reachable"] == full["reachable"]
    assert tight["omitted"] > 0 and sum(tight["omitted_by_class"].values()) == tight["omitted"]


async def test_licensed_edges_reports_both_ends_and_distinguishes_silence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`declares_edges: false` means the class SAID NOTHING, not that it licenses nothing.

    The two answers look alike and mean opposite things; a client that collapses them reports
    every instance in a half-filled corpus. Every BOSC class declares edges, so the false arm is
    only reachable with an ontology that does not — asserted here rather than left untested.
    """
    from watermark.agent import corpus_query

    body = await _call("licensed_edges", {"class": "artifact"})
    assert body["declares_edges"] is True
    directions = {e["direction"] for e in body["edges"]}
    # An edge is documented from BOTH ends — the licensing check ignores direction, so
    # filtering to `out` would answer a question the gate does not ask.
    assert directions == {"in", "out"}
    for edge in body["edges"]:
        assert set(edge) >= {"relationship", "target", "direction"}

    # And the coverage the skipped `declares-edges` case gave up: a class's licensed edges are
    # NOT constrained to one target class. `concept` licenses `related` → `concept` and the
    # `in-corpus` fallback → `artifact`, and both must be reported.
    spanning = await _call("licensed_edges", {"class": "concept"})
    assert spanning["declares_edges"] is True
    assert {e["target"] for e in spanning["edges"]} == {"concept", "artifact"}
    # All outbound here, and that is the honest answer rather than a filtered one: no other
    # class licenses an edge INTO `concept`, so the inbound view is genuinely empty. `artifact`
    # above is what proves the inbound half is reported when it exists.
    assert {e["direction"] for e in spanning["edges"]} == {"out"}

    silent = replace(corpus_mirror.ONTOLOGY["hypothesis"], edges=())
    monkeypatch.setitem(corpus_query.ONTOLOGY, "hypothesis", silent)
    monkeypatch.setitem(yidam_tools.ONTOLOGY, "hypothesis", silent)
    quiet = await _call("licensed_edges", {"class": "hypothesis"})
    assert quiet["declares_edges"] is False
    assert "not the same as licensing none" in quiet["note"]


async def test_cost_is_what_the_caller_pays_not_what_the_server_read() -> None:
    """`nodes_read` counts nodes whose content was evaluated, tested for a hop, or projected —
    never the corpus load, which happens either way. Class narrowing is a directory listing and
    is not charged; a predicate reads every candidate it tests."""
    listing = await _call("query", {"query": "concept", "limit": 3})
    assert listing["cost"]["corpus_nodes"] > listing["cost"]["nodes_read"]
    assert listing["cost"]["nodes_read"] == 3, "only the projected rows were read"

    # A predicate reads every candidate it tests — but only after `*` has narrowed to the
    # classes declaring the property, and that narrowing is a directory listing. So the charge
    # is the size of the narrowed class, not of the corpus: 35 questions, not 234 nodes.
    predicated = await _call("query", {"query": "*[claim_tag=open]"})
    questions = await _call("list_nodes", {"class": "question"})
    assert predicated["cost"]["nodes_read"] == len(questions["nodes"])
    assert predicated["cost"]["nodes_read"] < predicated["cost"]["corpus_nodes"]


async def test_a_missing_node_is_a_tool_error_not_a_crash() -> None:
    handler = next(t for t in yidam_tools.ALL_TOOLS if t.name == "get_node")
    result = await handler.handler({"id": "no/such-node"})
    assert result.get("isError") is True
    assert "not found" in result["content"][0]["text"]


async def test_a_rejected_select_carries_no_rows() -> None:
    """A rejection is an answer with nothing in it — including when the *projection* is what
    was wrong.

    `parse_select` rejects an unprojectable field by returning an empty field list, and the
    handler went on to project against it: fifty rows of `{"origin": null}` shipped beside a
    non-null `rejected`. Every JSON assertion passed and the envelope's one invariant — a
    rejection returns no results — was broken in the only place the suite did not look.
    """
    body = await _call("query", {"query": "concept", "select": "nope"})
    assert body["rejected"]["code"] == "unknown-field"
    assert body["results"] == [], "a rejected projection must not emit placeholder rows"
    assert body["returned"] == 0
    # The traversal still ran and still reports what it found — `matched` is not a projection.
    assert body["matched"] > 0
    assert body["absence"] is None, "at most one of `rejected`/`absence` is ever non-null"


async def test_the_anchor_scores_only_the_classes_the_step_narrowed_to() -> None:
    """The entry step applies its class filter to the anchor, not just to the plain pool.

    A hop filters its landings by `step_classes[i]`; the entry step never did, so an anchored
    `*[property=value]` scored every node in the corpus, reported out-of-class nodes in
    `anchor.entries`, and was billed for the narrowed pool it did not read. `Cost` says a
    degraded keyword anchor is charged for every candidate it scored, so that under-bill
    contradicted the rule in the same file that states it.
    """
    body = await _call("query", {"query": '*[claim_tag=open]~"water"'})
    narrowed = body["steps"][0]["classes"]
    assert narrowed == ["question"], "`claim_tag` is declared by exactly one class"
    entries = (body["anchor"] or {}).get("entries", [])
    assert entries, "the probe needs a non-empty anchor to be about anything"
    assert {e["class"] for e in entries} <= set(narrowed), "the anchor leaked an out-of-class node"
    # Charged for what it scored: the narrowed pool, not the whole corpus. Before the fix the
    # anchor scored all 234 nodes and was billed for the 35 it was narrowed to.
    questions = await _call("list_nodes", {"class": "question"})
    everything = await _call("list_nodes", {})
    assert body["cost"]["nodes_read"] <= len(questions["nodes"])
    assert len(questions["nodes"]) < len(everything["nodes"]), "the bound must bite"


async def test_the_pack_quote_prices_the_pack_and_not_a_projection() -> None:
    """`estimate.pack` must quote what `pack` would actually return, to the character.

    It quoted the widest *projection* instead — JSON of `node,class,label,body` rather than the
    markdown `pack` writes — overstating a real Lima pack by 113% while the comment above it
    promised `chars` was exact. `estimate` exists so a caller can decide affordability; a quote
    for prose it will never receive is worse than no quote. Both now render through
    `_render_for_pack`, so the two cannot drift apart again.
    """
    quote = await _call("estimate", {"query": "concept"})
    packed = await _call("pack", {"query": "concept"})
    assert quote["pack"]["chars"] == len(packed["text"])
    assert quote["pack"]["tokens"] == len(packed["text"]) // 4
    # `pack` takes no `limit`, so the quote covers the whole match set — not `estimate`'s page.
    assert quote["pack"]["nodes"] == packed["written"] == quote["matched"]
    assert quote["pack"]["fits"] is None, "no budget asked, so no verdict given"

    # And the verdict agrees with what `pack` then does with the same budget.
    tight = await _call("estimate", {"query": "artifact", "budget": 500})
    trimmed = await _call("pack", {"query": "artifact", "budget": 500})
    assert tight["pack"]["fits"] is False
    assert trimmed["omitted"] > 0, "the quote said it would not fit; the packer must have trimmed"


async def test_the_near_miss_is_drawn_from_every_candidate_class() -> None:
    """A `*` predicate is rejected across all classes, so its hint must come from all of them.

    Reading `classes[0]` drew the suggestion from one arbitrary class and silently dropped the
    near miss a later class would have supplied — a rejection without the near miss is a shrug.
    """
    body = await _call("query", {"query": "*[claimtag=open]"})
    assert body["rejected"]["code"] == "unknown-property"
    assert "claim_tag" in body["rejected"]["message"], (
        "`claim_tag` is declared by `question`, not by the first class searched"
    )
