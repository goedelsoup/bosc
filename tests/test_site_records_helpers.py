"""Pure record-classification helpers in site/records.py (#620)."""

from __future__ import annotations

from watermark.site.records import (
    _approx_paths,
    _cited_pages,
    _classify,
    _normalize_source_rel,
    _Record,
    _record_title,
    _source_ref,
)


def test_approx_paths_finds_every_tilde_scalar() -> None:
    # The ~-marker survives in the raw YAML as a string; _approx_paths reports its dotted
    # path so the bundle carries the approximate flag as data (#60 / #612).
    data = {
        "total": "~14223081",
        "precise": 600000,
        "section": {"drainage": "~1068530", "roadway": "12000"},
        "items": ["~5", "9", {"q": "~2"}],
    }
    assert _approx_paths(data) == ["total", "section.drainage", "items.0", "items.2.q"]
    assert _approx_paths({"a": "1.5"}) == []  # no marker → nothing
    assert _approx_paths("~9") == [""]  # a bare scalar


def test_classify_recognizes_block_genres_and_opc() -> None:
    assert _classify({"deed": {"grantee": "X"}}) == ("deeds", {"grantee": "X"})
    assert _classify({"permit": {"permit_no": "2PH"}}) == ("permits-npdes", {"permit_no": "2PH"})
    assert _classify({"action": {"agency": "OEPA"}})[0] == "permits-epa"
    # OPC is whole-document: the estimate block (if present) is the payload.
    assert _classify({"estimate": {"name": "OPC"}}) == ("opc", {"name": "OPC"})
    # Unrecognized shapes / non-dicts → None.
    assert _classify({"unknown": 1}) is None
    assert _classify(["not", "a", "dict"]) is None


def test_classify_publishes_whole_document_genres() -> None:
    """A filed case and a conveyance register are whole-document genres (#1724).

    Their subject is spread across the top level, not carried by one block, so the payload is
    the document minus its envelope — keying `litigation` to the `case:` block alone would
    publish a docket stub and drop the parties, counts and relief the filing pleads.
    """
    filing = {
        "source_path": "data/documents/legal/x/1.pdf",  # envelope — never a subject field
        "case": {"caption": "A v. B", "case_no": "3:26-cv-1"},
        "counts": ["I. Takings"],
    }
    group, payload = _classify(filing)  # type: ignore[misc]
    assert group == "litigation"
    assert payload == {"case": filing["case"], "counts": ["I. Takings"]}

    register = {"assembly": "The Hub", "conveyances": [{"grantee": "SPE I", "acres": 47.6}]}
    assert _classify(register) == ("land-assembly", register)

    # A register is NOT filed under `deeds` — that group is instrument-level, one vision read
    # per recorder PDF, and an instrument block still wins when both shapes are present.
    assert _classify({"deed": {"grantee": "X"}, "conveyances": [{"grantee": "X"}]})[0] == "deeds"  # type: ignore[index]
    # An empty list is no register at all.
    assert _classify({"conveyances": []}) is None


def test_source_ref_resolves_either_provenance_shape() -> None:
    """A structured read of a filed instrument points at its source with a `source:` block
    rather than the vision extractor's top-level `source_path` (#1724) — both must resolve, or
    the record can't link to the document it was read from."""
    assert _source_ref({"source_path": "data/documents/a.pdf"}) == "data/documents/a.pdf"
    block = {"source": {"instrument": "federal-complaint", "file": "data/documents/b.pdf"}}
    assert _source_ref(block) == "data/documents/b.pdf"
    assert _normalize_source_rel(_source_ref(block)) == "b.pdf"
    assert _source_ref({"source": "a bare string, not a block"}) is None
    assert _source_ref({}) is None


def test_record_title_prefers_the_most_identifying_field() -> None:
    rec = _Record(
        rel="oepa/x.yaml",
        group="permits-npdes",
        data={},
        payload={"facility_name": "American II WWTP"},
    )
    assert _record_title(rec) == "American II WWTP"
    # Falls back to meta.program, then the file stem.
    rec2 = _Record(
        rel="aedg/roundabouts.opc.yaml",
        group="opc",
        data={},
        payload={"meta": {"program": "BOSC Roadwork"}},
    )
    assert _record_title(rec2) == "BOSC Roadwork"
    rec3 = _Record(rel="misc/cole-street.yaml", group="opc", data={}, payload={})
    assert _record_title(rec3) == "cole-street"
    # The whole-document genres (#1724): a register names itself at the top level, a filing
    # names itself in the `case:` block it keeps its caption in.
    rec4 = _Record(
        rel="urbana/land-assembly.yaml",
        group="land-assembly",
        data={},
        payload={"assembly": "Urbana Technology Hub — SR-55 & S US-68", "conveyances": []},
    )
    assert _record_title(rec4) == "Urbana Technology Hub — SR-55 & S US-68"
    rec5 = _Record(
        rel="urbana/litigation-thor-v-urbana.yaml",
        group="litigation",
        data={},
        payload={"case": {"caption": "Thor Equities, LLC et al. v. City of Urbana, Ohio et al."}},
    )
    assert _record_title(rec5) == "Thor Equities, LLC et al. v. City of Urbana, Ohio et al."


def test_cited_pages_lifts_the_zero_based_pages_read_to_a_one_based_cite() -> None:
    # `DocExtraction.pages_read` is 0-based; a citation locates a claim by the page a viewer
    # shows, so every index gains one (#1584). The findlay Round-11 award is the worked example:
    # its envelope records `[16, 17]` and its own method note says "0-based pages 16-17, printed
    # sheets 17-18".
    assert _cited_pages({"pages_read": [16, 17]}) == (17, [17, 18])
    # A single-page read is fully described by `page`; no span is emitted to repeat it.
    assert _cited_pages({"pages_read": [0]}) == (1, None)
    # Unsorted / duplicated indices normalize; the span stays a LIST because a real read is
    # often non-contiguous (data/extracted/oepa/2PE00000.npdes.yaml reads 9 pages in 4 runs).
    assert _cited_pages({"pages_read": [3, 0, 3, 1]}) == (1, [1, 2, 4])
    assert _cited_pages({"pages_read": [0, 1, 2, 3, 36, 39, 83, 84, 92]}) == (
        1,
        [1, 2, 3, 4, 37, 40, 84, 85, 93],
    )


def test_cited_pages_never_invents_a_page() -> None:
    # No envelope, an empty list, or a non-list → no page cite at all. A connector-sourced
    # extraction genuinely has no page, and guessing one would fabricate provenance.
    assert _cited_pages({}) == (None, None)
    assert _cited_pages({"pages_read": []}) == (None, None)
    assert _cited_pages({"pages_read": "pages 1-3"}) == (None, None)
    # Junk in a hand-authored list is dropped, not coerced — `bool` is an `int` subclass, so a
    # stray `true` would otherwise become page 2.
    assert _cited_pages({"pages_read": [True, "4", None, -1, 5]}) == (6, None)


def test_source_ref_resolves_the_analysis_and_connector_provenance_shapes() -> None:
    """Three further shapes were in the corpus and used to resolve to nothing (#1993).

    A record with no ``source_doc_rel`` cannot be followed to the instrument it was read from —
    it stands alone on the page. 28 of the 32 records #1993 publishes carried a provenance
    pointer the resolver simply did not know how to read.
    """
    # The analysis envelope: `provenance.source_path`, and a `provenance.sources` list.
    assert _source_ref({"provenance": {"source_path": "data/documents/a.pdf"}}) == (
        "data/documents/a.pdf"
    )
    assert _source_ref({"provenance": {"sources": ["data/documents/b.pdf"]}}) == (
        "data/documents/b.pdf"
    )
    # The connector read: `meta.sources` is a dict of NAMED lists, so every list is scanned —
    # not just `primary`, which is often absent.
    assert _source_ref({"meta": {"sources": {"self_published": ["data/documents/c.pdf"]}}}) == (
        "data/documents/c.pdf"
    )
    # A top-level `sources:` list of instrument blocks.
    assert _source_ref({"sources": [{"file": "data/documents/d.pdf"}]}) == "data/documents/d.pdf"
    # `meta.source_path` — last, so it can only fill a gap.
    assert _source_ref({"meta": {"source_path": "data/documents/e.pdf"}}) == "data/documents/e.pdf"
    # The two original shapes still win, in order.
    assert _source_ref({"source_path": "x.pdf", "provenance": {"source_path": "y.pdf"}}) == "x.pdf"
    assert _source_ref({}) is None


def test_record_title_falls_back_to_the_documents_own_self_description() -> None:
    """Below every payload probe, so it can only ever replace a filename stem (#1993).

    Two shapes carry it: the digest envelope's top-level ``subject:`` (which ``_WORKING_NOTES``
    strips from the payload, because it is the title and not a field) and a connector read's
    ``meta.subject`` / ``meta.title``.
    """
    rec = _Record(rel="a/b.yaml", group="agreements", data={"subject": "The Thing"}, payload={})
    assert _record_title(rec) == "The Thing"
    rec = _Record(rel="a/b.yaml", group="tariffs", data={"meta": {"title": "Sheet 23"}}, payload={})
    assert _record_title(rec) == "Sheet 23"
    # A payload that resolves to a real identifier keeps it.
    rec = _Record(
        rel="a/b.yaml",
        group="agreements",
        data={"subject": "The Thing"},
        payload={"entity_name": "ACME LLC"},
    )
    assert _record_title(rec) == "ACME LLC"
    # Nothing to go on → the stem, never an invention.
    assert _record_title(_Record(rel="a/b.yaml", group="opc", data={}, payload={})) == "b"
