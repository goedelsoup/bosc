"""#1525 — cross-site civic loader, epic close-out (phase 5).

The load-bearing guarantee of the cross-site loader (#1520): a peer site's meeting records
flow through the whole pipeline under their own nested ``<site>/<body>/meetings/`` layout and
reach the peer's published bundle — while never leaking into another site's bundle, and Lima's
whole-tree scope never swallowing a peer. Phases 1-4 each landed their own unit tests (registry
resolution, the layout helper + bounded glob, per-site corridor vocabulary, the onboard
scaffold); this module locks the two guarantees that only exist at the *ends* of the pipeline:

* a full ``download → index → summarize → export`` round-trip on a fixture peer, proving the
  nested layout is honored at every stage and a fetched byte becomes a bundle
  :class:`~watermark.site.feeds.MeetingItem`;
* the meetings *feed* isolates by site in both directions — exactly the composition the bundle
  export runs (``export_meetings(load_committed_summaries(settings, scope))``, see
  :func:`watermark.site.export.export_bundle`) — so site A's meetings never render in site B's
  bundle and Lima's bundle excludes every peer (no #1504/#1505 regression).

Complements ``tests/test_civic_meeting_nesting.py`` (layout + scope at the corpus level) by
exercising the *bundle* surface the frontend actually reads.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from watermark.agent.extractor import StructuredExtractor
from watermark.civic.downloader import download_meetings, write_manifest
from watermark.civic.indexer import index_meetings, write_index
from watermark.civic.layout import meetings_dir
from watermark.civic.models import MeetingDoc, Platform, Publishing, Subdivision
from watermark.civic.summarize import (
    load_committed_summaries,
    summarize_corridor_meetings,
    write_summaries,
)
from watermark.config import Settings
from watermark.site.meetings import export_meetings
from watermark.sites import SITES, active_profile, effective_corpus_scope

# A registered peer with the plain default corpus scope (`("findlay",)`) — the epic's happy path:
# its records nest under the bare slug. Its real profile declares NO corridor subjects (#1523),
# so the round-trip patches one in to simulate a site that has onboarded its vocabulary.
PEER = "findlay"
PEER_BODY = "allen-cty-comm"
LIMA_BODY = "commissioners"  # one of Lima's six flat bodies


def _body(slug: str) -> Subdivision:
    return Subdivision(
        slug=slug,
        name=slug.replace("-", " ").title(),
        type="county",
        publishing=Publishing(records_url="https://peer.gov/records", platform=Platform.WORDPRESS),
    )


def _html_fetcher(payload: bytes):  # type: ignore[no-untyped-def]
    """A byte fetcher returning one HTML meeting document (no network)."""

    def fetch(url: str, settings: Settings) -> tuple[bytes, str | None, str | None]:
        return payload, "text/html", None

    return fetch


# --- a hermetic StructuredExtractor (fake Anthropic client, no keys/network) ------------------

_PAYLOAD = {
    "summary": "The commission approved the data-center rezoning request.",
    "corridor_relevance": "Names the hyperscale data center on the corridor parcel.",
    "decisions": ["Motion to recommend rezoning passed 3-0"],
    "parties": ["Applicant LLC"],
    "parcels": ["36-0100-03-002.000"],
    "dollar_figures": ["$5,000,000"],
}


class _FakeMessages:
    def create(self, **_: Any) -> Any:
        block = type("B", (), {"type": "tool_use", "name": "record_extraction", "input": _PAYLOAD})
        return type("M", (), {"content": [block()]})()


class _FakeClient:
    def __init__(self) -> None:
        self.messages = _FakeMessages()


def _extractor() -> StructuredExtractor:
    return StructuredExtractor(client=_FakeClient(), settings=Settings())


# --- the round-trip: download → index → summarize → export on a fixture peer ------------------


def test_peer_round_trip_download_index_summarize_export(tmp_path: Path, monkeypatch: Any) -> None:
    """A fetched byte becomes a bundle ``MeetingItem`` — under the peer's nested layout at every
    stage — and Lima's bundle never sees it. This is the whole cross-site loader in one test.
    """
    # The peer declares one corridor subject (as it would after onboarding, from a cited source);
    # without it, #1523's honest default surfaces nothing for a fresh peer.
    peer_profile = SITES[PEER].model_copy(update={"corridor_subjects": ("datacenter",)})
    monkeypatch.setitem(SITES, PEER, peer_profile)

    peer = Settings(data_dir=tmp_path, site=PEER)
    body = _body(PEER_BODY)

    # 1. download — the raw byte lands under the peer's NESTED tree; the flat body path is untouched.
    html = (
        b"<html><body>Plan Commission, March 2, 2026: the data center project "
        b"was discussed and approved.</body></html>"
    )
    doc = MeetingDoc(
        slug=PEER_BODY,
        body=None,
        kind="minutes",
        title="March 2 minutes",
        date="2026-03-02",
        url="https://peer.gov/2026-03-02-minutes.html",
    )
    report = download_meetings(body, [doc], settings=peer, fetcher=_html_fetcher(html))
    assert report.downloaded == 1
    nested = tmp_path / "documents" / PEER / PEER_BODY / "meetings" / "2026-03-02-minutes.html"
    assert nested.exists()  # documents/<site>/<body>/meetings/... — the peer's own namespace
    assert not (tmp_path / "documents" / PEER_BODY / "meetings").exists()  # never Lima's flat path
    write_manifest(
        report, meetings_dir(peer.extracted_dir, PEER_BODY, peer) / "download-manifest.yaml"
    )

    # 2. index — reads the nested manifest, scans the file's own text, verifies the date.
    idx = index_meetings(body, settings=peer)
    assert len(idx.docs) == 1
    assert "datacenter" in idx.docs[0].hits  # the corridor topic is found in the real text
    assert idx.docs[0].date_verified == "2026-03-02"  # restated in the document ("March 2, 2026")
    write_index(idx, meetings_dir(peer.extracted_dir, PEER_BODY, peer) / "meeting-index.yaml")

    # 3. summarize — selects the corridor meeting under the PEER's own vocab, writes summaries.
    summ = summarize_corridor_meetings(body, settings=peer, extractor=_extractor())
    assert [e.filename for e in summ.entries] == ["2026-03-02-minutes.html"]
    write_summaries(
        summ, meetings_dir(peer.extracted_dir, PEER_BODY, peer) / "meeting-summaries.yaml"
    )

    # 4. export — the peer's bundle carries exactly its one meeting.
    peer_feed = export_meetings(
        load_committed_summaries(peer, scope=effective_corpus_scope(active_profile(peer)))
    )
    assert [m.slug for m in peer_feed] == [PEER_BODY]
    assert peer_feed[0].date == "2026-03-02"
    assert "datacenter" in peer_feed[0].hits
    assert peer_feed[0].decisions == ["Motion to recommend rezoning passed 3-0"]

    # ... and Lima's bundle never sees the peer's nested meeting (whole-tree-minus-peers scope).
    lima = Settings(data_dir=tmp_path, site="lima")
    lima_feed = export_meetings(
        load_committed_summaries(lima, scope=effective_corpus_scope(active_profile(lima)))
    )
    assert lima_feed == []


# --- the bundle feed isolates by site, both directions ----------------------------------------


def _seed_summaries(settings: Settings, rel_dir: str, slug: str, *, date: str) -> None:
    """Write a committed ``meeting-summaries.yaml`` (the reviewed artifact export publishes)."""
    p = settings.extracted_dir / rel_dir / "meetings" / "meeting-summaries.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        yaml.safe_dump(
            {
                "meta": {"slug": slug},
                "meetings": [
                    {
                        "date": date,
                        "kind": "minutes",
                        "filename": f"{slug}-{date}.pdf",
                        "hits": ["datacenter"],
                        "summary": f"{slug} discussed the corridor.",
                        "corridor_relevance": "Names the data center.",
                        "decisions": [],
                        "parties": [],
                        "parcels": [],
                        "dollar_figures": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_meetings_feed_isolates_by_site_in_both_bundle_directions(tmp_path: Path) -> None:
    """The exact bundle composition (``export_meetings(load_committed_summaries(..., scope))``):
    a Lima flat body and a peer nested body coexist on disk, but each site's bundle carries only
    its own meetings — no re-gating on vocab, purely the corpus scope over the two layouts.
    """
    scratch = Settings(data_dir=tmp_path)  # site-agnostic; only resolves extracted_dir
    _seed_summaries(scratch, LIMA_BODY, LIMA_BODY, date="2026-01-05")
    _seed_summaries(scratch, f"{PEER}/{PEER_BODY}", PEER_BODY, date="2026-03-02")

    lima = Settings(data_dir=tmp_path, site="lima")
    peer = Settings(data_dir=tmp_path, site=PEER)

    lima_feed = export_meetings(
        load_committed_summaries(lima, scope=effective_corpus_scope(active_profile(lima)))
    )
    peer_feed = export_meetings(
        load_committed_summaries(peer, scope=effective_corpus_scope(active_profile(peer)))
    )

    assert {m.slug for m in lima_feed} == {LIMA_BODY}  # Lima's bundle: only its flat body
    assert {m.slug for m in peer_feed} == {PEER_BODY}  # the peer's bundle: only its nested body
    # The load-bearing assertion, stated in both directions: neither bundle carries the other's.
    assert PEER_BODY not in {m.slug for m in lima_feed}
    assert LIMA_BODY not in {m.slug for m in peer_feed}
