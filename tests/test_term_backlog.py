"""Tests for the wiki term-backlog harvest (#1565, epic #1560 A1).

The harvest mines investigative prose for domain terms the glossary doesn't yet define. These
pin the two passes (curated lexicon → ``terms``, mechanical acronym discovery → ``candidates``),
the already-defined filter, the noise controls (stoplist / identifier / length), and the
render/write round-trip — plus a guard that the committed ``lexicon.yaml`` parses and ships no
term the glossary already defines.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from watermark.config import Settings
from watermark.site.feeds import ConceptItem
from watermark.site.term_backlog import (
    BACKLOG_DIRNAME,
    Lexicon,
    LexiconEntry,
    ScopeBacklog,
    _normalize,
    build_glossary_index,
    harvest_backlog,
    harvest_scope,
    iter_prose_files,
    load_glossary,
    load_lexicon,
    render_backlog,
    write_backlog,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CONCEPTS_DIR = _REPO_ROOT / "data" / "concepts"


def _lexicon() -> Lexicon:
    """A small lexicon: two harvestable terms, one already-defined term, plus a stoplist."""
    return Lexicon(
        terms=[
            LexiconEntry(term="NPDES", aliases=["National Pollutant Discharge Elimination System"]),
            LexiconEntry(term="constructive denial", kind="concept", note="records-law concept"),
            # already a concept below — must be filtered out of the backlog:
            LexiconEntry(term="assimilative capacity", aliases=["dilution capacity"]),
        ],
        stopwords=["MW", "PDF", "II"],
    )


def _glossary() -> tuple[frozenset[str], int]:
    concepts = [
        ConceptItem(
            slug="assimilative-capacity",
            title="Assimilative capacity",
            aliases=["dilution capacity"],
        ),
        ConceptItem(slug="7q10", title="7Q10", aliases=["7Q10 low flow"]),
    ]
    return build_glossary_index(concepts), len(concepts)


# --- normalization --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("7Q10", "7q10"),
        ("7Q10 low flow", "7q10lowflow"),
        ("Assimilative capacity", "assimilativecapacity"),
        ("constructive-denial", "constructivedenial"),
        ("NPDES", "npdes"),
    ],
)
def test_normalize(raw: str, expected: str) -> None:
    assert _normalize(raw) == expected


def test_build_glossary_index_covers_slug_title_aliases() -> None:
    index, count = _glossary()
    assert count == 2
    assert {"assimilativecapacity", "dilutioncapacity", "7q10", "7q10lowflow"} <= index


# --- the lexicon pass -----------------------------------------------------------------------
def test_lexicon_pass_finds_undefined_skips_defined() -> None:
    index, count = _glossary()
    blob = (
        "The plant's NPDES permit sets effluent limits. A second NPDES fact sheet followed.\n"
        "The agency's constructive denial of the request was challenged. The stream's "
        "assimilative capacity was already at issue."
    )
    bl = harvest_scope(
        "sitex",
        [("data/extracted/sitex/rec.md", blob)],
        lexicon=_lexicon(),
        glossary_index=index,
        defined_count=count,
    )
    by_term = {t.term: t for t in bl.terms}
    # NPDES appears twice; constructive denial once; assimilative capacity is DEFINED → excluded.
    assert set(by_term) == {"NPDES", "constructive denial"}
    assert by_term["NPDES"].count == 2
    assert by_term["NPDES"].provenance == "lexicon"
    assert by_term["NPDES"].sources == {"data/extracted/sitex/rec.md": 2}
    assert by_term["constructive denial"].count == 1
    assert "constructive denial" in by_term["constructive denial"].example.lower()


def test_lexicon_alias_and_multiword_wrap() -> None:
    index, count = _glossary()
    # Alias hit + a phrase wrapped across a newline (harvest flattens whitespace first).
    blob = (
        "See the National Pollutant Discharge Elimination System.\nA constructive\ndenial ensued."
    )
    bl = harvest_scope(
        "s",
        [("f.md", blob)],
        lexicon=_lexicon(),
        glossary_index=index,
        defined_count=count,
        discover=False,
    )
    by_term = {t.term: t.count for t in bl.terms}
    assert by_term["NPDES"] == 1
    assert by_term["constructive denial"] == 1


def test_multi_alias_forms_stay_word_bounded() -> None:
    """A multi-alias entry must anchor *every* alternative — a middle alias must not substring-match
    (regression: an ungrouped alternation binds boundaries only to the first/last form)."""
    lexicon = Lexicon(terms=[LexiconEntry(term="RTO", aliases=["ISO", "grid operator"])])
    # "ISO" only appears inside "ISOLATED" / "PARISO" — never standalone → zero matches.
    bl = harvest_scope(
        "s",
        [("f.md", "The ISOLATED PARISO node.")],
        lexicon=lexicon,
        glossary_index=frozenset(),
        defined_count=0,
        discover=False,
    )
    assert bl.terms == []
    # A standalone alias does match.
    bl2 = harvest_scope(
        "s",
        [("f.md", "The regional ISO cleared it.")],
        lexicon=lexicon,
        glossary_index=frozenset(),
        defined_count=0,
        discover=False,
    )
    assert {t.term: t.count for t in bl2.terms} == {"RTO": 1}


def test_pattern_is_order_independent() -> None:
    """Match count must not depend on alias ordering (the compiled pattern is deterministic)."""
    text = "regional transmission organization and a standalone ISO and RTO"
    a = Lexicon(
        terms=[LexiconEntry(term="RTO", aliases=["ISO", "regional transmission organization"])]
    )
    b = Lexicon(
        terms=[LexiconEntry(term="RTO", aliases=["regional transmission organization", "ISO"])]
    )
    fa = (
        harvest_scope(
            "s",
            [("f.md", text)],
            lexicon=a,
            glossary_index=frozenset(),
            defined_count=0,
            discover=False,
        )
        .terms[0]
        .count
    )
    fb = (
        harvest_scope(
            "s",
            [("f.md", text)],
            lexicon=b,
            glossary_index=frozenset(),
            defined_count=0,
            discover=False,
        )
        .terms[0]
        .count
    )
    assert fa == fb == 3


def test_min_count_filters_low_frequency_terms() -> None:
    index, count = _glossary()
    blob = "One NPDES mention only."
    bl = harvest_scope(
        "s",
        [("f.md", blob)],
        lexicon=_lexicon(),
        glossary_index=index,
        defined_count=count,
        min_count=2,
        discover=False,
    )
    assert bl.terms == []


# --- the discovery pass ---------------------------------------------------------------------
def test_discovery_finds_acronyms_and_rejects_noise() -> None:
    index, count = _glossary()
    blob = (
        "The OPSB reviewed the OPSB filing again. The permit OHD000001 and 12 MW load and a PDF "
        "and NPDES appear too, plus a II heading."
    )
    bl = harvest_scope(
        "s",
        [("f.md", blob)],
        lexicon=_lexicon(),
        glossary_index=index,
        defined_count=count,
        min_count=1,
    )
    cands = {c.term for c in bl.candidates}
    assert "OPSB" in cands  # genuine initialism, discovered
    assert cands.isdisjoint({"MW", "PDF", "II"})  # stoplisted
    assert "OHD000001" not in cands  # identifier: >=3-digit run
    assert "NPDES" not in cands  # a lexicon surface form → never a candidate
    opsb = next(c for c in bl.candidates if c.term == "OPSB")
    assert opsb.count == 2 and opsb.provenance == "discovery"


def test_discovery_can_be_disabled() -> None:
    index, count = _glossary()
    bl = harvest_scope(
        "s",
        [("f.md", "OPSB PUCO FERC")],
        lexicon=_lexicon(),
        glossary_index=index,
        defined_count=count,
        discover=False,
    )
    assert bl.candidates == []


def test_max_candidates_caps_and_reports_total() -> None:
    index, count = _glossary()
    # Six distinct discoverable acronyms, each twice (>= discovery min_count of 2).
    tokens = ["ABC", "DEF", "GHI", "JKL", "MNO", "PQR"]
    blob = " ".join(f"{t} {t}" for t in tokens)
    bl = harvest_scope(
        "s",
        [("f.md", blob)],
        lexicon=Lexicon(),
        glossary_index=index,
        defined_count=count,
        max_candidates=3,
    )
    assert len(bl.candidates) == 3
    assert bl.candidates_found == 6  # pre-cap total, for transparency


# --- prose file discovery -------------------------------------------------------------------
def test_iter_prose_files_skips_scaffolding(tmp_path: Path) -> None:
    for name in ("record.md", "README.md", "ONBOARDING.md", "CLAUDE.md", "notes.txt"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    found = {p.name for p in iter_prose_files(tmp_path)}
    assert found == {"record.md"}


def test_iter_prose_files_honors_corpus_scope(tmp_path: Path) -> None:
    from watermark.sites import CorpusScope

    (tmp_path / "sitea").mkdir()
    (tmp_path / "siteb").mkdir()
    (tmp_path / "sitea" / "rec.md").write_text("a", encoding="utf-8")
    (tmp_path / "siteb" / "rec.md").write_text("b", encoding="utf-8")
    scope = CorpusScope(include=("sitea",))
    rels = {str(p.relative_to(tmp_path)) for p in iter_prose_files(tmp_path, scope=scope)}
    assert rels == {"sitea/rec.md"}


# --- render / write -------------------------------------------------------------------------
def test_render_round_trips_to_yaml() -> None:
    index, count = _glossary()
    bl = harvest_scope(
        "s",
        [("f.md", "NPDES NPDES OPSB OPSB")],
        lexicon=_lexicon(),
        glossary_index=index,
        defined_count=count,
    )
    parsed = yaml.safe_load(render_backlog(bl))
    assert parsed["scope"] == "s"
    assert parsed["glossary_defined"] == count
    assert parsed["terms"][0]["term"] == "NPDES"
    assert parsed["candidates"][0]["term"] == "OPSB"


def test_write_backlog_skips_empty_scope(tmp_path: Path) -> None:
    empty = ScopeBacklog(scope="empty")
    assert write_backlog(empty, tmp_path) is None
    assert not any(tmp_path.iterdir())
    nonempty = harvest_scope(
        "s",
        [("f.md", "NPDES")],
        lexicon=_lexicon(),
        glossary_index=frozenset(),
        defined_count=0,
    )
    path = write_backlog(nonempty, tmp_path)
    assert path is not None and path.name == "s.yaml" and path.exists()


# --- integration against the committed lexicon / concepts -----------------------------------
def test_committed_lexicon_parses_and_avoids_defined_terms() -> None:
    lexicon = load_lexicon(_CONCEPTS_DIR)
    assert lexicon.terms, "the committed lexicon should be non-empty"
    index, _ = load_glossary(_CONCEPTS_DIR)
    # No lexicon entry should duplicate a concept the glossary already defines.
    for entry in lexicon.terms:
        keys = {_normalize(f) for f in entry.surface_forms if _normalize(f)}
        assert not (keys & index), f"lexicon term {entry.term!r} is already a defined concept"


def test_harvest_backlog_over_fixture_tree(tmp_path: Path) -> None:
    """End-to-end over a tmp data dir: a registered site's prose yields its backlog scope."""
    extracted = tmp_path / "extracted"
    (extracted / "findlay").mkdir(parents=True)
    (extracted / "findlay" / "rec.md").write_text(
        "The MARA data center connects behind-the-meter; its NPDES permit and PJM queue matter.",
        encoding="utf-8",
    )
    concepts = tmp_path / "concepts"
    concepts.mkdir()
    # An explicit lexicon, not a copy of the committed one: as A2 (#1566) authors a curated term
    # into data/concepts/, its entry migrates out of the committed lexicon, so pinning this
    # end-to-end assertion to a self-contained fixture keeps it stable.
    (concepts / "lexicon.yaml").write_text(
        "terms:\n"
        "  - term: NPDES\n"
        "    aliases: [National Pollutant Discharge Elimination System]\n"
        "  - term: PJM\n"
        "  - term: behind-the-meter\n"
        "    kind: concept\n",
        encoding="utf-8",
    )
    settings = Settings(data_dir=tmp_path)
    out = harvest_backlog(settings, sites=["findlay"], include_network=False)
    assert set(out) == {"findlay"}
    terms = {t.term for t in out["findlay"].terms}
    assert {"NPDES", "PJM", "behind-the-meter"} <= terms


def test_backlog_dirname_constant() -> None:
    assert BACKLOG_DIRNAME == "backlog"


# --- overlap resolution + homonym excludes --------------------------------------------------
def _overlap_lexicon() -> Lexicon:
    return Lexicon(
        terms=[
            LexiconEntry(term="EPA", aliases=["Environmental Protection Agency"]),
            LexiconEntry(term="OEPA", aliases=["Ohio EPA"]),
            LexiconEntry(term="variance", exclude=["mercury variance"]),
            LexiconEntry(term="dilution", exclude=["isotope dilution"]),
            LexiconEntry(term="TIF", aliases=["tax increment financing"], exclude=[".tif"]),
        ]
    )


def test_longer_alias_wins_the_overlapping_span() -> None:
    # "Ohio EPA" is attributed only to OEPA; a bare "EPA" still counts for EPA.
    text = "The Ohio EPA issued a PTI; separately the EPA agreed and the U.S. EPA concurred."
    bl = harvest_scope(
        "s",
        [("f.md", text)],
        lexicon=_overlap_lexicon(),
        glossary_index=frozenset(),
        defined_count=0,
        discover=False,
    )
    counts = {t.term: t.count for t in bl.terms}
    assert counts["OEPA"] == 1  # "Ohio EPA"
    assert counts["EPA"] == 2  # "the EPA" + "U.S. EPA" — NOT the "Ohio EPA" occurrence


@pytest.mark.parametrize(
    ("text", "term", "expected"),
    [
        ("A Streamlined Mercury Variance renewed; also a zoning variance filed.", "variance", 1),
        ("Only a Mercury Variance appears here.", "variance", None),
        ("Analyzed by isotope-dilution EPA Method 537.1 at the plant.", "dilution", None),
        ("Effluent dilution matters; isotope-dilution is a lab method.", "dilution", 1),
        ("Wrote scene.tif then formed a TIF district downtown.", "TIF", 1),
        ("The pipeline writes a dated <acq-date>.tif sidecar only.", "TIF", None),
    ],
)
def test_exclude_phrases_drop_homonyms(text: str, term: str, expected: int | None) -> None:
    bl = harvest_scope(
        "s",
        [("f.md", text)],
        lexicon=_overlap_lexicon(),
        glossary_index=frozenset(),
        defined_count=0,
        discover=False,
    )
    counts = {t.term: t.count for t in bl.terms}
    assert counts.get(term) == expected


# --- input validation -----------------------------------------------------------------------
@pytest.mark.parametrize(("min_count", "max_candidates"), [(0, 40), (-1, 40), (1, -1)])
def test_harvest_scope_rejects_bad_thresholds(min_count: int, max_candidates: int) -> None:
    with pytest.raises(ValueError):
        harvest_scope(
            "s",
            [("f.md", "NPDES")],
            lexicon=_lexicon(),
            glossary_index=frozenset(),
            defined_count=0,
            min_count=min_count,
            max_candidates=max_candidates,
        )


# --- write_backlog removes stale empty artifacts --------------------------------------------
def test_write_backlog_unlinks_stale_empty_file(tmp_path: Path) -> None:
    nonempty = harvest_scope(
        "s", [("f.md", "NPDES")], lexicon=_lexicon(), glossary_index=frozenset(), defined_count=0
    )
    path = write_backlog(nonempty, tmp_path)
    assert path is not None and path.exists()
    # A later run where the scope went empty must remove the stale file (idempotent regen).
    assert write_backlog(ScopeBacklog(scope="s"), tmp_path) is None
    assert not path.exists()


# --- CLI --site validation ------------------------------------------------------------------
def test_cli_rejects_unknown_site() -> None:
    from typer.testing import CliRunner

    from watermark.cli import app

    result = CliRunner().invoke(app, ["term-backlog", "--site", "atlantis", "--no-write"])
    assert result.exit_code != 0
    assert "unknown site" in result.output.lower()
