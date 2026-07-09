"""Tests for ``watermark catalog backfill`` (epic #631, issue #624).

Two layers: hermetic synthetic-tree tests that pin the grouping rules (shared-stem filesets,
singleton dir-bundles, per-site templating + Lima fold, meta.source/LFS enrichment, the
idempotent + prose-preserving writer), and one regression guard that the *committed* catalog
stays in sync with the real data tree (a backfill dry-run produces no create/refresh).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from watermark.catalog import CatalogEntry, load_entries
from watermark.catalog.backfill import (
    backfill,
    discover_datasets,
)
from watermark.config import Settings


def _settings(tmp_path: Path) -> Settings:
    """A Settings rooted at a synthetic data tree, with an LFS rule like the real repo."""
    (tmp_path / ".gitattributes").write_text(
        "data/reference/**/*.pdf filter=lfs diff=lfs merge=lfs -text\n", encoding="utf-8"
    )
    data = tmp_path / "data"
    data.mkdir()
    return Settings(data_dir=data)


def _write(settings: Settings, relpath: str, body: str = "x: 1\n") -> None:
    path = settings.data_dir / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


# --- grouping ------------------------------------------------------------------------------
def test_shared_stem_files_form_one_dataset(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    for variant in ("all-npdes", "potw", "huc-counts"):
        _write(settings, f"reference/echo/maumee-wwtp.{variant}.yaml")
    datasets = {d.id: d for d in discover_datasets("reference", settings=settings)}
    assert "echo-maumee-wwtp" in datasets
    assert len(datasets["echo-maumee-wwtp"].storage) == 3
    assert datasets["echo-maumee-wwtp"].site_scope == "basin-shared"


def test_singleton_files_collapse_into_a_dir_bundle(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    for name in ("summary-2020", "summary-2022", "precincts"):
        _write(settings, f"reference/allen-boe/source-pdf/{name}.pdf")
    datasets = {d.id: d for d in discover_datasets("reference", settings=settings)}
    # three uniquely-named files -> one bundle, not three entries
    assert "allen-boe-source-pdf" in datasets
    assert len(datasets["allen-boe-source-pdf"].storage) == 3


def test_per_site_files_collapse_to_template_with_lima_fold(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write(settings, "reference/eia/bryan/consumer-energy.yaml")
    _write(settings, "reference/eia/columbus/consumer-energy.yaml")
    _write(settings, "reference/eia/consumer-energy.yaml")  # Lima's un-slugged peer
    datasets = {d.id: d for d in discover_datasets("reference", settings=settings)}
    ds = datasets["eia-consumer-energy"]
    assert ds.site_scope == "slug-scoped"
    relpaths = {s.relpath for s in ds.storage}
    # the 18-way per-site fan-in dedups to one {site} template; the Lima peer folds in
    assert relpaths == {
        "reference/eia/{site}/consumer-energy.yaml",
        "reference/eia/consumer-energy.yaml",
    }


def test_bosc_prefixed_files_are_lima_legacy(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    # a 2-file shared-stem fileset keeps its stem id (a lone file would collapse to the dir name)
    _write(settings, "reference/hydrology/bosc-stormwater-discharge.yaml")
    _write(settings, "reference/hydrology/bosc-stormwater-discharge.meta.yaml")
    datasets = {d.id: d for d in discover_datasets("reference", settings=settings)}
    assert datasets["hydrology-bosc-stormwater-discharge"].site_scope == "lima-legacy"


def test_meta_source_and_lfs_enrichment(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    # lone files collapse to a dir-named bundle (id == the collection dir)
    _write(
        settings,
        "reference/rsei/inventory.yaml",
        "meta:\n  source: EPA RSEI Public Data Set\nrows: []\n",
    )
    _write(settings, "reference/hydrology/atlas.pdf", "%PDF-1.4\n")
    datasets = {d.id: d for d in discover_datasets("reference", settings=settings)}
    assert datasets["rsei"].source == "EPA RSEI Public Data Set"
    assert datasets["rsei"].producer_kind == "connector"  # from the hint map
    assert datasets["hydrology"].storage[0].lfs is True  # reference PDF -> LFS


def test_readme_and_scripts_are_skipped(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write(settings, "reference/x/README.md", "# docs\n")
    _write(settings, "reference/x/parse.py", "print(1)\n")
    _write(settings, "reference/x/data.yaml")
    datasets = {d.id: d for d in discover_datasets("reference", settings=settings)}
    assert "x" in datasets
    assert len(datasets["x"].storage) == 1  # only data.yaml


# --- writer: create / idempotent / reviewed / refresh --------------------------------------
def test_backfill_creates_then_is_idempotent(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write(settings, "reference/echo/maumee-wwtp.potw.yaml")
    _write(settings, "reference/echo/maumee-wwtp.all-npdes.yaml")
    first = backfill(scopes=("reference",), apply=True, settings=settings)
    assert [a.action for a in first] == ["create"]
    # the written stub loads + validates
    entries = load_entries(settings=settings)
    assert [e.id for e in entries] == ["echo-maumee-wwtp"]
    # a second run sees no change
    second = backfill(scopes=("reference",), apply=True, settings=settings)
    assert [a.action for a in second] == ["skip-unchanged"]


def test_backfill_skips_a_reviewed_entry_by_storage_overlap(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write(settings, "reference/echo/maumee-wwtp.potw.yaml")
    # a hand-renamed reviewed entry covering that file
    cat = settings.catalog_dir / "reference"
    cat.mkdir(parents=True)
    (cat / "echo-maumee-npdes.yaml").write_text(
        textwrap.dedent(
            """\
            id: echo-maumee-npdes
            title: Curated
            scope: reference
            status: reviewed
            producer:
              kind: connector
              source: EPA ECHO
            storage:
            - relpath: reference/echo/maumee-wwtp.potw.yaml
              media_type: application/x-yaml
            refresh:
              cadence: quarterly
            """
        ),
        encoding="utf-8",
    )
    actions = backfill(scopes=("reference",), apply=True, settings=settings)
    assert [a.action for a in actions] == ["skip-reviewed"]
    # no duplicate stub written under the mechanical id
    assert not (cat / "echo-maumee-wwtp.yaml").exists()


def test_backfill_matches_slug_template_to_a_site_pinned_entry(tmp_path: Path) -> None:
    """A lone per-site file matches a reviewed entry that pins it literally (#778/#1326).

    When a second site promotes a shared stem to a real ``≥2`` fileset (here a second
    ``parcel-assemblage``), the singleton ``{site}`` bundle splits and a sibling lone per-site
    file (Wilmington's ``watch-items``) surfaces as its own slug-scoped dataset. Its ``{site}``
    template must still match the reviewer's ``site:<slug>`` entry that pins the literal path —
    otherwise backfill re-proposes a duplicate generic stub and the in-sync gate turns red.
    """
    settings = _settings(tmp_path)
    _write(settings, "reference/fort-wayne/parcel-assemblage.geojson")
    _write(settings, "reference/urbana/parcel-assemblage.geojson")
    _write(settings, "reference/wilmington/watch-items.geojson")
    cat = settings.catalog_dir / "reference"
    cat.mkdir(parents=True)
    (cat / "parcel-assemblage.yaml").write_text(
        textwrap.dedent(
            """\
            id: parcel-assemblage
            title: Per-Site Parcel Assemblage
            scope: reference
            status: reviewed
            producer:
              kind: connector
              source: County parcel GIS
            site_scope: slug-scoped
            storage:
            - relpath: reference/{site}/parcel-assemblage.geojson
              media_type: application/geo+json
            refresh:
              cadence: on-demand
            """
        ),
        encoding="utf-8",
    )
    (cat / "wilmington-watch-items.yaml").write_text(
        textwrap.dedent(
            """\
            id: wilmington-watch-items
            title: Wilmington watch-items
            scope: reference
            status: reviewed
            producer:
              kind: manual
              source: Ohio EPA fact sheet
            site_scope: site:wilmington
            storage:
            - relpath: reference/wilmington/watch-items.geojson
              media_type: application/geo+json
            refresh:
              cadence: static
            """
        ),
        encoding="utf-8",
    )
    actions = backfill(scopes=("reference",), apply=True, settings=settings)
    by_id = {a.id: a for a in actions}
    # the split-out watch-items dataset matches the site-pinned entry — no fresh generic stub
    assert by_id["watch-items"].action == "skip-reviewed"
    assert "wilmington-watch-items" in by_id["watch-items"].detail
    assert not (cat / "watch-items.yaml").exists()
    # and nothing anywhere is (re)created/refreshed
    assert not [a for a in actions if a.action in ("create", "refresh")]


def test_backfill_refreshes_needs_review_preserving_prose(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write(settings, "reference/echo/maumee-wwtp.potw.yaml")
    _write(settings, "reference/echo/maumee-wwtp.all-npdes.yaml")  # a new file to fold in
    cat = settings.catalog_dir / "reference"
    cat.mkdir(parents=True)
    (cat / "echo-maumee-wwtp.yaml").write_text(
        textwrap.dedent(
            """\
            id: echo-maumee-wwtp
            title: A reviewer's title
            scope: reference
            status: needs-review
            producer:
              kind: connector
              source: EPA ECHO
            license: Public domain
            access_tier: throttled
            storage:
            - relpath: reference/echo/maumee-wwtp.potw.yaml
              media_type: application/x-yaml
            refresh:
              cadence: quarterly
            notes: A human wrote this prose.
            """
        ),
        encoding="utf-8",
    )
    actions = backfill(scopes=("reference",), apply=True, settings=settings)
    assert [a.action for a in actions] == ["refresh"]
    e = {x.id: x for x in load_entries(settings=settings)}["echo-maumee-wwtp"]
    # prose preserved
    assert e.title == "A reviewer's title"
    assert e.license == "Public domain"
    assert e.access_tier == "throttled"
    assert e.notes == "A human wrote this prose."
    # mechanical fields rewritten: the new file is now in storage
    assert len(e.storage) == 2


def test_only_filter_restricts_by_id_prefix(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write(settings, "reference/echo/maumee-wwtp.potw.yaml")
    _write(settings, "reference/echo/maumee-wwtp.all-npdes.yaml")
    _write(settings, "reference/rsei/inventory.yaml")
    actions = backfill(scopes=("reference",), only="echo", apply=False, settings=settings)
    assert {a.id for a in actions} == {"echo-maumee-wwtp"}


def test_written_yaml_has_no_null_or_empty_keys(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write(settings, "reference/rsei/inventory.yaml")
    backfill(scopes=("reference",), apply=True, settings=settings)
    text = (settings.catalog_dir / "reference" / "rsei.yaml").read_text("utf-8")
    assert "null" not in text
    assert "ttl_days" not in text  # an unset optional is omitted, not null


# --- regression guard against the real committed catalog -----------------------------------
def test_committed_catalog_is_in_sync_with_data_tree() -> None:
    """The committed stubs cover the data tree: a dry-run backfill creates/refreshes nothing.

    This is the precursor to the #626 orphan gate — if a new reference/extracted dataset lands
    without a catalog entry (or an entry drifts from its files), this turns red.
    """
    actions = backfill(apply=False)
    drift = [a for a in actions if a.action in ("create", "refresh")]
    assert drift == [], (
        f"catalog drift — run `watermark catalog backfill --apply`: {[a.id for a in drift]}"
    )


def test_every_committed_entry_validates() -> None:
    """Belt-and-suspenders: every backfilled stub is a valid CatalogEntry."""
    entries = load_entries()
    assert len(entries) >= 60  # the bootstrapped reference + extracted stubs
    assert all(isinstance(e, CatalogEntry) for e in entries)
