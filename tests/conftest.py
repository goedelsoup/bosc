"""Shared test fixtures."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest
from filelock import FileLock

from watermark.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = REPO_ROOT / "data" / "extracted"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


# --- the collected suite, before sharding (#1772) --------------------------------------------
# CI splits the suite across six runners with pytest-split, which balances the shards on the
# committed ``.test_durations``. That manifest rots silently: a collected test with no recorded
# duration is charged the *average* of the recorded ones, so a file of expensive-but-unrecorded
# tests reads as cheap and its shard runs long — at #1772 the manifest was 53% stale and the
# slowest shard took 5.3x the fastest. ``test_split_durations.py`` gates that drift; this hook
# is how it sees the whole suite rather than its own shard.
#
# ``tryfirst`` is load-bearing: pytest-split's own ``pytest_collection_modifyitems`` is
# ``trylast`` and deselects every test outside the running group, so a later hook would only
# ever see one sixth of the suite. Running first captures the full collection under
# ``--splits/--group`` and under xdist alike (every worker collects everything, then filters).
# ``network``-marked tests are dropped here: ``addopts`` deselects them, so they never run and
# are never recorded — counting them would read as permanent staleness.
COLLECTED_NODE_IDS: pytest.StashKey[list[str] | None] = pytest.StashKey()


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Stash the full collection — but only when this run collected the whole suite.

    A targeted run (``pytest tests/test_foo.py``, a node id, ``--co`` on a directory) sets
    ``args_source`` to ``ARGS``; measuring coverage over that subset would fail the guard for
    any new file. Those runs stash ``None`` and the guard skips.
    """
    full_suite = getattr(config, "args_source", None) is pytest.Config.ArgsSource.TESTPATHS
    config.stash[COLLECTED_NODE_IDS] = (
        [item.nodeid for item in items if item.get_closest_marker("network") is None]
        if full_suite
        else None
    )


@pytest.fixture(scope="session")
def collected_node_ids(request: pytest.FixtureRequest) -> list[str] | None:
    """Every test id this run collected before sharding, or ``None`` if it wasn't a full run."""
    return request.config.stash.get(COLLECTED_NODE_IDS, None)


# --- shared bundle exports (#1773) ----------------------------------------------------------
# A full ``export_bundle()`` is the most expensive operation in the repo — ~14 s for Lima with
# ``skip_embeddings``, ~28 s without — and the suite used to pay for 26 of them: nine modules
# each exported their own Lima bundle just to read one feed, and four sites were exported twice.
# Worse, xdist's default ``--dist load`` hands individual tests to whichever worker is free, and
# each worker is a separate process with its own fixture cache, so a ``scope="module"`` export
# fixture was rebuilt once per worker that happened to receive one of that module's tests.
#
# The fixtures below export a site's bundle **once per session, shared across xdist workers** via
# the workers' common temp root plus a file lock (the pytest-xdist recipe for expensive
# session-scoped setup). The first worker to ask does the export; the rest block on the lock and
# then read the same directory. That is what makes the scatter harmless — it fixes the
# per-worker multiplication at the source, so the suite keeps ``--dist load``'s balancing
# instead of trading it away for ``--dist loadfile``. An exported bundle is a read-only artifact,
# so sharing one across tests (and processes) is safe.
#
# Embeddings are always skipped: no test asserts on the ``ask-embeddings`` /
# ``passage-embeddings`` vectors, both feeds are emitted either way (empty — see
# ``export_bundle``) so the feed and schema sets stay stable, and the encode pass is half the
# cost of a Lima export.

_BUNDLE_GENERATED_AT = "2026-01-01T00:00:00+00:00"


@dataclass(frozen=True)
class ExportedBundle:
    """A shared bundle export: where it landed, plus the ``BundleResult`` fields tests assert on.

    The summary travels through the on-disk sentinel rather than as a live ``BundleResult``
    because only one xdist worker actually runs the export — the others read what it wrote.
    """

    path: Path
    row_total: int
    feed_count: int
    mirror_nodes: int
    mirror_graph_issues: int
    mirror_reports_dir: str | None


@pytest.fixture(scope="session")
def _bundle_root(tmp_path_factory: pytest.TempPathFactory, worker_id: str) -> Path:
    """The directory shared bundles land in — common to every xdist worker in this run.

    Under xdist each worker's basetemp is ``<run>/popen-gwN``, so its parent is the run-wide
    root. Without xdist that parent is the *cross-run* pytest root, which would leak a stale
    bundle into the next run — hence the ``master`` branch takes a fresh dir instead.
    """
    if worker_id == "master":
        return tmp_path_factory.mktemp("bundles")
    root = tmp_path_factory.getbasetemp().parent / "bundles"
    root.mkdir(exist_ok=True)
    return root


@pytest.fixture(scope="session")
def exported_bundle(_bundle_root: Path) -> Callable[[str], ExportedBundle]:
    """Factory for a site's shared bundle export, built at most once per session."""
    from watermark.site.export import export_bundle

    def _for(slug: str = "lima") -> ExportedBundle:
        out = _bundle_root / slug
        sentinel = _bundle_root / f"{slug}.summary.json"
        with FileLock(str(_bundle_root / f"{slug}.lock"), timeout=900):
            if not sentinel.exists():
                # Clear any debris a crashed earlier attempt left, so a retry can't read a
                # half-written feed from the run before it.
                shutil.rmtree(out, ignore_errors=True)
                result = export_bundle(
                    Settings(data_dir=REPO_ROOT / "data", site=slug),
                    out_dir=out,
                    generated_at=_BUNDLE_GENERATED_AT,
                    skip_embeddings=True,
                )
                # Written last, and only on success, so a crashed export is re-run rather than
                # silently serving a half-written bundle to every other worker.
                sentinel.write_text(
                    json.dumps(
                        {
                            "row_total": result.row_total,
                            "feed_count": result.feed_count,
                            "mirror_nodes": result.mirror_nodes,
                            "mirror_graph_issues": result.mirror_graph_issues,
                            "mirror_reports_dir": (
                                None
                                if result.mirror_reports_dir is None
                                else str(result.mirror_reports_dir)
                            ),
                        }
                    ),
                    encoding="utf-8",
                )
        return ExportedBundle(path=out, **json.loads(sentinel.read_text(encoding="utf-8")))

    return _for


@pytest.fixture(scope="session")
def site_bundle(exported_bundle: Callable[[str], ExportedBundle]) -> Callable[[str], Path]:
    """Factory for the *path* of a site's shared bundle — what nearly every consumer wants."""

    def _for(slug: str = "lima") -> Path:
        return exported_bundle(slug).path

    return _for


@pytest.fixture(scope="session")
def lima_bundle(site_bundle: Callable[[str], Path]) -> Path:
    """The reference build's bundle — the one most bundle-reading modules assert against."""
    return site_bundle("lima")


@pytest.fixture
def summary_path() -> Path:
    """Path to the committed roundabouts summary extraction."""
    return EXTRACTED / "aedg" / "roundabouts.summary.opc.yaml"


@pytest.fixture
def hydro_settings() -> Settings:
    """Offline hydrology settings: real repo data dir, connector fixtures, no network.

    Injected into connector / pipeline calls so tests are hermetic without fighting
    ``get_settings()``'s ``lru_cache``.
    """
    return Settings(
        data_dir=REPO_ROOT / "data",
        hydro_offline=True,
        hydro_fixtures_dir=FIXTURES / "hydrology",
    )


@pytest.fixture
def hydro_settings_for() -> Callable[[str], Settings]:
    """Factory for offline per-site hydrology settings (the ``hydro_settings`` wiring + a slug).

    A factory rather than a params-parameterized fixture because the consuming tests are
    site-specific — e.g. the dewatering-discharge screen is Lima-scoped (`not_separable`) and
    degrades to ``None`` on a peer, so lima and fort-wayne can't share one parameterized body.
    """

    def _make(site: str) -> Settings:
        return Settings(
            data_dir=REPO_ROOT / "data",
            site=site,
            hydro_offline=True,
            hydro_fixtures_dir=FIXTURES / "hydrology",
        )

    return _make


@pytest.fixture
def econ_settings() -> Settings:
    """Offline economics settings: real repo data dir, connector fixtures, no network."""
    return Settings(
        data_dir=REPO_ROOT / "data",
        econ_offline=True,
        econ_fixtures_dir=FIXTURES / "economics",
    )


@pytest.fixture
def greenops_settings(tmp_path: Path) -> Settings:
    """Offline GreenOps settings: connector fixtures, no network, no key.

    Uses a tmp_path-backed data_dir so greenops_cache_dir is sandboxed — a stale on-disk
    cache entry from a previous live pull cannot shadow the committed fixture (offline
    cached_get returns a cache hit before consulting fixtures).
    """
    return Settings(
        data_dir=tmp_path,
        greenops_offline=True,
        greenops_fixtures_dir=FIXTURES / "greenops",
    )


@pytest.fixture
def gis_settings() -> Settings:
    """Offline GIS/imagery settings: real repo data dir, STAC fixtures, no network."""
    return Settings(
        data_dir=REPO_ROOT / "data",
        gis_offline=True,
        gis_fixtures_dir=FIXTURES / "gis",
    )


@pytest.fixture
def air_settings() -> Settings:
    """Offline air settings: AERMET/AERMAP connector fixtures, no network.

    The met/terrain station IDs are set explicitly (they are the #1180 SiteProfile seam,
    not yet a profile knob); ``nasa_power_lat/lon`` and ``hydro_utm_epsg`` auto-fill from
    the active (Lima) profile like the other connector fixtures.
    """
    return Settings(
        data_dir=REPO_ROOT / "data",
        air_offline=True,
        air_fixtures_dir=FIXTURES / "air",
        air_surface_station="725330-14827",  # Fort Wayne Intl (KFWA) — Lima representative
        air_upperair_station="USM00072426",  # Wilmington, OH (ILN) radiosonde
        air_met_year=2023,
    )


@pytest.fixture
def federal_settings(tmp_path: Path) -> Settings:
    """Offline federal-enclave settings for WPAFB: MIRTA/SDWIS/ECHO fixtures, no network (#1664).

    ``data_dir`` is a tmp_path shell that **symlinks** the committed ``extracted/`` and
    ``reference/`` trees — the same sandboxing idea as ``research_settings``, but the enclave
    assembly reads real committed data (its grounding record, its RSEI row), so those two subtrees
    are linked through rather than copied. The point of the shell is ``cache_dir``, which derives
    from ``data_dir``: it keeps a developer's live ``data/cache/federal/`` from shadowing the
    committed fixtures, so the register pulls are proven to replay from
    ``tests/fixtures/federal/`` alone rather than passing green off a warm local cache.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for sub in ("extracted", "reference", "documents", "site", "entities", "catalog"):
        src = REPO_ROOT / "data" / sub
        if src.is_dir():
            (data_dir / sub).symlink_to(src, target_is_directory=True)
    return Settings(
        site="wpafb",
        data_dir=data_dir,
        federal_offline=True,
        federal_fixtures_dir=FIXTURES / "federal",
        rsei_offline=True,
    )


@pytest.fixture
def civic_settings() -> Settings:
    """Offline civic settings: real repo data dir, civic page fixtures, no network."""
    return Settings(
        data_dir=REPO_ROOT / "data",
        civic_offline=True,
        civic_fixtures_dir=FIXTURES / "civic",
    )


@pytest.fixture
def poi_settings() -> Settings:
    """Settings for the committed POI store (data/entities/poi/) — no network, no connector."""
    return Settings(data_dir=REPO_ROOT / "data")


@pytest.fixture
def poi_offline_settings() -> Settings:
    """Offline POI resolve settings: geocoder + allen_gis (parcel) fixtures, no network."""
    return Settings(
        data_dir=REPO_ROOT / "data",
        poi_offline=True,
        poi_fixtures_dir=FIXTURES / "poi",
        hydro_offline=True,
        hydro_fixtures_dir=FIXTURES / "hydrology",
    )


@pytest.fixture
def research_settings(tmp_path: Path) -> Settings:
    """Offline research-connector settings: fixture-backed Serper/fetch, no network.

    Uses a tmp_path-backed data_dir so research_cache_dir is sandboxed — stale
    on-disk cache entries from previous live runs cannot leak into the test.
    """
    return Settings(
        data_dir=tmp_path,
        research_offline=True,
        research_fixtures_dir=FIXTURES / "research",
    )


@pytest.fixture
def facility_settings() -> Settings:
    """Settings for the facility compute-capacity derivation.

    Reads committed reference data only (data/reference/compute + the parcels
    geojson) — no network, no connector — so a plain real-data-dir Settings is
    hermetic. Offline flags set defensively in case the footprint method's parcels
    path ever grows a connector fallback.
    """
    return Settings(data_dir=REPO_ROOT / "data", hydro_offline=True)
