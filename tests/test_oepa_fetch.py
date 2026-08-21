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

from pathlib import Path

import yaml

from watermark.oepa.fetch import FetchedPermit, update_filename_map

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
