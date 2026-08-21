"""Tests for the published ``catalog`` feed (epic #631 Phase 3 / #659)."""

from __future__ import annotations

import textwrap
from pathlib import Path

from watermark.catalog.reconcile import reconcile, write_observed
from watermark.config import Settings
from watermark.site.catalog import _collection, export_catalog
from watermark.site.feeds import CatalogItem


def _settings(tmp_path: Path) -> Settings:
    (tmp_path / "data").mkdir()
    return Settings(data_dir=tmp_path / "data")


def _entry(settings: Settings, name: str, scope: str, body: str) -> None:
    path = settings.catalog_dir / scope / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body), encoding="utf-8")


# --- collection derivation -----------------------------------------------------------------
def test_collection_drops_site_template(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _entry(
        settings,
        "eia-consumer-energy",
        "reference",
        """\
        id: eia-consumer-energy
        title: T
        scope: reference
        site_scope: slug-scoped
        producer:
          kind: connector
          source: x
        refresh:
          cadence: static
        storage:
        - relpath: reference/eia/{site}/consumer-energy.yaml
          media_type: application/x-yaml
        """,
    )
    items = {i.id: i for i in export_catalog(settings)}
    assert items["eia-consumer-energy"].collection == "eia"  # {site} dropped


def test_collection_falls_back_to_scope_when_flat(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _entry(
        settings,
        "data-centers",
        "extracted",
        """\
        id: data-centers
        title: T
        scope: extracted
        site_scope: slug-scoped
        producer:
          kind: extracted
          source: x
        refresh:
          cadence: static
        storage:
        - relpath: extracted/{site}/data-centers.md
          media_type: text/markdown
        """,
    )
    assert {i.id: i for i in export_catalog(settings)}["data-centers"].collection == "extracted"


# --- projection + provenance ---------------------------------------------------------------
def test_projection_carries_facts_and_citation(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _entry(
        settings,
        "echo-x",
        "reference",
        """\
        id: echo-x
        title: Echo inventory
        scope: reference
        status: reviewed
        license: U.S. Government work
        access_tier: throttled
        producer:
          kind: connector
          command: npdes --basin maumee
          source: EPA ECHO
        refresh:
          cadence: quarterly
          ttl_days: 180
        storage:
        - relpath: reference/echo/x.yaml
          media_type: application/x-yaml
        """,
    )
    item = {i.id: i for i in export_catalog(settings)}["echo-x"]
    assert isinstance(item, CatalogItem)
    assert item.license == "U.S. Government work"
    assert item.access_tier == "throttled"
    assert item.cadence == "quarterly" and item.ttl_days == 180
    # the producer becomes the bundle's shared Citation shape
    assert item.citation.source == "EPA ECHO"
    assert item.citation.source_kind == "connector"
    assert item.citation.verified is True  # connector-sourced
    assert item.citation.note == "watermark npdes --basin maumee"
    # no _observed.yaml committed in this tmp catalog -> observed is None
    assert item.observed is None


def test_observed_snapshot_is_joined_when_present() -> None:
    """Against the real committed catalog, the reconcile snapshot is attached."""
    items = {i.id: i for i in export_catalog(Settings())}
    echo = items["echo-maumee-npdes"]
    assert echo.observed is not None
    assert echo.observed.exists is True
    assert echo.observed.file_count >= 1


# --- the per-site observation (#2066) -------------------------------------------------------
_PER_SITE_ENTRY = """\
    id: parcel-assemblage
    title: T
    scope: reference
    site_scope: slug-scoped
    producer:
      kind: connector
      source: x
    refresh:
      cadence: on-demand
    storage:
    - relpath: reference/{site}/parcel-assemblage.geojson
      media_type: application/geo+json
"""


def _per_site_tree(tmp_path: Path) -> Settings:
    """A slug-scoped dataset two sites hold and the reference build does not."""
    settings = _settings(tmp_path)
    _entry(settings, "parcel-assemblage", "reference", _PER_SITE_ENTRY)
    for slug, body in (("mansfield", '{"a": 1}\n'), ("fort-wayne", '{"bb": 22}\n')):
        path = settings.data_dir / "reference" / slug / "parcel-assemblage.geojson"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    write_observed(reconcile(settings=settings), settings=settings)
    return settings


def _row(settings: Settings, slug: str) -> CatalogItem:
    scoped = settings.model_copy(update={"site": slug})
    return {i.id: i for i in export_catalog(scoped)}["parcel-assemblage"]


def test_each_site_publishes_its_own_observation(tmp_path: Path) -> None:
    """A site's ``observed`` is its own file, never the network aggregate (#2066).

    Mansfield's committed bundle claimed 531,148 bytes and 11 files for a 29,769-byte file it
    holds alone; Fort Wayne, exported less recently, claimed a different aggregate again — so the
    two sites disagreed about the same dataset purely by export recency.
    """
    settings = _per_site_tree(tmp_path)
    mansfield = _row(settings, "mansfield").observed
    fort_wayne = _row(settings, "fort-wayne").observed
    assert mansfield is not None and fort_wayne is not None

    assert mansfield.file_count == 1 and fort_wayne.file_count == 1
    assert mansfield.size_bytes == len('{"a": 1}\n')
    assert fort_wayne.size_bytes == len('{"bb": 22}\n')
    assert mansfield.sha256 != fort_wayne.sha256


def test_a_site_without_the_file_publishes_exists_false(tmp_path: Path) -> None:
    """The sharpest form of the bug: ``exists: true`` for an artifact the site does not have."""
    settings = _per_site_tree(tmp_path)
    observed = _row(settings, "lima").observed
    assert observed is not None
    assert observed.exists is False
    assert observed.file_count == 0
    assert observed.size_bytes == 0
    assert observed.sha256 is None


def test_only_the_reference_build_carries_the_network_figure(tmp_path: Path) -> None:
    """``/about/catalog`` is network-global and reads the reference build; a sibling is its own."""
    settings = _per_site_tree(tmp_path)
    network = _row(settings, "lima").observed_network
    assert network is not None
    assert network.sites_present == 2
    assert network.sites_total > 2  # every registered site, not just the holders
    assert _row(settings, "mansfield").observed_network is None


def test_a_shared_dataset_keeps_one_record_for_every_site(tmp_path: Path) -> None:
    """Only slug-scoped datasets have a site axis — a shared one is the same fact everywhere."""
    settings = _settings(tmp_path)
    _entry(
        settings,
        "echo-x",
        "reference",
        """\
        id: echo-x
        title: T
        scope: reference
        site_scope: basin-shared
        producer:
          kind: connector
          source: x
        refresh:
          cadence: static
        storage:
        - relpath: reference/echo/x.yaml
          media_type: application/x-yaml
        """,
    )
    path = settings.data_dir / "reference" / "echo" / "x.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x: 1\n", encoding="utf-8")
    write_observed(reconcile(settings=settings), settings=settings)

    def row(slug: str) -> CatalogItem:
        scoped = settings.model_copy(update={"site": slug})
        return {i.id: i for i in export_catalog(scoped)}["echo-x"]

    lima, findlay = row("lima").observed, row("findlay").observed
    assert lima is not None and findlay is not None
    assert lima.exists is True and lima == findlay
    assert row("lima").observed_network is None


def test_every_entry_is_projected() -> None:
    from watermark.catalog import load_entries

    items = export_catalog(Settings())
    assert {i.id for i in items} == {e.id for e in load_entries()}


def test_collection_helper_direct() -> None:
    from watermark.catalog import CatalogEntry

    def e(relpath: str | None) -> CatalogEntry:
        storage = [{"relpath": relpath, "media_type": "application/x-yaml"}] if relpath else []
        return CatalogEntry.model_validate(
            {
                "id": "d",
                "title": "T",
                "scope": "reference",
                "producer": {"kind": "manual", "source": "x"},
                "refresh": {"cadence": "static"},
                "storage": storage,
            }
        )

    assert _collection(e("reference/echo/maumee-wwtp.all-npdes.yaml")) == "echo"
    assert _collection(e(None)) == "reference"  # no storage -> scope
