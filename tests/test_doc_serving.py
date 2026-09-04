"""Tests for the published-document serving audit (#2149).

The bug this check exists for had two independent causes at once — a publish gate that only
carried one site's set, and 456 objects absent from the bucket — and the whole value of the check
is that it tells them apart. So the classification is exercised against every combination of the
three sets, and the end-to-end path runs over an :class:`httpx.MockTransport`: hermetic, no
network, no credentials.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from watermark.site.doc_serving import (
    GateUnavailableError,
    OfferedRel,
    ServingAudit,
    audit,
    classify,
    doc_api_path,
    fetch_gate,
    offered_rels,
    probe_api,
    probe_store,
)


# --- the /api/doc key ---------------------------------------------------------
def test_doc_api_path_encodes_each_segment_and_keeps_the_separators() -> None:
    """Mirrors @watermark/core's `docApiUrl` — segment-wise, so a `/` stays a `/`."""
    assert doc_api_path("recorder/deed.pdf") == "/api/doc/recorder/deed.pdf"
    assert (
        doc_api_path("legal/prr/School District Notice.pdf")
        == "/api/doc/legal/prr/School%20District%20Notice.pdf"
    )
    assert doc_api_path("a/b&c/d#e.pdf") == "/api/doc/a/b%26c/d%23e.pdf"


def test_doc_api_path_encodes_a_literal_slash_free_segment_only() -> None:
    """A `#` in a name must not truncate the path into a fragment (as-received names carry them)."""
    assert "#" not in doc_api_path("oepa/2DP00130 #2.pdf")


# --- what the repo offers -----------------------------------------------------
def _bundle(root: Path, slug: str, entries: list[tuple[str, bool]]) -> None:
    feeds = root / slug / "feeds"
    feeds.mkdir(parents=True, exist_ok=True)
    (feeds / "documents.json").write_text(
        json.dumps(
            [
                {
                    "slug": "coll",
                    "title": "Collection",
                    "entries": [
                        {
                            "rel": rel,
                            "name": rel.split("/")[-1],
                            "size_bytes": 1,
                            "suffix": "pdf",
                            "media_type": "application/pdf",
                            "render_class": "pdf",
                            "published": published,
                            "available": True,
                        }
                        for rel, published in entries
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )


def test_offered_rels_unions_across_sites_and_records_which_publish_it(tmp_path: Path) -> None:
    _bundle(tmp_path, "lima", [("oepa/lima.pdf", True), ("oepa/withheld.pdf", False)])
    _bundle(tmp_path, "findlay", [("findlay/wwtp.pdf", True), ("oepa/lima.pdf", True)])

    offered = offered_rels(bundles_root=tmp_path, slugs=["lima", "findlay"])

    assert [o.rel for o in offered] == ["findlay/wwtp.pdf", "oepa/lima.pdf"]
    assert {o.rel: o.sites for o in offered} == {
        "findlay/wwtp.pdf": ("findlay",),
        "oepa/lima.pdf": ("lima", "findlay"),
    }


def test_offered_rels_skips_a_site_with_no_committed_feed(tmp_path: Path) -> None:
    """A registered-but-unbuilt site must not take the audit down with it."""
    _bundle(tmp_path, "lima", [("oepa/lima.pdf", True)])
    offered = offered_rels(bundles_root=tmp_path, slugs=["lima", "nowhere"])
    assert [o.rel for o in offered] == ["oepa/lima.pdf"]


def test_offered_rels_reads_the_real_exported_sites_and_finds_more_than_limas(
    tmp_path: Path,
) -> None:
    """Against the committed bundles: the offered set reaches past Lima.

    This is the shape of the bug — the deployed gate carried Lima's set alone — asserted on real
    data rather than a fixture, and without pinning a count that every clearance would move.
    """
    lima_only = offered_rels(slugs=["lima"])
    everything = offered_rels()
    assert len(everything) > len(lima_only)
    assert {o.rel for o in lima_only} <= {o.rel for o in everything}


# --- the classification (pure) ------------------------------------------------
GATE = frozenset({"served.pdf", "unserved.pdf"})
OFFERED = [
    OfferedRel(rel="served.pdf", sites=("lima",)),
    OfferedRel(rel="unserved.pdf", sites=("lima",)),
    OfferedRel(rel="ungated.pdf", sites=("findlay",)),
]
STATUSES = {"served.pdf": 200, "unserved.pdf": 404, "ungated.pdf": 404}


def test_classify_separates_a_gate_rejection_from_a_missing_object() -> None:
    unserved, ungated, absent, gate_only = classify(OFFERED, GATE, STATUSES)

    assert [f.rel for f in unserved] == ["unserved.pdf"]
    assert [f.rel for f in ungated] == ["ungated.pdf"]
    assert absent == []
    assert gate_only == []
    # The distinction is the whole point: both answered 404 on the wire.
    assert STATUSES["unserved.pdf"] == STATUSES["ungated.pdf"] == 404


def test_classify_does_not_double_report_a_gated_rel_as_unserved() -> None:
    """A rel the gate blocks never reaches R2, so calling it `unserved` would blame the store."""
    unserved, ungated, _, _ = classify(OFFERED, frozenset(), STATUSES)
    assert unserved == []
    assert len(ungated) == 3


def test_classify_reports_store_absence_independently_of_the_gate() -> None:
    """An absent object is a finding even while a gate rejection masks it on the wire."""
    _, _, absent, _ = classify(
        OFFERED, GATE, STATUSES, store_absent=frozenset({"ungated.pdf", "unserved.pdf"})
    )
    assert sorted(f.rel for f in absent) == ["ungated.pdf", "unserved.pdf"]


def test_classify_notes_a_gate_ahead_of_the_checkout() -> None:
    _, _, _, gate_only = classify(OFFERED, GATE | {"stale-clearance.pdf"}, STATUSES)
    assert gate_only == ["stale-clearance.pdf"]


def test_ok_fails_on_an_unserved_or_absent_document_and_tolerates_deploy_lag() -> None:
    unserved, ungated, absent, _ = classify(
        OFFERED, GATE, STATUSES, store_absent=frozenset({"ungated.pdf"})
    )
    base = {"base_url": "https://x", "offered": 3, "gate_size": 2, "served": 1}

    assert not ServingAudit(**base, unserved=unserved).ok
    assert not ServingAudit(**base, store_absent=absent).ok
    # Deploy lag alone is the repo's normal between-deploys state — reported, never failed.
    assert ServingAudit(**base, ungated=ungated).ok
    assert ServingAudit(**base).ok


# --- the gate asset -----------------------------------------------------------
def _client(handler: object) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]


def test_fetch_gate_reads_the_deployed_allowlist() -> None:
    with _client(lambda r: httpx.Response(200, json={"rels": ["a.pdf", "b.pdf"]})) as client:
        assert fetch_gate("https://x/", client=client) == frozenset({"a.pdf", "b.pdf"})


def test_fetch_gate_refuses_to_compare_against_a_missing_asset() -> None:
    """No gate means no verdict — never an empty set, which would read as "nothing published"."""
    with (
        _client(lambda r: httpx.Response(404, text="not found")) as client,
        pytest.raises(GateUnavailableError),
    ):
        fetch_gate("https://x", client=client)


def test_fetch_gate_refuses_a_payload_with_no_rels_array() -> None:
    with (
        _client(lambda r: httpx.Response(200, json={"documents": []})) as client,
        pytest.raises(GateUnavailableError),
    ):
        fetch_gate("https://x", client=client)


@pytest.mark.parametrize(
    "payload", [["a.pdf"], "nope", 42, None], ids=["list", "str", "int", "null"]
)
def test_fetch_gate_refuses_a_payload_that_is_not_a_mapping(payload: object) -> None:
    """A malformed gate must be a NAMED refusal, not an AttributeError.

    A JSON array or scalar has no `.get`, so the unguarded read escaped the caller's
    `GateUnavailableError` handler and surfaced as a traceback — the one failure mode the
    controlled error exists to prevent.
    """
    with (
        _client(lambda r: httpx.Response(200, json=payload)) as client,
        pytest.raises(GateUnavailableError),
    ):
        fetch_gate("https://x", client=client)


# --- the probes ---------------------------------------------------------------
def test_probe_api_heads_the_encoded_path_and_maps_each_status() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        # `raw_path`, not `path`: httpx decodes the latter, which would hide the encoding this
        # test is about.
        seen.append(request.url.raw_path.decode())
        assert request.method == "HEAD"  # never GET: the corpus is 3.7 GB
        return httpx.Response(200 if "ok" in request.url.path else 404)

    with _client(handler) as client:
        statuses = probe_api(["a/ok.pdf", "a/no name.pdf"], "https://x", client=client)

    assert statuses == {"a/ok.pdf": 200, "a/no name.pdf": 404}
    assert "/api/doc/a/no%20name.pdf" in seen


def test_probe_api_records_a_transport_error_as_not_served() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    with _client(handler) as client:
        assert probe_api(["a.pdf"], "https://x", client=client) == {"a.pdf": -1}


def test_probe_store_returns_only_what_the_bucket_lacks() -> None:
    held = {"present.pdf"}
    absent = probe_store(["present.pdf", "gone.pdf"], lambda rel: object() if rel in held else None)
    assert absent == frozenset({"gone.pdf"})


# --- end to end ---------------------------------------------------------------
def test_audit_reproduces_the_2149_shape(tmp_path: Path) -> None:
    """Both causes at once: a Lima-only gate, and an object missing from the bucket."""
    _bundle(tmp_path, "lima", [("oepa/served.pdf", True), ("oepa/gone.pdf", True)])
    _bundle(tmp_path, "findlay", [("findlay/blocked.pdf", True)])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/published-documents.json":
            return httpx.Response(200, json={"rels": ["oepa/served.pdf", "oepa/gone.pdf"]})
        return httpx.Response(200 if request.url.path.endswith("served.pdf") else 404)

    with _client(handler) as client:
        result = audit(
            base_url="https://x",
            bundles_root=tmp_path,
            slugs=["lima", "findlay"],
            client=client,
            store_head=lambda rel: None if rel == "oepa/gone.pdf" else object(),
        )

    assert (result.offered, result.gate_size, result.served) == (3, 2, 1)
    assert [f.rel for f in result.unserved] == ["oepa/gone.pdf"]
    assert [f.rel for f in result.ungated] == ["findlay/blocked.pdf"]
    assert [f.rel for f in result.store_absent] == ["oepa/gone.pdf"]
    assert not result.ok


def test_audit_is_green_when_every_offered_document_serves(tmp_path: Path) -> None:
    _bundle(tmp_path, "lima", [("oepa/a.pdf", True), ("oepa/withheld.pdf", False)])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/published-documents.json":
            # The withheld rel is absent from the gate AND unoffered — no finding either way.
            return httpx.Response(200, json={"rels": ["oepa/a.pdf"]})
        return httpx.Response(200)

    with _client(handler) as client:
        result = audit(base_url="https://x", bundles_root=tmp_path, slugs=["lima"], client=client)

    assert result.ok
    assert (result.offered, result.served) == (1, 1)
    assert result.gate_only == []
