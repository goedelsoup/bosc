"""FERC regulatory seam (#97): the jurisdictional map names FERC (wholesale/interstate)
and PUCO (retail), the campus is classified PUCO-retail (grid-served), the captured
co-location dockets (ER24-2172 / AD24-11) are cited evidence, and the committed YAML
round-trips. Hermetic - reads committed reference data only, no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.grid._registry import SERVING_UTILITIES, is_registered, utility_identity
from watermark.grid.ferc import (
    derive_ferc_seam,
    load_ferc_seam,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def grid_settings() -> Settings:
    """Real repo data dir (reads committed reference data); no network."""
    return Settings(data_dir=REPO_ROOT / "data", hydro_offline=True, econ_offline=True)


def test_jurisdictional_boundary_splits_ferc_and_puco(grid_settings: Settings) -> None:
    seam = derive_ferc_seam(settings=grid_settings)
    b = seam.boundary
    # FERC scope names wholesale + interstate transmission, anchored to the FPA.
    assert "FERC" in b.ferc_scope.value
    assert "wholesale" in b.ferc_scope.value.lower()
    assert "interstate" in b.ferc_scope.value.lower()
    assert "Federal Power Act" in b.ferc_scope.citation
    assert b.ferc_scope.confidence == "high"
    # PUCO scope names Ohio retail service / rates.
    assert "PUCO" in b.puco_scope.value
    assert "retail" in b.puco_scope.value.lower()
    assert b.puco_scope.confidence == "high"


def test_campus_classified_puco_retail_grid_served(grid_settings: Settings) -> None:
    seam = derive_ferc_seam(settings=grid_settings)
    arr = seam.boundary.campus_arrangement
    # The campus is classified PUCO-retail (grid-served), cross-referencing the #94
    # AEP Ohio identification, with co-location named as the FERC alternative.
    assert "PUCO retail" in arr.value
    assert "grid-served" in arr.value
    assert "AEP Ohio" in arr.value
    assert "co-location" in arr.value.lower()
    assert "#94" in arr.citation
    # A classification, not asserted fact: medium confidence, verify-flagged.
    assert arr.confidence == "medium"
    assert "verify" in arr.citation.lower()


def test_dockets_include_real_co_location_proceedings(grid_settings: Settings) -> None:
    seam = derive_ferc_seam(settings=grid_settings)
    by_no = {d.docket_no: d for d in seam.dockets}
    # The Talen/Susquehanna - AWS co-location rejection (ER24-2172).
    assert "ER24-2172" in by_no
    er = by_no["ER24-2172"]
    assert "co-location" in er.topic
    assert "rejected" in er.status.lower()
    assert "ER24-2172" in er.fact.citation
    assert "verify" in er.fact.citation.lower()
    assert er.fact.source == "reference"
    # The FERC large-load co-location technical conference (AD24-11-000).
    assert "AD24-11-000" in by_no
    ad = by_no["AD24-11-000"]
    assert "AD24-11-000" in ad.fact.citation
    assert "verify" in ad.fact.citation.lower()
    # The broad PJM co-location policy entry is described, not pinned, at low confidence.
    broad = next(d for d in seam.dockets if d.docket_no == "")
    assert broad.fact.confidence == "low"


def test_form1_is_a_cited_pointer_not_a_fabricated_figure(grid_settings: Settings) -> None:
    seam = derive_ferc_seam(settings=grid_settings)
    f1 = seam.form1
    assert "Ohio Power Company" in f1.utility
    assert "FERC Form 1" in f1.pointer.value
    assert "FERC Online" in f1.pointer.citation
    # No numeric figure is asserted unless confidently cited (prefer omission).
    assert f1.rate_base is None
    assert f1.operating_revenue is None


def test_seam_note_cross_references_economics(grid_settings: Settings) -> None:
    seam = derive_ferc_seam(settings=grid_settings)
    # The seam ties the grid arrangement to which regulator sets the price (#91).
    assert "#91" in seam.note
    assert "PUCO retail" in seam.note
    assert "FERC wholesale" in seam.note


def test_every_registered_utility_carries_both_halves_of_its_identity() -> None:
    """H2/#1645: the FERC + grid halves of a utility's identity are one record, not two maps.

    A5/#1638 could only bolt keyset equality across ``_FORM1_FILER`` and ``_UTILITY_GRID``; the
    collapse into :data:`SERVING_UTILITIES` makes a keyset drift unrepresentable, so what is
    still worth asserting is that no entry is *half*-filled — an empty FERC filer or an empty
    zone citation would reintroduce the WPAFB/Xenia failure (#4922 falling back to "the serving
    utility") from inside a registered row rather than from a missing key.
    """
    assert SERVING_UTILITIES, "the serving-utility registry must not be empty"
    for number, ident in SERVING_UTILITIES.items():
        blank = [
            f for f in ident._fields if isinstance(getattr(ident, f), str) and not getattr(ident, f)
        ]
        assert not blank, f"utility #{number} has empty identity fields: {blank}"
        assert ident.operating_company != "the serving utility", (
            f"utility #{number} is registered but names no FERC filer — that is the unlisted "
            "fallback's wording, which a registered row must never carry"
        )


def test_every_registered_site_resolves_a_named_serving_utility_or_a_clean_fallback() -> None:
    """H2/#1645: sweep all 26 profiles — each either hits the registry or degrades honestly.

    The multi-site oracle A5's keyset check couldn't be: it compared the two maps to each other,
    so both could go stale together against the site registry. This compares them to the sites
    that actually exist. A profile whose ``eia861_utility_number`` is registered must name a real
    operating company; one that is not must land on the neutral fallback — never a half-state,
    and never another site's utility.
    """
    from watermark.sites import SITES

    for slug, prof in SITES.items():
        ident = utility_identity(prof.eia861_utility_number)
        if is_registered(prof.eia861_utility_number):
            assert ident.operating_company != "the serving utility", slug
            assert ident.holding_company, slug
        else:
            # An unregistered number must not silently borrow a registered utility's identity.
            assert ident.operating_company == "the serving utility", slug
            assert "not confirmed" in ident.rto_citation, slug


def test_aes_ohio_sites_name_their_ferc_filer(grid_settings: Settings) -> None:
    """A5/#1638: a #4922 (AES Ohio) site now names Dayton P&L, not 'the serving utility'."""
    settings = Settings(
        site="wpafb", data_dir=REPO_ROOT / "data", hydro_offline=True, econ_offline=True
    )
    seam = derive_ferc_seam(settings=settings)
    assert "Dayton Power and Light" in seam.form1.utility
    assert "the serving utility" not in seam.form1.utility
    assert seam.form1.rate_base is None  # still a cited pointer, not a fabricated figure


def test_ferc_seam_path_is_per_site(tmp_path: Path) -> None:
    """B1/#1639: a non-Lima site resolves a slug-scoped path, never Lima's shared file.

    The seam embeds per-site content (jurisdiction OH→IN, the serving utility), so a
    ``watermark --site fort-wayne ferc`` write must not clobber Lima's committed file.
    """
    from watermark.grid.ferc import _reference_path

    lima = _reference_path(Settings(site="lima", data_dir=tmp_path))
    fw = _reference_path(Settings(site="fort-wayne", data_dir=tmp_path))
    assert lima != fw
    assert lima.name == "ferc-seam.yaml" and "fort-wayne" not in str(lima)
    assert "fort-wayne" in str(fw)


def test_committed_ferc_seam_loads() -> None:
    """The committed reference YAML round-trips into the model."""
    seam = load_ferc_seam(Settings(data_dir=REPO_ROOT / "data"))
    assert seam is not None
    assert "FERC" in seam.boundary.ferc_scope.value
    assert "PUCO" in seam.boundary.puco_scope.value
    assert "PUCO retail" in seam.boundary.campus_arrangement.value
    dockets = {d.docket_no for d in seam.dockets}
    assert "ER24-2172" in dockets
    assert "AD24-11-000" in dockets
    assert seam.form1.utility == "Ohio Power Company (AEP Ohio)"
