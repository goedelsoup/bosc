"""#1522 — per-site meeting-tree nesting + corpus-scope reconciliation (cross-site loader phase 2).

Lima's six meeting-holding bodies stay flat at ``<body>/meetings/``; every peer nests one level
deeper under its site slug at ``<site>/<body>/meetings/`` so its default corpus scope ``(slug,)``
owns the subtree for free and Lima's whole-tree-minus-peers scope excludes it. This module locks:

* the write-side layout (:func:`~watermark.civic.layout.meetings_dir`) + a download round-trip;
* the read-side bounded glob (:func:`~watermark.pipeline.corpus.iter_meeting_artifacts`);
* the design decision the epic flagged — a recursive read must not leak a nested peer tree into
  Lima (the #1505 invariant), resolved with an explicit scope test **first**;
* isolation in **both directions** across every meeting read surface (committed summaries, the
  timeline, and the retrieval iterator).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from watermark.civic.downloader import download_meetings
from watermark.civic.layout import meetings_dir
from watermark.civic.models import MeetingDoc, Platform, Publishing, Subdivision
from watermark.civic.summarize import load_committed_summaries
from watermark.config import Settings
from watermark.pipeline.corpus import (
    assert_meeting_layout_depth,
    iter_meeting_artifacts,
    relpath_in_scope,
)
from watermark.pipeline.timeline import _subdivision_meeting_events
from watermark.retrieval.ingestion import iter_extracted_chunks
from watermark.sites import SITES, active_profile, effective_corpus_scope

# A registered peer with the plain default corpus scope (unset `corpus_relpaths`, so purely its
# eponymous prefixes) — the epic's happy path: `<site>/<body>/meetings/` under the bare slug. This
# was findlay until #1460 gave that site a second prefix; what keeps it explicit today is #1463's
# `legal/one-energy-v-allen-twp`, filed by CASE name rather than by site (#1460's own `oepa/findlay`
# is eponymous and derived since #1405). The case under test here is the UNSET one, so it moved to
# another Maumee peer.
PEER = "defiance"
PEER_BODY = "allen-cty-comm"
LIMA_BODY = "commissioners"  # one of Lima's six flat bodies


# --- the design decision (resolve FIRST, per the epic's blocking checkbox) -------------------


def test_lima_scope_excludes_a_nested_peer_meeting_tree() -> None:
    """The interaction the epic flagged: making the meeting read recursive must NOT let a nested
    ``<peer>/<body>/meetings/`` tree into Lima. It doesn't — Lima's whole-tree-minus-peers scope
    subtracts every peer's prefixes, and a peer's default scope includes its bare slug, so the
    nested tree lands in **exactly one** site (#1505). No recursive glob can undo the predicate.
    """
    nested = f"{PEER}/{PEER_BODY}/meetings/meeting-index.yaml"
    flat = f"{LIMA_BODY}/meetings/meeting-index.yaml"

    lima = effective_corpus_scope(SITES["lima"])
    assert PEER in lima.exclude  # the peer's bare slug is subtracted from Lima
    assert not relpath_in_scope(nested, lima)  # ... so its nested meetings are out of Lima
    assert relpath_in_scope(flat, lima)  # Lima's own flat body stays in

    peer = effective_corpus_scope(SITES[PEER])
    assert peer.include == (f"*/{PEER}", PEER)  # unset scope → its two eponymous prefixes (#1405)
    assert relpath_in_scope(nested, peer)  # ... which owns the nested tree for free
    assert not relpath_in_scope(flat, peer)  # and never Lima's flat bodies


# --- write side: the layout helper + a real download round-trip ------------------------------


def test_meetings_dir_flat_for_lima_nested_for_peer(tmp_path: Path) -> None:
    lima = Settings(data_dir=tmp_path, site="lima")
    peer = Settings(data_dir=tmp_path, site=PEER)
    for root in (lima.documents_dir, lima.extracted_dir):
        assert meetings_dir(root, LIMA_BODY, lima) == root / LIMA_BODY / "meetings"
    for root in (peer.documents_dir, peer.extracted_dir):
        assert meetings_dir(root, PEER_BODY, peer) == root / PEER / PEER_BODY / "meetings"


def _fetcher(payload: bytes = b"%PDF x"):  # type: ignore[no-untyped-def]
    def fetch(url: str, settings: Settings) -> tuple[bytes, str | None, str | None]:
        return payload, "application/pdf", None

    return fetch


def _body(slug: str) -> Subdivision:
    return Subdivision(
        slug=slug,
        name=slug.replace("-", " ").title(),
        type="county",
        publishing=Publishing(records_url="https://x.gov/records", platform=Platform.WORDPRESS),
    )


def test_download_writes_under_the_peer_nested_tree(tmp_path: Path) -> None:
    """With no dest override, a peer's binaries land under ``documents/<site>/<body>/meetings/`` —
    never the flat body-slug path that would collide with Lima's namespace."""
    peer = Settings(data_dir=tmp_path, site=PEER)
    docs = [
        MeetingDoc(
            slug=PEER_BODY,
            body=None,
            kind="minutes",
            title="t",
            date="2026-01-06",
            url="https://x.gov/m.pdf",
        )
    ]
    report = download_meetings(_body(PEER_BODY), docs, settings=peer, fetcher=_fetcher())
    assert report.downloaded == 1
    assert (tmp_path / "documents" / PEER / PEER_BODY / "meetings" / "m.pdf").exists()
    # The flat body-slug path (Lima's namespace) is untouched.
    assert not (tmp_path / "documents" / PEER_BODY / "meetings" / "m.pdf").exists()


def test_download_stays_flat_for_lima(tmp_path: Path) -> None:
    lima = Settings(data_dir=tmp_path, site="lima")
    docs = [
        MeetingDoc(
            slug=LIMA_BODY,
            body=None,
            kind="minutes",
            title="t",
            date="2026-01-06",
            url="https://x.gov/m.pdf",
        )
    ]
    download_meetings(_body(LIMA_BODY), docs, settings=lima, fetcher=_fetcher())
    assert (tmp_path / "documents" / LIMA_BODY / "meetings" / "m.pdf").exists()


# --- read side: the bounded glob ------------------------------------------------------------


def test_iter_meeting_artifacts_covers_both_depths_but_is_bounded(tmp_path: Path) -> None:
    """Finds Lima's flat (1-segment) and a peer's nested (2-segment) trees, and — being two bounded
    globs, not a ``**`` walk — deliberately does NOT descend to a spurious 3-segment tree."""
    flat = tmp_path / LIMA_BODY / "meetings" / "meeting-index.yaml"
    nested = tmp_path / PEER / PEER_BODY / "meetings" / "meeting-index.yaml"
    too_deep = tmp_path / "a" / "b" / "c" / "meetings" / "meeting-index.yaml"
    other_name = tmp_path / LIMA_BODY / "meetings" / "meeting-summaries.yaml"
    for p in (flat, nested, too_deep, other_name):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("meta: {}\n", encoding="utf-8")

    found = iter_meeting_artifacts(tmp_path, "meeting-index.yaml")
    assert found == sorted([flat, nested])  # bounded to the two real layouts; other name ignored


# --- isolation, both directions, across every meeting read surface ---------------------------


def _seed_index(settings: Settings, rel_dir: str, slug: str) -> None:
    """A meeting-index with one corridor-hitting, dated meeting (surfaces on the timeline)."""
    p = settings.extracted_dir / rel_dir / "meetings" / "meeting-index.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        yaml.safe_dump(
            {
                "meta": {"slug": slug},
                "documents": [
                    {
                        "filename": f"{slug}.pdf",
                        "kind": "minutes",
                        "date_verified": "2026-03-01",
                        "hits": ["datacenter"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _seed_summaries(settings: Settings, rel_dir: str, slug: str) -> None:
    p = settings.extracted_dir / rel_dir / "meetings" / "meeting-summaries.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        yaml.safe_dump(
            {
                "meta": {"slug": slug},
                "meetings": [{"date": "2026-03-01", "kind": "minutes", "filename": f"{slug}.pdf"}],
            }
        ),
        encoding="utf-8",
    )


def _seed_both_layouts(tmp_path: Path) -> None:
    """One Lima flat body + one peer nested body under the same extracted tree."""
    scratch = Settings(data_dir=tmp_path)  # only used to resolve extracted_dir (site-agnostic)
    _seed_index(scratch, LIMA_BODY, LIMA_BODY)
    _seed_summaries(scratch, LIMA_BODY, LIMA_BODY)
    _seed_index(scratch, f"{PEER}/{PEER_BODY}", PEER_BODY)
    _seed_summaries(scratch, f"{PEER}/{PEER_BODY}", PEER_BODY)


def test_committed_summaries_isolate_by_site(tmp_path: Path) -> None:
    _seed_both_layouts(tmp_path)
    lima_slugs = {
        s
        for s, _ in load_committed_summaries(
            Settings(data_dir=tmp_path, site="lima"),
            scope=effective_corpus_scope(active_profile(Settings(data_dir=tmp_path, site="lima"))),
        )
    }
    peer_slugs = {
        s
        for s, _ in load_committed_summaries(
            Settings(data_dir=tmp_path, site=PEER),
            scope=effective_corpus_scope(active_profile(Settings(data_dir=tmp_path, site=PEER))),
        )
    }
    assert lima_slugs == {LIMA_BODY}  # Lima sees its flat body, never the nested peer's
    assert peer_slugs == {PEER_BODY}  # the peer sees only its own nested body, never Lima's


def test_timeline_meeting_events_isolate_by_site(tmp_path: Path) -> None:
    _seed_both_layouts(tmp_path)
    lima = Settings(data_dir=tmp_path, site="lima")
    peer = Settings(data_dir=tmp_path, site=PEER)

    # This is a *provenance-isolation* test, not a vocabulary test: pass an explicit corridor
    # vocab so the seeded ``datacenter`` meeting surfaces for BOTH sites regardless of each
    # profile's own ``corridor_subjects`` (the peer, defiance, declares none by default — #1523).
    # Per-site vocabulary selection has its own coverage in tests/test_civic_indexer.py.
    lima_events = _subdivision_meeting_events(
        lima, effective_corpus_scope(active_profile(lima)), subjects=("datacenter",)
    )
    peer_events = _subdivision_meeting_events(
        peer, effective_corpus_scope(active_profile(peer)), subjects=("datacenter",)
    )

    assert {e.source for e in lima_events} == {f"{LIMA_BODY}/meetings/meeting-index.yaml"}
    # The peer event cites its real NESTED path (provenance follows the layout, #1522).
    assert {e.source for e in peer_events} == {f"{PEER}/{PEER_BODY}/meetings/meeting-index.yaml"}


def test_retrieval_iterator_isolates_meeting_trees_by_site(tmp_path: Path) -> None:
    """The RAG iterator (already ``rglob`` + scope-gated) never crosses a site's meeting trees:
    site B's nested meetings never appear in site A's rows, in either direction (#1504/#1505)."""
    _seed_both_layouts(tmp_path)
    extracted = tmp_path / "extracted"

    lima_sources = {c.source_path for c in iter_extracted_chunks(extracted, site="lima")}
    peer_sources = {c.source_path for c in iter_extracted_chunks(extracted, site=PEER)}

    assert any(s.startswith(f"{LIMA_BODY}/meetings/") for s in lima_sources)
    assert not any(s.startswith(f"{PEER}/") for s in lima_sources)  # peer nested excluded from Lima
    assert all(s.startswith(f"{PEER}/{PEER_BODY}/meetings/") for s in peer_sources)
    assert peer_sources  # the peer does index its own nested meetings


# --- the depth contract, made explicit (#1839) ----------------------------------------------


def test_layout_depth_tripwire_accepts_both_real_layouts() -> None:
    """Every path :func:`meetings_dir` can produce passes the assert the read path relies on."""
    assert_meeting_layout_depth(f"{LIMA_BODY}/meetings/meeting-index.yaml")
    assert_meeting_layout_depth(f"{PEER}/{PEER_BODY}/meetings/meeting-index.yaml")


def test_layout_depth_tripwire_rejects_a_jurisdiction_prefixed_tree() -> None:
    """The silent-invisibility case the audit called out (#1839).

    ``iter_meeting_artifacts`` globs one- and two-segment prefixes only. A peer that ever filed
    meetings under a jurisdiction-prefixed collection — ``idem/fort-wayne/<body>/meetings/``, three
    segments, the shape Fort Wayne's IDEM permits already use — would read as an empty tree with
    no error at all. Make that a failure instead.
    """
    with pytest.raises(ValueError, match="segment"):
        assert_meeting_layout_depth("idem/fort-wayne/council/meetings/meeting-index.yaml")
    with pytest.raises(ValueError, match="not a meeting artifact"):
        assert_meeting_layout_depth("commissioners/minutes/2026-01-06.yaml")


def test_meetings_dir_is_the_only_thing_that_decides_depth(tmp_path: Path) -> None:
    """The write path asserts its own output, so the two globs can't silently drift apart."""
    for slug, body in ((PEER, PEER_BODY), ("lima", LIMA_BODY)):
        settings = Settings(data_dir=tmp_path, site=slug)
        out = meetings_dir(settings.extracted_dir, body, settings)
        rel = out.relative_to(settings.extracted_dir) / "meeting-index.yaml"
        assert_meeting_layout_depth(str(rel))  # would raise if meetings_dir had not


def test_layout_depth_tripwire_rejects_a_subdirectory_under_meetings() -> None:
    """Both globs end ``meetings/<filename>`` — a nested sub-directory is just as invisible
    as a too-deep prefix, so it fails the same way (#1839)."""
    with pytest.raises(ValueError, match="direct child"):
        assert_meeting_layout_depth(f"{LIMA_BODY}/meetings/archive/meeting-index.yaml")
    with pytest.raises(ValueError, match="direct child"):
        assert_meeting_layout_depth(f"{PEER}/{PEER_BODY}/meetings/2024/meeting-index.yaml")
