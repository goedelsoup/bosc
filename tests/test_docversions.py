"""Tests for the document version / duplicate-cluster projection (#1590).

`watermark.site.docversions` reads the curated custody manifest and stamps
`duplicate_cluster` / `canonical_document_id` / `version` / `supersedes` onto the matching
`DocumentItem`s so retrieval can collapse a filing's versions to canonical. The projection is
stale-safe (a member rel absent from the catalog is skipped; a <2-present-member cluster is
dropped) and a missing/malformed manifest is a no-op.
"""

from __future__ import annotations

from pathlib import Path

from watermark.site import docversions
from watermark.site.feeds import DocumentCollectionItem, DocumentItem


def _item(rel: str) -> DocumentItem:
    return DocumentItem(
        rel=rel,
        name=rel.rsplit("/", 1)[-1],
        size_bytes=1,
        suffix="pdf",
        media_type="application/pdf",
        render_class="pdf",
        published=True,
        available=True,
    )


def _collection(*rels: str) -> list[DocumentCollectionItem]:
    return [DocumentCollectionItem(slug="oepa", title="Ohio EPA", entries=[_item(r) for r in rels])]


_MANIFEST = """
clusters:
  - id: oepa:2PH00006
    canonical: oepa/permit.pdf
    source: filename convention + _base_permit(2PH00006)
    members:
      - rel: oepa/permit.pdf
        version: final
      - rel: oepa/draft.pdf
        version: draft
        evidence_note: draft carries the un-redacted rating
      - rel: oepa/fact-sheet.pdf
        version: fact_sheet
"""


def _by_rel(colls: list[DocumentCollectionItem]) -> dict[str, DocumentItem]:
    return {e.rel: e for c in colls for e in c.entries}


def test_projects_cluster_metadata_onto_members(tmp_path: Path) -> None:
    path = tmp_path / "document-versions.yaml"
    path.write_text(_MANIFEST, encoding="utf-8")
    colls = _collection("oepa/permit.pdf", "oepa/draft.pdf", "oepa/fact-sheet.pdf")

    docversions.apply_document_versions(colls, docversions.load_document_versions(path))

    items = _by_rel(colls)
    for e in items.values():
        assert e.duplicate_cluster == "oepa:2PH00006"
        assert e.canonical_document_id == "oepa/permit.pdf"
    assert items["oepa/permit.pdf"].version == "final"
    assert items["oepa/draft.pdf"].version == "draft"
    assert items["oepa/fact-sheet.pdf"].version == "fact_sheet"
    # `supersedes` is set on the canonical member only.
    assert set(items["oepa/permit.pdf"].supersedes) == {"oepa/draft.pdf", "oepa/fact-sheet.pdf"}
    assert items["oepa/draft.pdf"].supersedes == []


def test_absent_member_is_skipped_but_cluster_survives(tmp_path: Path) -> None:
    """A member rel not in the catalog is dropped; the rest of the cluster still projects."""
    path = tmp_path / "document-versions.yaml"
    path.write_text(_MANIFEST, encoding="utf-8")
    # fact-sheet.pdf is not catalogued (e.g. filtered out of scope / removed).
    colls = _collection("oepa/permit.pdf", "oepa/draft.pdf")

    docversions.apply_document_versions(colls, docversions.load_document_versions(path))

    items = _by_rel(colls)
    assert items["oepa/permit.pdf"].duplicate_cluster == "oepa:2PH00006"
    # The dropped member never appears, so it can't be in supersedes.
    assert items["oepa/permit.pdf"].supersedes == ["oepa/draft.pdf"]


def test_thin_cluster_is_dropped(tmp_path: Path) -> None:
    """A cluster left with a single present member has nothing to collapse — no metadata stamped."""
    path = tmp_path / "document-versions.yaml"
    path.write_text(_MANIFEST, encoding="utf-8")
    colls = _collection("oepa/permit.pdf")  # only the canonical present

    docversions.apply_document_versions(colls, docversions.load_document_versions(path))

    assert _by_rel(colls)["oepa/permit.pdf"].duplicate_cluster is None


def test_canonical_absent_promotes_first_present_member(tmp_path: Path) -> None:
    """When the declared canonical isn't catalogued, the first present member becomes canonical."""
    path = tmp_path / "document-versions.yaml"
    path.write_text(_MANIFEST, encoding="utf-8")
    colls = _collection("oepa/draft.pdf", "oepa/fact-sheet.pdf")  # no permit.pdf

    docversions.apply_document_versions(colls, docversions.load_document_versions(path))

    items = _by_rel(colls)
    assert items["oepa/draft.pdf"].canonical_document_id == "oepa/draft.pdf"
    assert set(items["oepa/draft.pdf"].supersedes) == {"oepa/fact-sheet.pdf"}


def test_missing_manifest_is_a_noop(tmp_path: Path) -> None:
    colls = _collection("oepa/permit.pdf", "oepa/draft.pdf")
    versions = docversions.load_document_versions(tmp_path / "does-not-exist.yaml")
    assert not versions
    docversions.apply_document_versions(colls, versions)
    assert all(e.duplicate_cluster is None for e in _by_rel(colls).values())


def test_malformed_manifest_is_a_noop(tmp_path: Path) -> None:
    path = tmp_path / "document-versions.yaml"
    path.write_text("clusters:\n  - id: broken\n    members: not-a-list\n", encoding="utf-8")
    versions = docversions.load_document_versions(path)
    assert not versions  # the malformed cluster is skipped, leaving no clusters


def test_canonical_must_be_a_member(tmp_path: Path) -> None:
    """A cluster whose canonical isn't among its members is rejected (never a dangling canonical)."""
    path = tmp_path / "document-versions.yaml"
    path.write_text(
        "clusters:\n"
        "  - id: oepa:x\n"
        "    canonical: oepa/not-listed.pdf\n"
        "    members:\n"
        "      - rel: oepa/a.pdf\n"
        "      - rel: oepa/b.pdf\n",
        encoding="utf-8",
    )
    assert not docversions.load_document_versions(path)


def test_committed_lima_manifest_loads() -> None:
    """The committed Lima manifest parses and declares every curated cluster (#1590, #1696)."""
    repo_root = Path(__file__).resolve().parents[1]
    versions = docversions.load_document_versions(
        repo_root / "data" / "site" / "document-versions.yaml"
    )
    ids = {c.id for c in versions.clusters}
    assert ids == {
        # OEPA permit triads (draft PN + fact sheet + issued permit).
        "oepa:2PH00006",
        "oepa:2PH00007",
        "oepa:2PK00002",
        # OHD000001 draft-only lifecycle (draft body + public notice + fact sheet).
        "oepa:OHD000001",
        # Cross-site permit + fact-sheet pairs.
        "oepa:2PD00006",
        "oepa:1PD00013",
        # Byte-identical commissioners meeting-record pairs.
        "commissioners:M031126-Special",
        "commissioners:M031926",
        "commissioners:M090825-Special-Session",
        # Byte-identical LACRPC agenda/minutes-endpoint pairs.
        "lacrpc:_01132026-261",
        "lacrpc:_01272026-262",
        "lacrpc:_02102026-266",
        # The 2026-08-22 Lima WWTP portal pull (#2075 follow-on). Two byte-identical situations, and
        # neither is a corpus defect — the portal addresses a document by docid, so one filing can
        # be reachable at several, and a DAM fetch can land the same bytes a second time under a
        # different name. `2PE00000-OD` is the 2023 issued permit, held once from the DAM (already
        # extracted) and once from the portal; the flow-diagram cluster is three docids inside one
        # 2022 application package serving a single page.
        "oepa:2PE00000-OD",
        "oepa:2PE00000-app256207483-flow-diagram",
        # Twin captures: ONE Ohio EPA letter served at TWO docids as two different scans. NOT
        # byte-identical (four distinct sha256s), so these are `v2` content twins rather than
        # `duplicate`s — both stay readable evidence. Declared because two independent extractions
        # of one letter disagreed, which is precisely what a cluster exists to surface.
        "oepa:2PE00000-prov-2016-07-11",
        "oepa:2PE00000-rov-2016-08-01",
    }
    by_id = {c.id: c for c in versions.clusters}
    # The 2026-08-22 Lima pull's two KINDS of multiplicity are distinguished by `version`, and the
    # distinction is load-bearing: `duplicate` means byte-identical (search_passages collapses those
    # outright), while `v2` means the same filing captured twice with genuinely differing bytes —
    # two scans of one letter, both readable. Asserting only the ids would let a later edit flip one
    # into the other and silently change what retrieval collapses.
    for cid in ("oepa:2PE00000-OD", "oepa:2PE00000-app256207483-flow-diagram"):
        assert {m.version for m in by_id[cid].members} == {"duplicate"}, cid
    for cid in ("oepa:2PE00000-prov-2016-07-11", "oepa:2PE00000-rov-2016-08-01"):
        assert {m.version for m in by_id[cid].members} == {"v2"}, cid
    # The already-extracted DAM copy is the canonical of the 2023 permit pair, so the portal capture
    # never becomes the cite target for a permit that was read from the other copy.
    assert by_id["oepa:2PE00000-OD"].canonical == "oepa/2PE00000.pdf"
    # The text-layer capture is canonical for each twin pair — never the image-only/poorer scan.
    assert by_id["oepa:2PE00000-prov-2016-07-11"].canonical == "oepa/lima/edoc-1914761.pdf"
    # Every cluster's canonical is one of its own members (never a dangling ref).
    for c in versions.clusters:
        assert any(m.rel == c.canonical for m in c.members)
    # The classic OEPA triads keep the issued permit as canonical.
    for pid in ("oepa:2PH00006", "oepa:2PH00007", "oepa:2PK00002"):
        c = by_id[pid]
        assert c.canonical.endswith("-permit.pdf")
        assert len(c.members) == 3
    # The byte-identical meeting pairs label BOTH members `duplicate` (passages-collapsible).
    for did in (
        "commissioners:M031126-Special",
        "commissioners:M031926",
        "commissioners:M090825-Special-Session",
        "lacrpc:_01132026-261",
        "lacrpc:_01272026-262",
        "lacrpc:_02102026-266",
    ):
        c = by_id[did]
        assert len(c.members) == 2
        assert {m.version for m in c.members} == {"duplicate"}
