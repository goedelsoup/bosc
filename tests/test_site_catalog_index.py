"""Tests for the hydrated ``catalog-index`` feed (epic #1090 / #1093).

The builder tests are pure (no corpus load) — they pin the handle grammar, the locked rough
edges (timeline ref-gating, meeting composite keying), and ``catalog_version`` stability. One
integration test exports a real Lima bundle and asserts every feed-backed atom resolves back
into its source feed (the "no dangling pointer" invariant — chain of custody).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from watermark.site.catalog_index import (
    CATALOG_KINDS,
    FEED_BACKED_KINDS,
    build_catalog_index,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

_CV = "2.1.0"


def _index(rows_by_feed: dict[str, list[dict[str, Any]]], site: str = "lima"):
    return build_catalog_index(rows_by_feed, site=site, contract_version=_CV)


# --- handle grammar + kind mapping ---------------------------------------------------------
def test_handle_grammar_and_key_reuse() -> None:
    index = _index(
        {
            "records": [{"rel": "recorder/x.deed.yaml", "title": "A deed"}],
            "entities": [{"key": "BISTROZZI LLC", "display": "Bistrozzi LLC"}],
            "people": [{"slug": "cynthia-leis", "name": "Cynthia Leis"}],
            "leads": [{"id": "ASWCD-03", "title": "Wetland determination"}],
            "contacts": [
                {"id": "allen-county-commissioners", "name": "Allen County Board of Commissioners"}
            ],
            "catalog": [{"id": "echo-maumee", "title": "ECHO inventory"}],
        }
    )
    by_handle = {a.handle: a for a in index.atoms}
    # `<kind>:<site>:<localId>`, localId is the feed's existing key verbatim.
    assert by_handle["record:lima:recorder/x.deed.yaml"].title == "A deed"
    assert by_handle["entity:lima:BISTROZZI LLC"].feed == "entities"
    assert by_handle["person:lima:cynthia-leis"].local_id == "cynthia-leis"
    assert by_handle["lead:lima:ASWCD-03"].kind == "lead"
    # A contact atom's title is the contact name (not a `title` field).
    assert (
        by_handle["contact:lima:allen-county-commissioners"].title
        == "Allen County Board of Commissioners"
    )
    assert by_handle["dataset:lima:echo-maumee"].feed == "catalog"
    assert index.site == "lima" and index.contract_version == _CV


def test_kind_sets_are_the_single_source_of_truth() -> None:
    # feed-backed + web-only, no overlap, closed set the resolver's guard reads.
    assert set(FEED_BACKED_KINDS).isdisjoint({"teardown", "doc", "chapter", "figure"})
    assert set(CATALOG_KINDS) == set(FEED_BACKED_KINDS) | {"teardown", "doc", "chapter", "figure"}


def test_catalog_kinds_match_the_shared_literal() -> None:
    """The kind partition must exactly cover the `CatalogKind` Literal (feeds.py) — the enum the
    generated schema carries and the frontend parity-tests against, so the two tiers can't drift."""
    from typing import get_args

    from watermark.site.feeds import CatalogKind

    assert set(CATALOG_KINDS) == set(get_args(CatalogKind))


def test_schema_kind_enum_is_the_closed_set() -> None:
    """The committed `catalog-index.schema.json` `kind` enum is the frontend's parity anchor."""
    schema = json.loads(
        (
            REPO_ROOT / "data" / "site" / "bundle" / "schemas" / "catalog-index.schema.json"
        ).read_text()
    )
    enum = schema["$defs"]["CatalogAtom"]["properties"]["kind"]["enum"]
    assert set(enum) == set(CATALOG_KINDS)


# --- locked rough edges --------------------------------------------------------------------
def test_timeline_atoms_require_a_ref() -> None:
    index = _index(
        {
            "timeline": [
                {"ref": "1A-C-3104", "title": "Grading plan"},  # grabbable
                {"ref": "", "title": "Undated note"},  # ref-less -> skipped
                {"title": "No ref field at all"},  # skipped
            ]
        }
    )
    handles = [a.handle for a in index.atoms]
    assert handles == ["timeline:lima:1A-C-3104"]


def test_meeting_uses_composite_key_and_drops_ambiguous_duplicates() -> None:
    index = _index(
        {
            "meetings": [
                {"slug": "lacrpc", "date": "2024-11-25"},
                {"slug": "lacrpc", "date": "2025-01-06"},
                {"slug": "american-township", "date": ""},  # undated -> bare slug
                {"slug": "american-township", "date": ""},  # ambiguous dup -> dropped (v1)
            ]
        }
    )
    handles = sorted(a.handle for a in index.atoms)
    assert handles == [
        "meeting:lima:american-township",
        "meeting:lima:lacrpc/2024-11-25",
        "meeting:lima:lacrpc/2025-01-06",
    ]
    # No minted ids — every local_id is a source key verbatim, and every handle is unique.
    assert all("#" not in a.local_id for a in index.atoms)
    assert len({a.handle for a in index.atoms}) == len(index.atoms)


def test_title_falls_back_to_local_id_when_blank() -> None:
    index = _index({"concepts": [{"slug": "7q10", "title": ""}]})
    assert index.atoms[0].title == "7q10"


# --- catalog_version stability -------------------------------------------------------------
def test_catalog_version_is_stable_and_content_addressed() -> None:
    rows = {"records": [{"rel": "a", "title": "A"}, {"rel": "b", "title": "B"}]}
    v1 = _index(rows).catalog_version
    # Reordering rows must not change the version (atoms are sorted; hash is over handles).
    v2 = _index({"records": list(reversed(rows["records"]))}).catalog_version
    assert v1 == v2
    # Titles don't participate in identity — only handles do.
    v3 = _index(
        {"records": [{"rel": "a", "title": "X"}, {"rel": "b", "title": "Y"}]}
    ).catalog_version
    assert v1 == v3
    # A new handle changes the version.
    v4 = _index({"records": [*rows["records"], {"rel": "c", "title": "C"}]}).catalog_version
    assert v4 != v1


def test_absent_and_empty_feeds_are_skipped() -> None:
    index = _index({"records": [], "people": None})  # type: ignore[dict-item]
    assert index.atoms == []
    assert (
        index.catalog_version
        == build_catalog_index({}, site="lima", contract_version=_CV).catalog_version
    )


# --- integration: every atom resolves into its source feed ---------------------------------
# `lima_bundle` is conftest's session-wide, cross-worker export (#1773) — this module reads one
# feed off it, so it must never pay for an export of its own.
def _load(bundle: Path, feed_name: str, media_type: str) -> list[dict[str, Any]]:
    path = (
        bundle
        / "feeds"
        / (f"{feed_name}.ndjson" if "ndjson" in media_type else f"{feed_name}.json")
    )
    text = path.read_text(encoding="utf-8")
    if "ndjson" in media_type:
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return json.loads(text)


def test_catalog_index_feed_emitted_and_every_atom_resolves(lima_bundle: Path) -> None:
    manifest = json.loads((lima_bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["contract_version"] == _CV
    ref = next(f for f in manifest["feeds"] if f["name"] == "catalog-index")
    assert ref["kind"] == "object"

    index = json.loads((lima_bundle / ref["path"]).read_text(encoding="utf-8"))
    atoms = index["atoms"]
    assert index["site"] == "lima"
    assert len(atoms) > 0
    # Handles are well-formed and unique.
    handles = [a["handle"] for a in atoms]
    assert len(handles) == len(set(handles))
    for a in atoms:
        assert a["handle"] == f"{a['kind']}:{a['site']}:{a['local_id']}"
        assert a["kind"] in FEED_BACKED_KINDS  # the Python tier only emits feed-backed kinds

    # The pointer resolves: each atom's (feed, local_id) matches a live row (chain of custody).
    media = {f["name"]: f["media_type"] for f in manifest["feeds"]}
    key_field = {
        "records": "rel",
        "timeline": "ref",
        "entities": "key",
        "people": "slug",
        "places": "slug",
        "exhibits": "slug",
        "concepts": "slug",
        "leads": "id",
        "contacts": "id",
        "catalog": "id",
    }
    cache: dict[str, set[str]] = {}
    for a in atoms:
        feed = a["feed"]
        if feed == "meetings":
            continue  # composite slug/{date} key, resolution covered by the builder unit tests
        if feed not in cache:
            rows = _load(lima_bundle, feed, media[feed])
            cache[feed] = {str(r.get(key_field[feed])) for r in rows}
        assert a["local_id"] in cache[feed], f"dangling atom {a['handle']}"
