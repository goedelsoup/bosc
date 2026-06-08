"""Indexer: text extraction, date verification, corridor-hit scan, timeline events."""

from __future__ import annotations

import zipfile
from pathlib import Path

import yaml

from bosc.civic.indexer import (
    _date_appears,
    _verify_date,
    extract_text,
    index_meetings,
    write_index,
)
from bosc.civic.keywords import scan_text
from bosc.civic.models import Platform, Publishing, Subdivision
from bosc.config import Settings
from bosc.pipeline.timeline import _subdivision_meeting_events


def _make_docx(path: Path, text: str) -> None:
    runs = "".join(f"<w:t>{seg} </w:t>" for seg in text.split(" "))
    xml = f'<?xml version="1.0"?><w:document><w:body><w:p>{runs}</w:p></w:body></w:document>'
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", xml)


def _body() -> Subdivision:
    return Subdivision(
        slug="bath-township",
        name="Bath Township",
        type="township",
        publishing=Publishing(platform=Platform.WORDPRESS),
    )


def test_scan_text_finds_corridor_topics() -> None:
    assert scan_text("Approved rezoning for the new data center and a force main") == [
        "datacenter",
        "forcemain",
        "rezoning",
    ]
    assert scan_text("Routine road levy and a new mailbox") == []


def test_date_appears_recognizes_written_forms() -> None:
    assert _date_appears("Regular Meeting held January 6, 2026 at 7pm", "2026-01-06")
    assert _date_appears("Minutes of 1/6/2026", "2026-01-06")
    assert _date_appears("dated 1-6-26", "2026-01-06")
    assert not _date_appears("no date", "2026-01-06")
    assert not _date_appears("January 6, 2026", "")  # malformed iso


def test_verify_date_only_confirms_from_text() -> None:
    assert _verify_date("met January 6, 2026", "2026-01-06", "pdf_text") == (
        "2026-01-06",
        "pdf_text",
    )
    # Listing date NOT found in text -> unconfirmed (listing still stands separately).
    assert _verify_date("some other text", "2026-01-06", "pdf_text") == (None, "listing")
    # No text at all (image scan) -> none.
    assert _verify_date("", "2026-01-06", "none") == (None, "listing")


def test_extract_text_docx(tmp_path: Path) -> None:
    p = tmp_path / "m.docx"
    _make_docx(p, "Trustees discussed the data center easement on March 11, 2026")
    text, method = extract_text(p)
    assert method == "docx"
    assert "data center easement" in text
    # An empty/odd file is an honest "none", not a crash.
    (tmp_path / "x.pdf").write_bytes(b"not a real pdf")
    assert extract_text(tmp_path / "x.pdf") == ("", "none")


def _seed_corpus(tmp: Path, *, text: str, date: str = "2026-01-06") -> Settings:
    """A tmp data dir with one downloaded docx + its download manifest."""
    settings = Settings(data_dir=tmp)
    docs_dir = settings.documents_dir / "bath-township" / "meetings"
    _make_docx(docs_dir / "1-6-26 minutes.docx", text)
    manifest = {
        "meta": {"slug": "bath-township"},
        "documents": [
            {
                "filename": "1-6-26 minutes.docx",
                "kind": "minutes",
                "body": None,
                "date": date,
                "title": "1-6-26 minutes",
                "sha256": "abc123",
                "source_url": "https://bath.test/1-6-26-minutes.docx",
                "status": "downloaded",
            }
        ],
    }
    man_dir = settings.extracted_dir / "bath-township" / "meetings"
    man_dir.mkdir(parents=True, exist_ok=True)
    (man_dir / "download-manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    return settings


def test_index_meetings_verifies_date_and_scans_hits(tmp_path: Path) -> None:
    settings = _seed_corpus(
        tmp_path, text="Regular Meeting January 6, 2026: rezoning of the data center parcel"
    )
    report = index_meetings(_body(), settings=settings)
    assert len(report.docs) == 1
    doc = report.docs[0]
    assert doc.text_method == "docx"
    assert doc.date_verified == "2026-01-06"  # confirmed in the file's own text
    assert doc.date_evidence == "docx"
    assert doc.hits == ["datacenter", "rezoning"]


def test_index_meetings_unconfirmed_date_when_absent(tmp_path: Path) -> None:
    settings = _seed_corpus(tmp_path, text="Routine business, no date or topics here")
    doc = index_meetings(_body(), settings=settings).docs[0]
    assert doc.date_verified is None
    assert doc.date_evidence == "listing"  # listing date still stands, just unconfirmed
    assert doc.hits == []
    assert doc.date == "2026-01-06"  # falls back to listing


def test_subdivision_meeting_events_surface_only_corridor_hits(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    idx = {
        "meta": {"slug": "shawnee-township"},
        "documents": [
            {
                "kind": "minutes",
                "body": None,
                "date_verified": "2026-02-09",
                "date_listing": "2026-02-09",
                "hits": ["datacenter", "annexation"],
                "filename": "a.pdf",
            },
            {
                "kind": "minutes",
                "body": None,
                "date_verified": None,
                "date_listing": "2026-03-01",
                "hits": [],
                "filename": "b.pdf",
            },  # no hits -> not on timeline
        ],
    }
    out = settings.extracted_dir / "shawnee-township" / "meetings" / "meeting-index.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(idx), encoding="utf-8")

    events = _subdivision_meeting_events(settings)
    assert len(events) == 1
    e = events[0]
    assert e.category == "subdivision_meeting"
    assert e.date == "2026-02-09"
    assert "Shawnee Township" in e.title
    assert "datacenter" in e.detail


def test_write_index_shape(tmp_path: Path) -> None:
    settings = _seed_corpus(tmp_path, text="data center on January 6, 2026")
    report = index_meetings(_body(), settings=settings)
    out = write_index(report, tmp_path / "meeting-index.yaml")
    doc = yaml.safe_load(out.read_text())
    assert doc["meta"]["slug"] == "bath-township"
    assert "NO OCR" in doc["meta"]["text_extraction"]
    assert doc["meta"]["counts"]["with_corridor_hits"] == 1
    assert doc["documents"][0]["date_verified"] == "2026-01-06"


def test_extract_text_ocr_fallback(tmp_path: Path, monkeypatch: object) -> None:
    from pypdf import PdfWriter

    from bosc.civic import indexer

    p = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)  # a valid PDF with no text layer
    with p.open("wb") as f:
        writer.write(f)

    # No text layer, OCR off -> honest empty (the default behaviour).
    assert indexer.extract_text(p, ocr=False) == ("", "none")

    # OCR on -> routes to ocr_pdf. Monkeypatched so the suite never calls tesseract.
    monkeypatch.setattr(  # type: ignore[attr-defined]
        indexer, "ocr_pdf", lambda path, **kw: "Data center rezoning on February 9, 2026"
    )
    text, method = indexer.extract_text(p, ocr=True)
    assert method == "ocr"
    assert "data center" in text.lower()
    assert scan_text(text) == ["datacenter", "rezoning"]
