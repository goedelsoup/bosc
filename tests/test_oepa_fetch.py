"""Unit tests for watermark.oepa.fetch — the filename-map merge (#1406).

All tests are offline: they build ``FetchedPermit`` records by hand and merge them into a
tmp-path manifest. Nothing touches the network.

The property under test is chain of custody. Ohio EPA re-serves a permit's DAM slot IN PLACE
when the permit is modified, so one URL yields different bytes at different times — the Van Wert
``permits/doc/2PD00006.pdf`` slot carried the *VD renewal in June 2026 and the *WD modification
in July. Both files are on disk under the fetcher's collision rule, so the manifest must keep a
provenance row for each, and the reviewed fields a human added to a row must survive a re-fetch
of the same bytes.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
import structlog
import yaml

from watermark.oepa.fetch import (
    FetchedPermit,
    _basename,
    _pdf_is_complete,
    _refusal,
    fetch_one,
    update_filename_map,
)

_URL = "https://dam.assets.ohio.gov/image/upload/epa.ohio.gov/Portals/35/permits/doc/2PD00006.pdf"


def _record(
    sha: str, *, filename: str = "2PD00006.pdf", status: str = "downloaded"
) -> FetchedPermit:
    return FetchedPermit(
        filename=filename,
        permit_id="2PD00006",
        source_url=_URL,
        sha256=sha,
        bytes=len(sha),
        content_type="application/pdf",
        fetched_at="2026-08-01T00:00:00+00:00",
        status=status,  # type: ignore[arg-type]
    )


def _documents(path: Path) -> list[dict[str, object]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return list(data["documents"])


def test_same_url_different_bytes_keeps_both_rows(tmp_path: Path) -> None:
    """A slot that later serves different bytes must not overwrite the earlier capture."""
    path = tmp_path / "filename-map.yaml"
    update_filename_map([_record("aaaa" * 16)], path)
    update_filename_map(
        [_record("bbbb" * 16, filename="2PD00006.bbbbbbbb.pdf", status="conflict")], path
    )

    rows = _documents(path)
    assert [r["sha256"] for r in rows] == ["aaaa" * 16, "bbbb" * 16]
    assert [r["filename"] for r in rows] == ["2PD00006.pdf", "2PD00006.bbbbbbbb.pdf"]


def test_refetching_identical_bytes_updates_in_place(tmp_path: Path) -> None:
    """The same URL *and* the same hash is the same capture — one row, not two."""
    path = tmp_path / "filename-map.yaml"
    update_filename_map([_record("aaaa" * 16)], path)
    update_filename_map([_record("aaaa" * 16, status="skipped_existing")], path)

    rows = _documents(path)
    assert len(rows) == 1
    assert rows[0]["status"] == "skipped_existing"


def test_reviewed_fields_survive_a_refetch(tmp_path: Path) -> None:
    """``canonical_name`` / ``content_verified_date`` / ``as_received_name`` and a reviewed note
    are the human half of the manifest and are not derivable from an HTTP response."""
    path = tmp_path / "filename-map.yaml"
    update_filename_map([_record("aaaa" * 16)], path)

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["meta"]["subject"] = "hand-authored subject"
    data["documents"][0].update(
        {
            "canonical_name": "2PD00006*VD as issued on renewal",
            "content_verified_date": "2025-04-18",
            "as_received_name": "2PD00006.pdf",
            "note": "SUPERSEDED IN THE SLOT, NOT IN THE RECORD.",
        }
    )
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    update_filename_map([_record("aaaa" * 16, status="skipped_existing")], path)

    merged = yaml.safe_load(path.read_text(encoding="utf-8"))
    row = merged["documents"][0]
    assert row["canonical_name"] == "2PD00006*VD as issued on renewal"
    assert row["content_verified_date"] == "2025-04-18"
    assert row["as_received_name"] == "2PD00006.pdf"
    assert row["note"] == "SUPERSEDED IN THE SLOT, NOT IN THE RECORD."
    assert merged["meta"]["subject"] == "hand-authored subject"
    assert merged["meta"]["generated_at"]  # refreshed, not dropped


def test_reviewed_note_does_not_mask_a_fetch_error(tmp_path: Path) -> None:
    """A reviewed note outranks the fetcher's boilerplate — but never an error message."""
    path = tmp_path / "filename-map.yaml"
    update_filename_map([_record("aaaa" * 16)], path)

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["documents"][0]["note"] = "reviewed note"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    failed = _record("aaaa" * 16, status="error").model_copy(
        update={"note": "fetch failed: ConnectError: nope"}
    )
    update_filename_map([failed], path)

    assert _documents(path)[0]["note"] == "fetch failed: ConnectError: nope"


def test_hand_authored_entries_survive_a_fetch(tmp_path: Path) -> None:
    """A curated entry has no ``source_url`` and must be preserved verbatim.

    The urbana and west-union maps predate this fetcher and key their documents by
    ``edoc_id``. Reading such an entry as a fetch record raised ``KeyError: 'source_url'``,
    which blocked ``watermark oepa fetch`` outright on any site holding a curated map.
    """
    map_path = tmp_path / "filename-map.yaml"
    curated = {
        "edoc_id": "2784672",
        "filename": "2784672.pdf",
        "canonical": "oepa-1pd00011-urbana-wpcf-inspection-2024-03.pdf",
        "content_verified": "text-layer",
    }
    map_path.write_text(
        yaml.safe_dump({"meta": {"subject": "curated"}, "documents": [curated]}),
        encoding="utf-8",
    )

    update_filename_map([_record("aa")], map_path)

    documents = _documents(map_path)
    assert curated in documents, "the hand-authored entry was dropped or rewritten"
    # The fetched record is appended after it, not merged into it.
    assert documents[0] == curated
    assert documents[1]["source_url"] == _URL
    # A hand-authored ``meta`` still survives.
    assert yaml.safe_load(map_path.read_text())["meta"]["subject"] == "curated"


def test_curated_entries_are_not_duplicated_across_repeat_fetches(tmp_path: Path) -> None:
    map_path = tmp_path / "filename-map.yaml"
    curated = {"edoc_id": "1", "filename": "1.pdf"}
    map_path.write_text(yaml.safe_dump({"documents": [curated]}), encoding="utf-8")

    update_filename_map([_record("aa")], map_path)
    update_filename_map([_record("aa")], map_path)

    documents = _documents(map_path)
    assert [d for d in documents if d.get("edoc_id") == "1"] == [curated]
    assert len([d for d in documents if d.get("source_url") == _URL]) == 1


# ---------------------------------------------------------------------------
# portal-served documents: naming and truncation
# ---------------------------------------------------------------------------


def test_portal_documents_are_named_by_docid() -> None:
    """Regression: every portal document would otherwise be called ``ViewDocument.aspx``.

    The portal addresses a document by query string, so ``urlparse(url).path`` is the same
    for all of them and carries no filename. Sending the 261-document ``2PE00000`` set
    through the old basename would have written one file and 260 ``conflict`` rows, each
    annotated "same name, different bytes" — a false collision report, since those are
    different documents that never shared a name to begin with.
    """
    assert (
        _basename("https://edocpub.epa.ohio.gov/publicportal/ViewDocument.aspx?docid=4192703", None)
        == "edoc-4192703.pdf"
    )
    # Matches the convention already committed for the hand-curated west-union tree.
    assert (
        _basename("https://edocpub.epa.ohio.gov/publicportal/viewdocument.aspx?DOCID=3940058", None)
        == "edoc-3940058.pdf"
    )


def test_dam_documents_keep_their_as_received_name() -> None:
    """The DAM route is unchanged — its URL basename is a real filename."""
    assert _basename(_URL, None) == "2PD00006.pdf"
    assert _basename(_URL, 'attachment; filename="2PD00006_mod.pdf"') == "2PD00006_mod.pdf"


def test_a_pdf_with_bytes_after_its_eof_marker_is_refused() -> None:
    """The marker must be LAST, not merely present near the end.

    A body cut mid-object after an incremental-update section still carries an earlier
    `%%EOF` well inside any trailing window, so a substring test passes it. All 261 documents
    of the Lima WWTP pull end with the marker under `rstrip()`, so the strict rule costs
    nothing on real agency PDFs.
    """
    assert not _pdf_is_complete(b"%PDF-1.7\n" + b"x" * 100 + b"\n%%EOF\n" + b"truncated tail")
    # Trailing whitespace is normal and must still pass.
    assert _pdf_is_complete(b"%PDF-1.7\n" + b"x" * 100 + b"\n%%EOF\n\r\n  ")


def test_a_pdf_without_its_eof_marker_is_refused() -> None:
    """The portal has served a body truncated at exactly 2 MiB with an agreeing length.

    Neither a short read nor a Content-Length mismatch exposes that, so the terminating
    marker is the only signal — and committing a half-copied PDF into litigation evidence
    is worse than failing the fetch.
    """
    assert not _pdf_is_complete(b"%PDF-1.7\n" + b"x" * 4096)


def test_a_complete_pdf_passes() -> None:
    assert _pdf_is_complete(b"%PDF-1.7\n" + b"x" * 4096 + b"\n%%EOF\n")


def test_a_non_pdf_response_is_not_judged_by_the_eof_rule() -> None:
    """An HTML error page is a different failure, handled elsewhere — don't mislabel it."""
    assert _pdf_is_complete(b"<html><body>Not found</body></html>")


def test_a_successful_retry_retires_the_failed_row(tmp_path: Path) -> None:
    """Regression: a transient 500 left a permanent row describing no document.

    A failed fetch has no hash, so it keys as ``(url, None)``. The retry that succeeds
    carries a digest and lands under a *different* key, so the failure was unreachable
    forever — the Lima WWTP pull 500'd on 22 of 261 documents, served every one on retry,
    and produced a manifest of 283 rows against 261 files, 22 of them with an empty
    ``filename``.
    """
    path = tmp_path / "filename-map.yaml"
    failed = FetchedPermit(
        filename="",
        permit_id="2PE00000",
        source_url=_URL,
        sha256=None,
        bytes=None,
        content_type=None,
        fetched_at=None,
        status="error",
        note="fetch failed: HTTPStatusError: Server error '500 Internal Server Error'",
    )
    update_filename_map([failed], path)
    assert [e["status"] for e in _documents(path)] == ["error"]

    update_filename_map([_record("aa" * 32)], path)
    rows = _documents(path)
    assert [e["status"] for e in rows] == ["downloaded"]
    assert rows[0]["filename"] == "2PD00006.pdf"


def test_a_success_retires_a_failure_recorded_later_in_the_same_batch(tmp_path: Path) -> None:
    """Regression: retirement must not depend on the order records arrive in.

    Retiring as each record is walked misses the batch that succeeds and THEN errors on the
    same URL — the failure is appended after the success has already run, so nothing retires
    it. The set of successful URLs is computed up front instead.
    """
    path = tmp_path / "filename-map.yaml"
    failed = FetchedPermit(
        filename="",
        permit_id="2PD00006",
        source_url=_URL,
        sha256=None,
        bytes=None,
        content_type=None,
        fetched_at=None,
        status="error",
    )
    update_filename_map([_record("aa" * 32), failed], path)
    rows = _documents(path)
    assert [e["status"] for e in rows] == ["downloaded"]
    assert all(e["filename"] for e in rows)


def test_retiring_a_failure_leaves_other_urls_untouched(tmp_path: Path) -> None:
    """The rebuild after a deletion must not disturb unrelated provenance."""
    path = tmp_path / "filename-map.yaml"
    other = "https://dam.assets.ohio.gov/image/upload/epa.ohio.gov/Portals/35/permits/doc/OTHER.pdf"
    update_filename_map(
        [
            _record("bb" * 32, filename="OTHER.pdf").model_copy(update={"source_url": other}),
            FetchedPermit(
                filename="",
                permit_id="2PD00006",
                source_url=_URL,
                sha256=None,
                bytes=None,
                content_type=None,
                fetched_at=None,
                status="error",
            ),
        ],
        path,
    )
    update_filename_map([_record("cc" * 32)], path)
    rows = _documents(path)
    assert len(rows) == 2
    assert {e["source_url"] for e in rows} == {other, _URL}
    assert all(e["status"] == "downloaded" for e in rows)


def test_two_successful_captures_of_one_url_still_coexist(tmp_path: Path) -> None:
    """The *VD/*WD case must survive the retirement rule — only *failures* are retired."""
    path = tmp_path / "filename-map.yaml"
    update_filename_map([_record("dd" * 32)], path)
    update_filename_map([_record("ee" * 32, filename="2PD00006.aabbccdd.pdf")], path)
    rows = _documents(path)
    assert len(rows) == 2
    assert {e["sha256"] for e in rows} == {"dd" * 32, "ee" * 32}


# ---------------------------------------------------------------------------
# refused bodies: nothing that is not a document reaches data/documents/** (#2091)
# ---------------------------------------------------------------------------


class _StubResponse:
    """The two fields ``fetch_one`` reads off a streamed response."""

    def __init__(self, content: bytes, headers: dict[str, str]) -> None:
        self._content = content
        self.headers = headers

    def read(self) -> bytes:
        return self._content


def _stub_request(content: bytes, headers: dict[str, str]) -> object:
    @contextmanager
    def _fake(
        method: str, url: str, settings: object, *, stream: bool = False
    ) -> Iterator[_StubResponse]:
        yield _StubResponse(content, headers)

    return _fake


_PORTAL_URL = "https://edocpub.epa.ohio.gov/publicportal/ViewDocument.aspx?docid=4116210"

# Verbatim response headers for ``docid=4116210``, re-verified live 2026-08-23. The portal
# does not 404 a docid it cannot serve: it returns 200 with an empty body typed text/html.
_EMPTY_200_HEADERS = {"content-type": "text/html", "content-length": "0"}


def test_an_empty_200_is_refused_and_never_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression (#2091): the portal's empty 200 was committed as a 0-byte PDF.

    ``b"".startswith(b"%PDF-")`` is ``False``, so an empty body took ``_pdf_is_complete``'s
    non-PDF carve-out, fell through to the write path, and landed on disk as
    ``edoc-4116210.pdf`` — zero bytes, hashed to the empty-string digest ``e3b0c442…``, with a
    manifest row reading ``downloaded``. Every other silent-200 portal failure produces a
    *wrong result* a reader can notice; this one produced a file that exists and is empty,
    which reads as a successful acquisition.
    """
    monkeypatch.setattr(
        "watermark.oepa.fetch._browser_request", _stub_request(b"", _EMPTY_200_HEADERS)
    )
    result = fetch_one(_PORTAL_URL, tmp_path, permit_id="2DP00130")

    assert result.status == "empty"
    assert result.sha256 is None, "an empty body must not be hashed into the manifest"
    assert result.bytes == 0
    assert result.filename == ""
    assert result.note and "ZERO-LENGTH" in result.note
    assert list(tmp_path.iterdir()) == [], "nothing may be written for a body that never arrived"


def test_an_empty_body_is_not_reported_as_truncated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``empty`` and ``truncated`` are different findings and must stay distinct.

    ``truncated`` means a document exists and we hold a prefix of it — re-fetch and compare.
    ``empty`` means nothing was served at all, which for the portal is a negative result about
    the docid. Collapsing them would send a reader chasing bytes that were never offered.
    """
    monkeypatch.setattr(
        "watermark.oepa.fetch._browser_request", _stub_request(b"", _EMPTY_200_HEADERS)
    )
    assert fetch_one(_PORTAL_URL, tmp_path).status != "truncated"


def test_an_html_body_is_refused_under_a_pdf_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An error page written as ``.pdf`` is the same defect class as a 0-byte one.

    The old carve-out assumed "callers already handle it"; ``fetch_one`` did not — it hashed
    the page, derived ``edoc-<docid>.pdf`` from the URL and recorded ``downloaded``.
    """
    body = b"<!DOCTYPE html>\n<html><head><title>Error</title></head><body>error</body></html>"
    monkeypatch.setattr(
        "watermark.oepa.fetch._browser_request",
        _stub_request(body, {"content-type": "text/html; charset=utf-8"}),
    )
    result = fetch_one(_PORTAL_URL, tmp_path, permit_id="2DP00130")

    assert result.status == "not_a_document"
    assert result.sha256 is None
    assert result.content_type == "text/html; charset=utf-8"
    assert list(tmp_path.iterdir()) == []


def test_an_html_body_with_no_content_type_is_still_refused() -> None:
    """A missing or mislabelled header must not be the thing that lets an error page in."""
    assert _refusal(b"<html><body>nope</body></html>", None) is not None
    assert _refusal(b"  \n<!doctype html>\n<html></html>", "application/pdf") is not None


def test_a_bom_prefixed_html_body_is_still_refused() -> None:
    """A UTF-8 BOM is invisible to ``bytes.lstrip()``, which strips ASCII whitespace only.

    ASP.NET emits one whenever the response encoding calls for it, so a BOM'd error page
    mislabelled ``application/pdf`` would otherwise sniff clean and be written under a
    ``.pdf`` name — the same defect the content-type rule exists to stop.
    """
    assert _refusal(b"\xef\xbb\xbf<html><body>nope</body></html>", "application/pdf") is not None
    assert _refusal(b"\xef\xbb\xbf\r\n<!DOCTYPE html>\n<html></html>", None) is not None
    # The BOM alone is not markup, and a BOM'd non-HTML body is not this rule's business.
    assert _refusal(b"\xef\xbb\xbfpermit id,county\n1PD00011,ALLEN\n", "text/csv") is None


def test_a_real_pdf_under_a_wrong_content_type_is_still_committed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bytes decide what a document is, not the header.

    The magic + ``%%EOF`` check runs BEFORE the content-type rule, so a server that mislabels
    a genuine PDF as ``text/html`` does not cost us the document.
    """
    body = b"%PDF-1.7\n" + b"x" * 512 + b"\n%%EOF\n"
    monkeypatch.setattr(
        "watermark.oepa.fetch._browser_request",
        _stub_request(body, {"content-type": "text/html"}),
    )
    result = fetch_one(_PORTAL_URL, tmp_path, permit_id="2DP00130")

    assert result.status == "downloaded"
    assert result.filename == "edoc-4116210.pdf"
    assert (tmp_path / "edoc-4116210.pdf").read_bytes() == body


def test_a_refused_fetch_logs_at_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Per the #1994 lesson: two errors buried in seventy-eight debug lines read as zero.

    A bulk fetch reports per-document outcomes only in the manifest, which is read after the
    fact; the run itself has to say something a human notices while it is happening.
    """
    monkeypatch.setattr(
        "watermark.oepa.fetch._browser_request", _stub_request(b"", _EMPTY_200_HEADERS)
    )
    with structlog.testing.capture_logs() as logs:
        fetch_one(_PORTAL_URL, tmp_path)

    events = [e for e in logs if e.get("event") == "oepa.fetch.empty"]
    assert len(events) == 1, f"expected one oepa.fetch.empty event, got {logs}"
    assert events[0]["log_level"] == "warning"
    assert events[0]["bytes"] == 0
    assert events[0]["content_type"] == "text/html"


def test_refusal_passes_a_complete_pdf() -> None:
    assert _refusal(b"%PDF-1.7\n" + b"x" * 64 + b"\n%%EOF\n", "application/pdf") is None


def test_a_refused_row_is_retired_by_a_later_success(tmp_path: Path) -> None:
    """A refusal has no hash, so it must follow the same retirement rule as an error row.

    Otherwise the docid a gap-probing workflow eventually resolves leaves a permanent
    ``empty`` row behind, describing a document the corpus does hold.
    """
    path = tmp_path / "filename-map.yaml"
    refused = FetchedPermit(
        filename="",
        permit_id="2PD00006",
        source_url=_URL,
        sha256=None,
        bytes=0,
        content_type="text/html",
        fetched_at=None,
        status="empty",
        note="refused: the server answered 200 with a ZERO-LENGTH body",
    )
    update_filename_map([refused], path)
    assert [e["status"] for e in _documents(path)] == ["empty"]

    update_filename_map([_record("ff" * 32)], path)
    rows = _documents(path)
    assert [e["status"] for e in rows] == ["downloaded"]
    assert rows[0]["filename"] == "2PD00006.pdf"
