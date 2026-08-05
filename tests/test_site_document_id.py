"""Stable document handles (#1887) — and the cross-runtime parity that keeps citations alive.

The handle is minted in three runtimes: Node (the Astro build), the Workers runtime (the
legacy-path redirect and `/ask` citation rendering), and here (retrieval / MCP `search_passages`
citations). Nothing raises if they disagree — a drifted handle just 404s every document
citation, quietly. So the golden vectors committed beside the TypeScript implementation are
asserted from both sides, and this module is the Python half of that guard.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from watermark.site.document_id import (
    DOCUMENT_ID_LENGTH,
    DOCUMENT_ID_PINS,
    doc_permalink,
    doc_permalink_for_rel,
    document_id,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = REPO_ROOT / "web" / "packages" / "core" / "src"
VECTORS_PATH = CORE_SRC / "__fixtures__" / "document-id-vectors.json"
LIMA_DOCUMENTS = REPO_ROOT / "web" / "sites" / "lima" / "feeds" / "documents.json"

# Crockford base32, lower-cased — deliberately without i/l/o/u.
ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"


def _vectors() -> list[dict[str, str]]:
    data = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))
    vectors: list[dict[str, str]] = data["vectors"]
    return vectors


def _lima_rels() -> list[str]:
    collections = json.loads(LIMA_DOCUMENTS.read_text(encoding="utf-8"))
    return [entry["rel"] for collection in collections for entry in collection["entries"]]


@pytest.mark.parametrize("vector", _vectors(), ids=lambda v: v["note"])
def test_matches_the_frontend_golden_vectors(vector: dict[str, str]) -> None:
    """THE parity guard: `documentId.test.ts` asserts this same file from Node.

    If this fails, fix the implementation — never the fixture. A changed vector invalidates every
    document citation already published against the old handle.
    """
    assert document_id(vector["rel"]) == vector["id"]


def test_vectors_cover_the_multibyte_cases_that_break_cross_runtime_hashes() -> None:
    """UTF-8 width is where a JS/Python hash port actually diverges — JS iterates UTF-16 units."""
    notes = " ".join(v["note"] for v in _vectors())
    assert "2-byte UTF-8" in notes
    assert "3-byte UTF-8" in notes
    assert "4-byte UTF-8" in notes


def test_handles_are_fixed_width_lowercase_crockford() -> None:
    for rel in _lima_rels():
        handle = document_id(rel)
        assert len(handle) == DOCUMENT_ID_LENGTH
        assert set(handle) <= set(ALPHABET)


def test_ambiguous_glyphs_never_appear() -> None:
    """i/l/o/u are excluded so a handle re-typed off a filing can't collide via 1/l or 0/O."""
    seen = {char for rel in _lima_rels() for char in document_id(rel)}
    assert not (seen & set("ilou"))


def test_no_collision_across_the_committed_corpus() -> None:
    rels = _lima_rels()
    # 3247 → 3250 (#1966): refreshing the lagging committed Lima bundle surfaced three `odd/`
    # documents it predated — the DeWine tax-exemption-pause release and two Ohio Tax Credit
    # Authority minutes. Reviewed: all 3250 handles are distinct.
    assert len(rels) == 3250, "a corpus change belongs in review, not a silent collision"
    assert len({document_id(rel) for rel in rels}) == len(rels)


def test_rel_is_taken_verbatim() -> None:
    """The rel is the as-received custody path; normalizing here would fork its definition."""
    assert document_id("A/B.pdf") != document_id("a/b.pdf")
    distinct = {document_id(r) for r in ("a/b c.pdf", "a/b%20c.pdf", "a/b&c.pdf", "a/b#c.pdf")}
    assert len(distinct) == 4


def test_pins_are_empty_and_match_the_frontend() -> None:
    """Both sides ship no pins, so every handle is reproducible from the corpus alone.

    Reads the pin literal out of the TypeScript source rather than re-declaring the expectation:
    an entry added on one side only would silently break the other runtime's resolution.
    """
    assert DOCUMENT_ID_PINS == {}
    ts_source = (CORE_SRC / "documentId.ts").read_text(encoding="utf-8")
    body = ts_source.split("DOCUMENT_ID_PINS: Readonly<Record<string, string>> = {", 1)[1]
    body = body.split("};", 1)[0]
    declared = [ln for ln in body.splitlines() if ln.strip() and not ln.strip().startswith("//")]
    assert declared == [], f"frontend declares pins Python does not carry: {declared}"


def test_pin_wins_over_the_derivation(monkeypatch: pytest.MonkeyPatch) -> None:
    rel = "oepa/van-wert/moved.pdf"
    derived = document_id(rel)
    monkeypatch.setitem(DOCUMENT_ID_PINS, rel, "zzzzzzzz")
    assert document_id(rel) == "zzzzzzzz" != derived
    assert document_id("oepa/van-wert/other.pdf") != "zzzzzzzz"


def test_permalink_is_flat_regardless_of_corpus_depth() -> None:
    deepest = max(_lima_rels(), key=lambda rel: rel.count("/"))
    assert deepest.count("/") == 11  # 12 segments — the route it replaces rendered at 16
    assert doc_permalink_for_rel(deepest).strip("/").count("/") == 1
    assert doc_permalink("7k3m9qpb") == "/doc/7k3m9qpb/"
