"""The shared registries the grid/economics stacks read, and the invariants that justify them.

H2/#1645 collapsed four hand-synced duplications into single sources — the per-state jurisdiction
facts (:mod:`watermark.states`), the serving-utility identity
(:mod:`watermark.grid._registry`), the load-factor citation
(:func:`watermark.facility.consumption.load_factor_cite`), and the per-site reference path
(:func:`watermark.sites.site_reference_path`). These are the oracles for that collapse.

Two of them are **byte oracles**: the citation prose and the resolved paths both land in committed
reference artifacts, so a refactor that "only" reorganizes code must reproduce them exactly or it
has silently rewritten ``data/reference/**``. Hermetic — no network, no data-dir writes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.facility.consumption import LOAD_FACTOR, load_factor_cite
from watermark.grid._registry import SERVING_UTILITIES, is_registered, utility_identity
from watermark.sites import SITES, site_reference_path
from watermark.states import STATE_NAME, state_name, state_puc

REPO_ROOT = Path(__file__).resolve().parents[1]

# The four `_LOAD_FACTOR_CITE` literals as they stand in the committed reference artifacts —
# `data/reference/eia/**/grid-profile.yaml`, `**/demand-pressure.yaml`, and
# `reference/federal/**/federal-energy.yaml`. Transcribed from those files, NOT imported from the
# modules under test: an oracle the code cannot move by moving with it.
_COMMITTED_LOAD_FACTOR_CITES = {
    # grid.policy + grid.utility
    "#91": "data-center capacity utilization ~0.9 (near-flat 24x7); assumption (cf. #91)",
    # grid.market
    "#91/#94/#95": (
        "data-center capacity utilization ~0.9 (near-flat 24x7); assumption (cf. #91/#94/#95)"
    ),
}
_COMMITTED_ENERGY_CITE = "data-center capacity utilization ~0.9 (near-flat 24x7 load); assumption"

# The per-site reference artifacts the grid writers own, as (profile field, subdir, filename).
_SITE_REFERENCE_WRITERS = (
    ("ferc_relpath", "ferc", "ferc-seam.yaml"),
    ("pjm_relpath", "pjm", "pjm-market.yaml"),
    ("federal_relpath", "federal", "federal-energy.yaml"),
    # The design-storm routing tables + artifact (#1806) — Lima pins its legacy un-slugged
    # paths; every peer resolves reference/hydrology/<slug>/<file>.
    ("hydrology_network_relpath", "hydrology", "network.yaml"),
    ("hydrology_reaches_relpath", "hydrology", "reaches.yaml"),
    ("reach_nav_relpath", "hydrology", "reach-nav.yaml"),
    ("routed_hydrograph_relpath", "hydrology", "routed-hydrograph.yaml"),
)


# --- watermark.states ---------------------------------------------------------------------


def test_every_registered_site_state_has_a_readable_name_and_regulator() -> None:
    """No registered site falls through to a bare two-letter code or a nameless regulator."""
    for slug, prof in SITES.items():
        assert prof.eia_state in STATE_NAME, (
            f"site {slug!r} is in state {prof.eia_state!r}, which has no entry in "
            "watermark.states.STATE_NAME — add it rather than letting the prose print the code"
        )
        puc = state_puc(prof.eia_state)
        assert puc.short and puc.full and puc.retail_clause, slug
        assert state_name(prof.eia_state) in puc.retail_clause, (
            f"{slug}: the retail clause should name the state in full, not its code"
        )


def test_unlisted_state_degrades_generically_and_never_borrows_a_neighbour() -> None:
    """A5/A1 discipline: an unregistered state gets a templated form, never Ohio's regulator."""
    puc = state_puc("ZZ")
    assert "ZZ" in puc.short and "ZZ" in puc.full and "ZZ" in puc.retail_clause
    for known in STATE_NAME.values():
        assert known not in puc.full, f"the unlisted-state fallback leaked {known!r}"
        assert known not in puc.retail_clause
    assert state_name("ZZ") == "ZZ"


# --- watermark.grid._registry -------------------------------------------------------------


def test_no_registered_site_shares_another_sites_utility_identity_by_accident() -> None:
    """Sites legitimately share a serving utility — but only via the same EIA-861 number.

    The A5/#1638 failure was an identity resolving to the *wrong* thing silently. Two sites may
    share Ohio Power (#14006); what must never happen is two different numbers resolving to the
    same registered operating company, which would mean a duplicated row rather than a shared one.
    """
    by_company: dict[str, set[int]] = {}
    for number, ident in SERVING_UTILITIES.items():
        by_company.setdefault(ident.operating_company, set()).add(number)
    dupes = {co: nums for co, nums in by_company.items() if len(nums) > 1}
    assert not dupes, f"one operating company registered under several utility numbers: {dupes}"


def test_unlisted_utility_asserts_no_filer_and_no_rto() -> None:
    """B2/#1639: the fallback must claim neither a FERC Form-1 filer nor PJM membership."""
    ident = utility_identity(999_999, "Some Rural Electric Co-op")
    assert not is_registered(999_999)
    assert ident.operating_company == "the serving utility"
    assert ident.holding_company == "Some Rural Electric Co-op"
    assert "not confirmed" in ident.ba_citation and "not confirmed" in ident.rto_citation
    assert "PJM" not in ident.ba_citation and "PJM" not in ident.rto_citation
    # Called without a name (the FERC seam's path), it still refuses to invent one.
    assert utility_identity(999_999).holding_company == "the serving utility"


# --- facility.consumption.load_factor_cite (byte oracle) -----------------------------------


@pytest.mark.parametrize(("refs", "expected"), sorted(_COMMITTED_LOAD_FACTOR_CITES.items()))
def test_load_factor_cite_reproduces_the_committed_prose(refs: str, expected: str) -> None:
    """H2/#1645: the shared formatter emits exactly what is already committed to disk.

    ``grid.policy`` / ``grid.utility`` / ``grid.market`` used to carry these as literals. Building
    them from :data:`LOAD_FACTOR` is only safe if the output is byte-identical — otherwise the
    "pure cleanup" quietly rewrites the citation on every committed grid profile.
    """
    assert load_factor_cite(refs=refs) == expected


def test_load_factor_cite_reproduces_the_committed_economics_prose() -> None:
    assert load_factor_cite(subject="load") == _COMMITTED_ENERGY_CITE


def test_load_factor_cite_tracks_the_number_it_describes() -> None:
    """The point of the collapse: the prose is derived from the value, not typed alongside it."""
    assert f"~{LOAD_FACTOR:g}" in load_factor_cite()
    # Every committed variant states the same figure — that is what four literals could not promise.
    for cite in (*_COMMITTED_LOAD_FACTOR_CITES.values(), _COMMITTED_ENERGY_CITE):
        assert f"~{LOAD_FACTOR:g}" in cite


# --- sites.site_reference_path (B1 multi-site collision oracle) -----------------------------


def test_per_site_reference_paths_never_collide_across_the_network() -> None:
    """B1/#1639 + H3/#1645: no two registered sites write the same grid reference artifact.

    ``ferc_relpath`` / ``pjm_relpath`` / ``federal_relpath`` are **not** in
    ``PER_SITE_OUTPUT_FIELDS``, so ``output_path_collisions`` does not cover them — and it checks
    the raw field, which is ``None`` for every non-Lima site, so it could not cover them anyway.
    This resolves the path the writer will actually use and asserts uniqueness, which is the
    property B1 established: a ``watermark --site <peer> ferc`` run must never clobber Lima's file.
    """
    data_dir = Path("/nonexistent-test-root")  # resolution only; nothing is read or written
    for field, subdir, filename in _SITE_REFERENCE_WRITERS:
        seen: dict[Path, str] = {}
        for slug, prof in SITES.items():
            path = site_reference_path(
                Settings(site=slug, data_dir=data_dir),
                getattr(prof, field),
                subdir=subdir,
                filename=filename,
            )
            assert path not in seen, (
                f"{field}: sites {seen[path]!r} and {slug!r} both write {path} — a non-Lima "
                "run would clobber the other site's committed artifact (B1/#1639)"
            )
            seen[path] = slug
        assert len(seen) == len(SITES)


def test_site_reference_path_slug_scopes_the_default_and_honours_a_pin() -> None:
    """The safe default is slug-scoped; an explicit profile pin wins (Lima's legacy paths)."""
    data_dir = Path("/nonexistent-test-root")
    peer = site_reference_path(
        Settings(site="fort-wayne", data_dir=data_dir), None, subdir="ferc", filename="x.yaml"
    )
    assert peer == data_dir / "reference/ferc/fort-wayne/x.yaml"
    pinned = site_reference_path(
        Settings(site="fort-wayne", data_dir=data_dir),
        "reference/ferc/legacy.yaml",
        subdir="ferc",
        filename="x.yaml",
    )
    assert pinned == data_dir / "reference/ferc/legacy.yaml"


# --- watermark.hydrology.basin x watermark.hydrology.connectors.echo -----------------------
#
# The basin-screen coverage gap (#1120 follow-up): a registered site whose basin has no
# committed POTW inventory screens against an EMPTY SET and reports `total=0`, which reads
# exactly like "this basin has no dischargers". `basin._load_dischargers` returns `[]` for a
# missing file on purpose — an absent inventory must never fall back to another basin's
# dischargers — so the silence is a deliberate safety property and cannot be removed. What can
# be removed is the possibility of a registered site sitting behind it unnoticed, which is what
# these two guards do.
#
# All three failure modes below were live simultaneously and none of them raised anything:
#   * `muskingum` (mansfield, coshocton) was in no registry at all — `_inventory_path` fell
#     through to a conventional filename that did not exist.
#   * `sandusky` (sandusky) was likewise unregistered.
#   * `scioto` (columbus, new-albany, piketon, portsmouth) WAS registered in both
#     `_BASIN_POTW_INVENTORY` and `echo.BASINS`, with a full three-HUC-8 `Basin` and curated
#     mainstem gages waiting for it — and the inventory had simply never been pulled. That is
#     the worse shape: the code advertised support and the screen returned nothing.


def test_every_registered_sites_basin_is_a_registered_echo_basin() -> None:
    """A profile's `basin` must name a basin the ECHO connector can actually pull."""
    from watermark.hydrology.connectors.echo import BASINS

    unregistered: dict[str, list[str]] = {}
    for slug, prof in SITES.items():
        if prof.basin not in BASINS:
            unregistered.setdefault(prof.basin, []).append(slug)
    assert not unregistered, (
        f"registered sites sit on basins the ECHO connector does not know: {unregistered} — "
        "add a `Basin` (HUC-8 set + caveats) in watermark.hydrology.connectors.echo rather "
        "than letting `watermark npdes --basin` refuse it and the screen read total=0"
    )


def test_every_registered_sites_basin_has_a_committed_potw_inventory() -> None:
    """...and that basin's inventory must be pulled, or its sites screen a silent empty set."""
    # Resolve through the RUNTIME rule, never a copy of it: a guard that re-implements the
    # path convention keeps asserting the old shape after the convention moves, and reports
    # green while every basin resolves somewhere nobody committed — the same silent total=0
    # this guard exists to eliminate.
    from watermark.hydrology.basin import _inventory_relpath

    missing: dict[str, list[str]] = {}
    for slug, prof in SITES.items():
        rel = _inventory_relpath(prof.basin)
        if not (REPO_ROOT / "data" / "reference" / Path(*rel)).is_file():
            missing.setdefault(prof.basin, []).append(slug)
    assert not missing, (
        f"registered sites screen against a POTW inventory that was never pulled: {missing} — "
        "run `watermark npdes --basin <slug>` and commit the result. A missing file is an "
        "EMPTY screen (total=0), which is indistinguishable from a basin with no dischargers"
    )
