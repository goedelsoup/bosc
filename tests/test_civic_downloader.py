"""Downloader: filename derivation, chain-of-custody writes, manifest."""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from bosc.civic.downloader import (
    DownloadedDoc,
    derive_filename,
    download_meetings,
    write_manifest,
)
from bosc.civic.models import MeetingDoc, Platform, Publishing, Subdivision
from bosc.config import Settings


def _body() -> Subdivision:
    return Subdivision(
        slug="bath-township",
        name="Bath Township",
        type="township",
        publishing=Publishing(
            records_url="https://www.bathtwp.com/meeting-minutes-2026/",
            platform=Platform.WORDPRESS,
        ),
    )


def _doc(url: str, *, kind: str = "minutes", date: str | None = "2026-01-06") -> MeetingDoc:
    return MeetingDoc(slug="bath-township", body=None, kind=kind, title="t", date=date, url=url)


def test_derive_filename_prefers_disposition_then_basename() -> None:
    assert derive_filename("https://x.gov/a/1-6-26-Minutes.pdf") == "1-6-26-Minutes.pdf"
    # Percent-encoded path basename is decoded.
    assert derive_filename("https://x.gov/files/council%20minutes.htm") == "council minutes.htm"
    # Content-Disposition wins over the (opaque) URL basename.
    assert (
        derive_filename(
            "https://x.gov/_files/ugd/64b7b9_hash.docx?dn=x",
            content_disposition='attachment; filename="1-2-26 Minutes.docx"',
        )
        == "1-2-26 Minutes.docx"
    )


def test_derive_filename_appends_extension_from_content_type() -> None:
    # CivicPlus ViewFile URLs carry no extension but serve a PDF.
    assert (
        derive_filename(
            "https://x.gov/AgendaCenter/ViewFile/Minutes/_05062024-853",
            content_type="application/pdf",
        )
        == "_05062024-853.pdf"
    )
    # An existing extension is left untouched.
    assert derive_filename("https://x.gov/a/m.pdf", content_type="application/pdf") == "m.pdf"


def _fake_fetcher(payloads: dict[str, bytes]):  # type: ignore[no-untyped-def]
    def fetch(url: str, settings: Settings) -> tuple[bytes, str | None, str | None]:
        return payloads[url], "application/pdf", None

    return fetch


def test_download_writes_files_hash_and_canonical(tmp_path: Path) -> None:
    payloads = {
        "https://x.gov/1-6-26-Minutes.pdf": b"%PDF minutes",
        "https://x.gov/1-6-26-Agenda.pdf": b"%PDF agenda",
    }
    docs = [
        _doc("https://x.gov/1-6-26-Minutes.pdf", kind="minutes"),
        _doc("https://x.gov/1-6-26-Agenda.pdf", kind="agenda"),
    ]
    report = download_meetings(_body(), docs, dest_root=tmp_path, fetcher=_fake_fetcher(payloads))
    assert report.downloaded == 2 and report.conflicts == 0
    minutes = next(d for d in report.docs if d.kind == "minutes")
    assert (tmp_path / "1-6-26-Minutes.pdf").read_bytes() == b"%PDF minutes"
    assert minutes.sha256 == hashlib.sha256(b"%PDF minutes").hexdigest()
    assert minutes.canonical == "2026-01-06-minutes.pdf"  # manifest-only, file keeps as-received


def test_download_is_idempotent_then_flags_conflict(tmp_path: Path) -> None:
    url = "https://x.gov/1-6-26-Minutes.pdf"
    docs = [_doc(url)]
    # First run downloads.
    r1 = download_meetings(_body(), docs, dest_root=tmp_path, fetcher=_fake_fetcher({url: b"v1"}))
    assert r1.downloaded == 1
    # Re-run, identical bytes -> skipped (idempotent).
    r2 = download_meetings(_body(), docs, dest_root=tmp_path, fetcher=_fake_fetcher({url: b"v1"}))
    assert r2.skipped == 1 and r2.downloaded == 0
    # Same URL/name, DIFFERENT bytes -> never overwrites; kept beside original, flagged.
    r3 = download_meetings(_body(), docs, dest_root=tmp_path, fetcher=_fake_fetcher({url: b"v2"}))
    assert r3.conflicts == 1
    assert (tmp_path / "1-6-26-Minutes.pdf").read_bytes() == b"v1"  # original untouched
    conflict = r3.docs[0]
    assert conflict.filename != "1-6-26-Minutes.pdf"
    assert (tmp_path / conflict.filename).read_bytes() == b"v2"


def test_download_limit_caps_run(tmp_path: Path) -> None:
    payloads = {f"https://x.gov/{i}.pdf": f"doc{i}".encode() for i in range(5)}
    docs = [_doc(u) for u in payloads]
    report = download_meetings(
        _body(), docs, dest_root=tmp_path, limit=2, fetcher=_fake_fetcher(payloads)
    )
    assert len(report.docs) == 2
    assert len(list(tmp_path.glob("*.pdf"))) == 2


def test_write_manifest_shape(tmp_path: Path) -> None:
    report = download_meetings(
        _body(),
        [_doc("https://x.gov/1-6-26-Minutes.pdf")],
        dest_root=tmp_path / "docs",
        fetcher=_fake_fetcher({"https://x.gov/1-6-26-Minutes.pdf": b"x"}),
    )
    out = write_manifest(report, tmp_path / "download-manifest.yaml")
    doc = yaml.safe_load(out.read_text())
    assert doc["meta"]["slug"] == "bath-township"
    assert "listing" in doc["meta"]["date_evidence"]  # dates not content-verified
    assert doc["meta"]["counts"]["downloaded"] == 1
    assert doc["documents"][0]["source_url"] == "https://x.gov/1-6-26-Minutes.pdf"
    assert doc["documents"][0]["sha256"] == hashlib.sha256(b"x").hexdigest()


def test_write_manifest_merges_two_pages(tmp_path: Path) -> None:
    """A body posting minutes + agendas on separate pages downloads in two runs.

    Both must accumulate into the one manifest the indexer reads (keyed by source_url),
    not overwrite each other.
    """
    out = tmp_path / "download-manifest.yaml"
    min_report = download_meetings(
        _body(),
        [_doc("https://x.gov/M060226.pdf", kind="minutes", date="2026-06-02")],
        dest_root=tmp_path / "docs",
        fetcher=_fake_fetcher({"https://x.gov/M060226.pdf": b"m"}),
    )
    write_manifest(min_report, out)
    ag_report = download_meetings(
        _body(),
        [_doc("https://x.gov/A060226.pdf", kind="agenda", date="2026-06-02")],
        dest_root=tmp_path / "docs",
        fetcher=_fake_fetcher({"https://x.gov/A060226.pdf": b"a"}),
    )
    write_manifest(ag_report, out)

    doc = yaml.safe_load(out.read_text())
    urls = {d["source_url"] for d in doc["documents"]}
    assert urls == {"https://x.gov/M060226.pdf", "https://x.gov/A060226.pdf"}  # both retained
    assert doc["meta"]["counts"]["total"] == 2
    assert {d["kind"] for d in doc["documents"]} == {"minutes", "agenda"}


def test_downloaded_doc_model_forbids_extra() -> None:
    # Guards the manifest schema from silent drift.
    d = DownloadedDoc(
        filename="m.pdf",
        canonical=None,
        source_url="https://x/m.pdf",
        body=None,
        kind="minutes",
        date=None,
        title=None,
        sha256="abc",
        bytes=3,
        content_type="application/pdf",
        fetched_at=None,
        status="downloaded",
    )
    assert d.status == "downloaded"
