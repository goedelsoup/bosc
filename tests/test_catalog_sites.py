"""Tests for the site-aware catalog views (epic #631, issue #628).

Pins relevance + per-site presence resolution (including Lima's dual convention: an un-slugged
reference peer vs a `lima/` extracted segment) and the readiness rollup that feeds the
onboarding/promotion gate.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from watermark.catalog.sites import is_relevant, owner_matches, readiness, site_view
from watermark.config import Settings


def test_owner_matches_explicit_owner_kinds() -> None:
    """The #778 owner grammar: ``site:``/``basin:``/``state:`` match the site's identity, and the
    legacy kinds keep their meaning. Fort Wayne is Maumee/Indiana; Urbana is Great-Miami/Ohio."""
    # site: only the named slug
    assert owner_matches("site:fort-wayne", "fort-wayne")
    assert not owner_matches("site:fort-wayne", "urbana")
    # basin: only sites in that basin
    assert owner_matches("basin:great-miami", "urbana")
    assert not owner_matches("basin:great-miami", "fort-wayne")
    # state: only sites in that state (profile.eia_state)
    assert owner_matches("state:OH", "urbana")
    assert not owner_matches("state:OH", "fort-wayne")  # Indiana
    # legacy kinds unchanged: shared/template everyone, lima-legacy only the reference build
    assert owner_matches("basin-shared", "urbana")
    assert owner_matches("slug-scoped", "urbana")
    assert owner_matches("lima-legacy", "lima")
    assert not owner_matches("lima-legacy", "urbana")
    # an unregistered site can't claim another owner's data
    assert not owner_matches("basin:great-miami", "no-such-site")


def _settings(tmp_path: Path) -> Settings:
    (tmp_path / "data").mkdir()
    return Settings(data_dir=tmp_path / "data")


def _data(settings: Settings, relpath: str) -> None:
    path = settings.data_dir / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x: 1\n", encoding="utf-8")


def _entry(settings: Settings, name: str, scope: str, site_scope: str, *relpaths: str) -> None:
    storage = "\n".join(f"- relpath: {r}\n  media_type: application/x-yaml" for r in relpaths)
    body = textwrap.dedent(
        f"""\
        id: {name}
        title: T
        scope: {scope}
        site_scope: {site_scope}
        producer:
          kind: connector
          source: x
        refresh:
          cadence: static
        storage:
        """
    ) + textwrap.indent(storage, "")
    path = settings.catalog_dir / scope / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body + "\n", encoding="utf-8")


# --- relevance -----------------------------------------------------------------------------
def test_relevance_by_site_scope() -> None:
    from watermark.catalog import CatalogEntry

    def e(site_scope: str) -> CatalogEntry:
        return CatalogEntry.model_validate(
            {
                "id": "d",
                "title": "T",
                "scope": "reference",
                "site_scope": site_scope,
                "producer": {"kind": "connector", "source": "x"},
                "refresh": {"cadence": "static"},
            }
        )

    assert is_relevant(e("basin-shared"), "findlay") is True
    assert is_relevant(e("slug-scoped"), "findlay") is True
    assert is_relevant(e("lima-legacy"), "findlay") is False
    assert is_relevant(e("lima-legacy"), "lima") is True


# --- per-site presence ---------------------------------------------------------------------
def test_slug_scoped_presence_is_per_site(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/eia/bryan/consumer-energy.yaml")  # bryan has it, findlay does not
    _data(settings, "reference/eia/consumer-energy.yaml")  # Lima's un-slugged peer
    _entry(
        settings,
        "eia-consumer-energy",
        "reference",
        "slug-scoped",
        "reference/eia/{site}/consumer-energy.yaml",
        "reference/eia/consumer-energy.yaml",
    )
    by_site = {
        s: {d.id: d for d in site_view(s, settings=settings)} for s in ("bryan", "findlay", "lima")
    }
    assert by_site["bryan"]["eia-consumer-energy"].present is True
    assert by_site["findlay"]["eia-consumer-energy"].present is False  # no findlay/ copy
    # Lima resolves to its un-slugged peer, which exists
    assert by_site["lima"]["eia-consumer-energy"].present is True
    assert by_site["lima"]["eia-consumer-energy"].resolved == ["reference/eia/consumer-energy.yaml"]


def test_lima_uses_slug_segment_when_no_unslugged_peer(tmp_path: Path) -> None:
    """In the extracted tree Lima is just another `<slug>/` — no un-slugged peer exists."""
    settings = _settings(tmp_path)
    _data(settings, "extracted/lima/data-centers.md")
    _entry(settings, "data-centers", "extracted", "slug-scoped", "extracted/{site}/data-centers.md")
    lima = {d.id: d for d in site_view("lima", settings=settings)}["data-centers"]
    assert lima.resolved == ["extracted/lima/data-centers.md"]
    assert lima.present is True
    findlay = {d.id: d for d in site_view("findlay", settings=settings)}["data-centers"]
    assert findlay.present is False


def test_basin_shared_is_global_presence(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/echo/maumee.yaml")
    _entry(settings, "echo-maumee", "reference", "basin-shared", "reference/echo/maumee.yaml")
    for slug in ("bryan", "findlay", "lima"):
        view = {d.id: d for d in site_view(slug, settings=settings)}
        assert view["echo-maumee"].present is True


def test_lima_legacy_only_relevant_to_lima(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/hydrology/bosc-stormwater.yaml")
    _entry(
        settings,
        "hydrology-bosc-stormwater",
        "reference",
        "lima-legacy",
        "reference/hydrology/bosc-stormwater.yaml",
    )
    assert "hydrology-bosc-stormwater" in {d.id for d in site_view("lima", settings=settings)}
    assert "hydrology-bosc-stormwater" not in {d.id for d in site_view("bryan", settings=settings)}


# --- readiness rollup ----------------------------------------------------------------------
def test_readiness_counts_present_and_missing(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/echo/shared.yaml")
    _data(settings, "reference/eia/bryan/x.yaml")
    _entry(settings, "echo-shared", "reference", "basin-shared", "reference/echo/shared.yaml")
    _entry(settings, "eia-x", "reference", "slug-scoped", "reference/eia/{site}/x.yaml")

    bryan = readiness("bryan", settings=settings)
    assert bryan.total == 2 and bryan.present == 2 and bryan.ready is True
    assert bryan.missing == []

    findlay = readiness("findlay", settings=settings)
    assert findlay.total == 2 and findlay.present == 1
    assert findlay.missing == ["eia-x"] and findlay.ready is False


def test_basin_shared_is_not_a_cross_basin_wildcard() -> None:
    """#1251: ``basin-shared`` means *the whole network* (a genuine national/statewide reference),
    NOT "every site regardless of basin" for a basin-specific dataset. A Maumee-basin dataset must
    carry ``basin:maumee`` (shared within its basin) and a Lima-campus dataset ``lima-legacy`` — so
    a Scioto/Great-Miami point does not inherit either. Pinned against a mixed-basin site set."""
    from watermark.catalog import CatalogEntry

    def e(site_scope: str) -> CatalogEntry:
        return CatalogEntry.model_validate(
            {
                "id": "d",
                "title": "T",
                "scope": "reference",
                "site_scope": site_scope,
                "producer": {"kind": "connector", "source": "x"},
                "refresh": {"cadence": "static"},
            }
        )

    maumee = ("lima", "findlay", "fort-wayne", "bryan")  # Fort Wayne is Maumee/Indiana
    cross_basin = ("columbus", "piketon", "xenia", "hamilton-middletown", "coshocton", "sandusky")
    # A Maumee dataset reaches every Maumee site (any state) and no cross-basin site.
    assert all(is_relevant(e("basin:maumee"), s) for s in maumee)
    assert not any(is_relevant(e("basin:maumee"), s) for s in cross_basin)
    # A Lima-campus dataset reaches only the reference build, not even its Maumee siblings.
    assert is_relevant(e("lima-legacy"), "lima")
    assert not any(is_relevant(e("lima-legacy"), s) for s in ("findlay", *cross_basin))
    # A genuine network reference stays shared with everyone.
    assert all(is_relevant(e("basin-shared"), s) for s in (*maumee, *cross_basin))


def test_named_maumee_datasets_do_not_leak_cross_basin() -> None:
    """#1251 regression against the *committed* catalog: the mis-tagged datasets the sweep found
    (and their campus siblings) must not appear in a Scioto/Great-Miami site's expected set."""
    from watermark.catalog import load_entries

    entries = {entry.id: entry for entry in load_entries()}
    basin_scoped = ("hydrology",)  # basin:maumee — the Maumee TMDL working set, basin-wide
    # Lima-only: campus artifacts + the Allen County registry (subdivisions is lima-legacy per #1250,
    # since Allen County OH rosters describe no other Maumee site's subdivisions).
    lima_only = ("hydrology-swmm", "hydrology-wbd", "hydrology-low-flow-7q10", "subdivisions")
    for eid in (*basin_scoped, *lima_only):
        entry = entries[eid]
        assert is_relevant(entry, "lima"), f"{eid} must stay on the reference build"
        for cross in ("columbus", "xenia", "coshocton"):
            assert not is_relevant(entry, cross), f"{eid} leaked into cross-basin {cross}"
    # basin-scoped datasets still reach Maumee siblings; Lima-only ones do not.
    assert all(is_relevant(entries[eid], "findlay") for eid in basin_scoped)
    assert not any(is_relevant(entries[eid], "findlay") for eid in lima_only)


# --- real catalog --------------------------------------------------------------------------
def test_real_catalog_readiness_runs() -> None:
    r = readiness("lima")
    assert r.total > 0
    assert 0 <= r.present <= r.total


def test_peer_civic_datasets_are_owned_by_findlay_not_lima() -> None:
    """The per-site ``site_scope:<slug>`` path, against the real catalog (#1839).

    Epic #1520 shipped the cross-site civic loader but no peer dataset ever exercised this
    mechanism, so nothing pinned it. Findlay's registry and its two ingested meeting trees are
    now real committed datasets, and the ownership has to cut both ways: they belong to Findlay,
    and — crucially — they must NOT be relevant to Lima, whose own civic datasets are
    ``lima-legacy``. A leak here is the catalog half of the #1504/#1505 isolation guarantee.
    """
    from watermark.catalog import load_entries

    entries = {e.id: e for e in load_entries()}
    peer = (
        "subdivisions-findlay",
        "allen-township-meetings",
        "hancock-county-commissioners-meetings",
    )
    for eid in peer:
        assert entries[eid].site_scope == "site:findlay", eid
        assert is_relevant(entries[eid], "findlay"), eid
        assert not is_relevant(entries[eid], "lima"), eid
        # Literal paths under the peer's own slug — not a {site} template, and never Lima's flat tree.
        for item in entries[eid].storage:
            assert "{site}" not in item.relpath, eid
            assert "/findlay/" in item.relpath, eid

    # And the reverse: Lima's registry + its township trees stay Lima's.
    for eid in ("subdivisions", "american-township-meetings", "lacrpc-meetings"):
        assert entries[eid].site_scope == "lima-legacy", eid
        assert not is_relevant(entries[eid], "findlay"), eid
