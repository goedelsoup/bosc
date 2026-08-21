"""Tests for ``watermark catalog reconcile`` (epic #631, issue #625).

The observed half of declared-vs-observed: stat + sha256 + LFS-materialization + freshness for
every entry, written to ``data/catalog/_observed.yaml``. Hermetic synthetic-tree tests pin the
observation rules (existence/missing, single-file vs aggregate sha, ``{site}`` fan-out, LFS
pointer, freshness), plus a regression guard that the committed snapshot stays in sync with the
committed catalog + data tree.
"""

from __future__ import annotations

import hashlib
import textwrap
from datetime import UTC, datetime
from pathlib import Path

from watermark.catalog.reconcile import (
    load_observed,
    reconcile,
    write_observed,
)
from watermark.config import Settings

_FIXED = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)


def _settings(tmp_path: Path) -> Settings:
    (tmp_path / "data").mkdir()
    return Settings(data_dir=tmp_path / "data")


def _data(settings: Settings, relpath: str, body: str = "x: 1\n") -> Path:
    path = settings.data_dir / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _entry(settings: Settings, name: str, body: str) -> None:
    path = settings.catalog_dir / "reference" / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body), encoding="utf-8")


_CONCRETE = """\
    id: {name}
    title: T
    scope: reference
    producer:
      kind: connector
      source: x
    storage:
    - relpath: {relpath}
      media_type: application/x-yaml
    refresh:
      cadence: {cadence}
"""


# --- existence + sha -----------------------------------------------------------------------
def test_present_file_is_observed_with_its_own_sha(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    f = _data(settings, "reference/echo/x.yaml", "hello: 1\n")
    _entry(
        settings,
        "echo-x",
        _CONCRETE.format(name="echo-x", relpath="reference/echo/x.yaml", cadence="static"),
    )
    snap = reconcile(settings=settings, now=_FIXED, reconciled_at="pin")
    obs = snap.entries["echo-x"]
    assert obs.exists is True
    assert obs.file_count == 1
    assert obs.missing == []
    # a single materialized file reports its own file-level sha (comparable to a pin)
    assert obs.sha256 == hashlib.sha256(f.read_bytes()).hexdigest()


def test_missing_file_is_flagged_and_sha_is_none(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _entry(
        settings,
        "echo-x",
        _CONCRETE.format(name="echo-x", relpath="reference/echo/gone.yaml", cadence="static"),
    )
    obs = reconcile(settings=settings, now=_FIXED).entries["echo-x"]
    assert obs.exists is False
    assert obs.missing == ["reference/echo/gone.yaml"]
    assert obs.sha256 is None


def test_multi_file_entry_gets_a_stable_aggregate_sha(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/echo/a.yaml", "a: 1\n")
    _data(settings, "reference/echo/b.yaml", "b: 2\n")
    _entry(
        settings,
        "echo-multi",
        """\
        id: echo-multi
        title: T
        scope: reference
        producer:
          kind: connector
          source: x
        storage:
        - relpath: reference/echo/a.yaml
          media_type: application/x-yaml
        - relpath: reference/echo/b.yaml
          media_type: application/x-yaml
        refresh:
          cadence: static
        """,
    )
    result = reconcile(settings=settings, now=_FIXED)
    assert "echo-multi" in result.entries, f"missing key; got: {list(result.entries)}"
    obs = result.entries["echo-multi"]
    assert obs.exists is True
    assert obs.file_count == 2
    assert obs.sha256 is not None and len(obs.sha256) == 64
    # stable across runs
    again = reconcile(settings=settings, now=_FIXED).entries["echo-multi"]
    assert again.sha256 == obs.sha256


# --- per-site {site} template --------------------------------------------------------------
def test_site_template_fans_out_to_existing_files(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/eia/bryan/consumer-energy.yaml")
    _data(settings, "reference/eia/columbus/consumer-energy.yaml")
    # not every registered site has the file — absence must not be a false miss
    _entry(
        settings,
        "eia-consumer-energy",
        """\
        id: eia-consumer-energy
        title: T
        scope: reference
        site_scope: slug-scoped
        producer:
          kind: connector
          source: x
        storage:
        - relpath: reference/eia/{site}/consumer-energy.yaml
          media_type: application/x-yaml
        refresh:
          cadence: static
        """,
    )
    obs = reconcile(settings=settings, now=_FIXED).entries["eia-consumer-energy"]
    assert obs.exists is True
    assert obs.file_count == 2
    assert obs.missing == []


# --- the per-site axis (#2066) --------------------------------------------------------------
_SLUG_SCOPED = """\
    id: eia-consumer-energy
    title: T
    scope: reference
    site_scope: slug-scoped
    producer:
      kind: connector
      source: x
    storage:
    - relpath: reference/eia/{site}/consumer-energy.yaml
      media_type: application/x-yaml
    refresh:
      cadence: static
"""


def test_slug_scoped_entry_is_observed_per_site(tmp_path: Path) -> None:
    """Each site's own record, keyed by slug — NOT the network aggregate (#2066).

    The aggregate is the whole bug: one record for a dataset that is a different file per site
    was published into every site's bundle, so a site asserted its siblings' bytes as its own.
    """
    settings = _settings(tmp_path)
    bryan = _data(settings, "reference/eia/bryan/consumer-energy.yaml", "bryan: 1\n")
    columbus = _data(settings, "reference/eia/columbus/consumer-energy.yaml", "columbus: 22\n")
    _entry(settings, "eia-consumer-energy", _SLUG_SCOPED)

    obs = reconcile(settings=settings, now=_FIXED).entries["eia-consumer-energy"]

    # the entry-level record stays the network aggregate — check/diff/audit read it
    assert obs.file_count == 2
    assert obs.size_bytes == bryan.stat().st_size + columbus.stat().st_size

    # ...and each site now carries its OWN file's hash and size, not that sum
    assert set(obs.sites) == {"bryan", "columbus"}
    assert obs.sites["bryan"].file_count == 1
    assert obs.sites["bryan"].size_bytes == bryan.stat().st_size
    assert obs.sites["bryan"].sha256 == hashlib.sha256(bryan.read_bytes()).hexdigest()
    assert obs.sites["columbus"].sha256 == hashlib.sha256(columbus.read_bytes()).hexdigest()
    assert obs.sites["bryan"].sha256 != obs.sites["columbus"].sha256


def test_a_site_with_no_copy_gets_no_record(tmp_path: Path) -> None:
    """Absence is recorded by omission — the renderer reads it as ``exists: false``.

    ``parcel-assemblage`` is the worked case: lima, new-albany and piketon hold no such file and
    published ``exists: true`` over 531,148 bytes belonging to eleven other sites.
    """
    settings = _settings(tmp_path)
    _data(settings, "reference/eia/bryan/consumer-energy.yaml")
    _entry(settings, "eia-consumer-energy", _SLUG_SCOPED)

    obs = reconcile(settings=settings, now=_FIXED).entries["eia-consumer-energy"]
    assert set(obs.sites) == {"bryan"}
    assert "lima" not in obs.sites
    assert "piketon" not in obs.sites


def test_one_absent_templated_member_does_not_hide_the_site(tmp_path: Path) -> None:
    """A second ``{site}`` member only some sites can have is not the others' gap (#2066).

    ``rsei-inventory`` declares ``{site}/enclave.yaml`` alongside ``{site}/inventory.yaml``, and
    only the one federal-enclave site has an enclave — an all-members rule read 21 sites that
    hold their own inventory as missing it.
    """
    settings = _settings(tmp_path)
    _data(settings, "reference/rsei/bryan/inventory.yaml")
    _data(settings, "reference/rsei/wpafb/inventory.yaml")
    _data(settings, "reference/rsei/wpafb/enclave.yaml")
    _entry(
        settings,
        "rsei-inventory",
        """\
        id: rsei-inventory
        title: T
        scope: reference
        site_scope: slug-scoped
        producer:
          kind: connector
          source: x
        storage:
        - relpath: reference/rsei/{site}/inventory.yaml
          media_type: application/x-yaml
        - relpath: reference/rsei/{site}/enclave.yaml
          media_type: application/x-yaml
        refresh:
          cadence: static
        """,
    )
    obs = reconcile(settings=settings, now=_FIXED).entries["rsei-inventory"]
    assert obs.sites["bryan"].exists is True
    assert obs.sites["bryan"].file_count == 1
    assert obs.sites["wpafb"].file_count == 2


def test_reference_build_keeps_its_un_slugged_peer_and_its_slugged_file(tmp_path: Path) -> None:
    """The reference build resolves peers UNION templated, not one or the other (#2066).

    ``hydrology-reaches`` gives Lima both an un-slugged ``reach-nav.yaml`` and a slugged
    ``reaches/lima.geojson``; an either/or rule silently dropped the second.
    """
    settings = _settings(tmp_path)
    _data(settings, "reference/hydrology/reach-nav.yaml")
    _data(settings, "reference/hydrology/reaches/lima.geojson", "{}\n")
    _data(settings, "reference/hydrology/reaches/sidney.geojson", "{}\n")
    _data(settings, "reference/hydrology/sidney/reaches.yaml")
    _entry(
        settings,
        "hydrology-reaches",
        """\
        id: hydrology-reaches
        title: T
        scope: reference
        site_scope: slug-scoped
        producer:
          kind: connector
          source: x
        storage:
        - relpath: reference/hydrology/reach-nav.yaml
          media_type: application/x-yaml
        - relpath: reference/hydrology/{site}/reaches.yaml
          media_type: application/x-yaml
        - relpath: reference/hydrology/reaches/{site}.geojson
          media_type: application/geo+json
        refresh:
          cadence: static
        """,
    )
    obs = reconcile(settings=settings, now=_FIXED).entries["hydrology-reaches"]
    assert obs.sites["lima"].file_count == 2  # the peer AND reaches/lima.geojson
    assert obs.sites["sidney"].file_count == 2  # its own two, never lima's peer
    assert obs.sites["sidney"].sha256 != obs.sites["lima"].sha256


def test_shared_and_virtual_entries_carry_no_site_axis(tmp_path: Path) -> None:
    """Only a slug-scoped entry WITH storage is observed per site."""
    settings = _settings(tmp_path)
    _data(settings, "reference/echo/shared.yaml")
    _entry(
        settings,
        "echo-shared",
        _CONCRETE.format(
            name="echo-shared", relpath="reference/echo/shared.yaml", cadence="static"
        ),
    )
    _entry(
        settings,
        "virtual-node",
        """\
        id: virtual-node
        title: T
        scope: reference
        site_scope: slug-scoped
        producer:
          kind: derived
          source: x
        storage: []
        refresh:
          cadence: static
        """,
    )
    entries = reconcile(settings=settings, now=_FIXED).entries
    assert entries["echo-shared"].sites == {}
    # a virtual node has nothing on disk — it is present for everyone, with no per-site record
    assert entries["virtual-node"].exists is True
    assert entries["virtual-node"].sites == {}


def test_per_site_records_survive_the_yaml_round_trip(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/eia/bryan/consumer-energy.yaml", "bryan: 1\n")
    _entry(settings, "eia-consumer-energy", _SLUG_SCOPED)

    snap = reconcile(settings=settings, now=_FIXED, reconciled_at="pin")
    write_observed(snap, settings=settings)
    reloaded = load_observed(settings=settings)
    assert reloaded is not None
    assert (
        reloaded.entries["eia-consumer-energy"].sites == snap.entries["eia-consumer-energy"].sites
    )
    # an entry with no site axis writes no empty `sites:` map to carry
    assert "sites:" in (settings.catalog_dir / "_observed.yaml").read_text(encoding="utf-8")


# --- LFS pointer ---------------------------------------------------------------------------
def test_lfs_pointer_is_present_but_unmaterialized(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    pointer = "version https://git-lfs.github.com/spec/v1\noid sha256:deadbeef\nsize 123\n"
    _data(settings, "reference/imagery/scene.tif", pointer)
    _entry(
        settings,
        "imagery-scene",
        _CONCRETE.format(
            name="imagery-scene", relpath="reference/imagery/scene.tif", cadence="static"
        ),
    )
    obs = reconcile(settings=settings, now=_FIXED).entries["imagery-scene"]
    assert obs.exists is True  # the pointer file is present on disk
    assert obs.lfs_materialized is False  # but the real bytes are not
    assert obs.sha256 is None  # so we don't hash the pointer text


# --- freshness -----------------------------------------------------------------------------
def test_stale_when_past_ttl(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/echo/x.yaml", "meta:\n  last_refreshed: '2020-01-01'\n")
    _entry(
        settings,
        "echo-x",
        """\
        id: echo-x
        title: T
        scope: reference
        producer:
          kind: connector
          source: x
        storage:
        - relpath: reference/echo/x.yaml
          media_type: application/x-yaml
        refresh:
          cadence: annual
          ttl_days: 30
        """,
    )
    obs = reconcile(settings=settings, now=_FIXED).entries["echo-x"]
    assert obs.asof == "2020-01-01"
    assert obs.stale is True


def test_not_stale_within_ttl_and_unknowable_without_date(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/echo/fresh.yaml", "meta:\n  asof: '2026-06-01'\n")
    _data(settings, "reference/echo/undated.yaml", "rows: []\n")
    for name, rel, ttl in [
        ("fresh", "reference/echo/fresh.yaml", "ttl_days: 365"),
        ("undated", "reference/echo/undated.yaml", "ttl_days: 1"),
    ]:
        _entry(
            settings,
            f"echo-{name}",
            f"""\
            id: echo-{name}
            title: T
            scope: reference
            producer:
              kind: connector
              source: x
            storage:
            - relpath: {rel}
              media_type: application/x-yaml
            refresh:
              cadence: annual
              {ttl}
            """,
        )
    snap = reconcile(settings=settings, now=_FIXED)
    assert snap.entries["echo-fresh"].stale is False  # within ttl
    assert snap.entries["echo-undated"].stale is False  # no asof/last_refreshed -> unknowable


# --- determinism + round-trip --------------------------------------------------------------
def test_snapshot_is_deterministic_and_round_trips(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/echo/b.yaml")
    _data(settings, "reference/echo/a.yaml")
    _entry(
        settings,
        "echo-b",
        _CONCRETE.format(name="echo-b", relpath="reference/echo/b.yaml", cadence="static"),
    )
    _entry(
        settings,
        "echo-a",
        _CONCRETE.format(name="echo-a", relpath="reference/echo/a.yaml", cadence="static"),
    )
    snap = reconcile(settings=settings, now=_FIXED, reconciled_at="pin")
    assert list(snap.entries) == ["echo-a", "echo-b"]  # sorted by id
    path = write_observed(snap, settings=settings)
    assert path.name == "_observed.yaml"
    loaded = load_observed(settings=settings)
    assert loaded is not None
    assert loaded.entries == snap.entries
    assert loaded.reconciled_at == "pin"


def test_load_observed_is_none_before_first_run(tmp_path: Path) -> None:
    assert load_observed(settings=_settings(tmp_path)) is None


# --- regression guard against the committed catalog ----------------------------------------
# sha256/size_bytes/lfs_materialized depend on whether the checkout *materialized* the Git-LFS
# bytes — CI does not pull LFS (data/documents is ~5.4GB), so for LFS-bearing entries a fresh
# reconcile sees pointers, not real bytes. The committed snapshot is authored from a full-LFS
# checkout; compare those entries on the materialization-independent fields only.
_LFS_SENSITIVE = {"sha256", "size_bytes", "lfs_materialized"}


def test_committed_observed_is_in_sync_with_catalog() -> None:
    """The committed _observed.yaml matches a fresh reconcile (content-stable, no mtime).

    Precursor to the #626 checksum-drift gate — if a catalogued file changed bytes or a new
    entry landed without re-reconciling, this turns red. ``reconciled_at`` is excluded (it is
    the one intentionally non-deterministic field), and LFS-materialization-sensitive fields
    are compared only for entries with no LFS storage (CI runs without LFS bytes).
    """
    from watermark.catalog import load_entries

    committed = load_observed()
    assert committed is not None, "run `watermark catalog reconcile`"
    fresh = reconcile(reconciled_at=committed.reconciled_at)
    assert set(fresh.entries) == set(committed.entries)
    lfs_ids = {e.id for e in load_entries() if any(s.lfs for s in e.storage)}
    for eid, c in committed.entries.items():
        f = fresh.entries[eid]
        if eid in lfs_ids:
            assert f.model_dump(exclude=_LFS_SENSITIVE) == c.model_dump(exclude=_LFS_SENSITIVE), eid
        else:
            assert f == c, eid
