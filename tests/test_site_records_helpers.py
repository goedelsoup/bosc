"""Pure record-classification helpers in site/records.py (#620)."""

from __future__ import annotations

from watermark.site.records import (
    _approx_paths,
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
