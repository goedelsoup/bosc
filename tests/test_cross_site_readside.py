"""#618 — cross-site (non-Lima, non-Ohio) read-side round-trip.

The site axis (``SiteProfile`` / ``WATERMARK_SITE``) is honored on the **write / connector-input**
side but historically leaked Lima/Ohio defaults on the **read / derivation** side — the same
asymmetry that let Ohio-hardcoding through until a non-OH site (Fort Wayne) surfaced it. This
module drives the per-site reference readers (#606), the FERC seam (#608), and the cooling
basis (#607) under ``WATERMARK_SITE=fort-wayne`` (Indiana) and asserts the output is the active
site's, never Lima's. It reads only committed reference data — no network.

Note: Fort Wayne and Lima are *both* in an "Allen County", so the discriminator here is the
state (IN vs OH) and the serving utility (Indiana Michigan Power vs AEP Ohio), not the county.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.economics.baseline import load_baseline
from watermark.economics.energy import load_consumer_energy
from watermark.facility.power import derive_power_basis
from watermark.grid.ferc import derive_ferc_seam
from watermark.grid.utility import load_grid_profile
from watermark.hydrology.cooling import derive_cooling_basis

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def fw_settings() -> Settings:
    """Fort Wayne, IN — a non-Lima, non-Ohio registered site with committed reference data."""
    return Settings(
        site="fort-wayne", data_dir=REPO_ROOT / "data", hydro_offline=True, econ_offline=True
    )


@pytest.fixture
def lima_settings() -> Settings:
    """Lima, OH — the live reference build (the historical hardcoded default)."""
    return Settings(data_dir=REPO_ROOT / "data", hydro_offline=True, econ_offline=True)


# --- #780: an unscoped sibling site defaults to its OWN corpus, never Lima's whole tree ----


def test_effective_corpus_scope_defaults_to_own_slug_not_lima() -> None:
    """#780 — the safe default. ``corpus_relpaths = None`` means "whole tree" ONLY for the
    reference build (Lima); every other site defaults to its own ``<slug>/`` collection, so a
    freshly-registered site (scope left unset) can't silently inherit Lima's Allen-County record.
    An explicit scope (Fort Wayne's IDEM-included tuple) always wins.
    """
    from watermark.sites import SITES, effective_corpus_scope

    assert effective_corpus_scope(SITES["lima"]) is None  # reference build = whole-tree catch-all
    assert effective_corpus_scope(SITES["urbana"]) == ("urbana",)  # unset → own slug, not Lima
    assert effective_corpus_scope(SITES["new-albany"]) == ("new-albany",)
    assert effective_corpus_scope(SITES["fort-wayne"]) == ("fort-wayne", "idem/fort-wayne")


def test_unscoped_sibling_loads_its_own_corpus_not_lima() -> None:
    """The read side honors the #780 default: an unpopulated sibling (Urbana — the #782
    validation candidate, no committed corpus) loads an empty corpus, not Lima's deeds/permits.
    Before the fix its ``None`` scope meant the whole tree, silently inheriting Allen County."""
    from watermark.pipeline.corpus import load_corpus

    urbana = load_corpus(Settings(site="urbana", data_dir=REPO_ROOT / "data"))
    assert not urbana.deeds, "Urbana must not inherit Lima's recorder deeds"
    assert not urbana.permits, "Urbana must not inherit Lima's NPDES permits"
    assert not urbana.summaries, "Urbana must not inherit Lima's OPC estimates"

    # Contrast: Lima (the reference build) still loads its full corpus.
    lima = load_corpus(Settings(site="lima", data_dir=REPO_ROOT / "data"))
    assert lima.deeds and lima.permits, "the reference build still reads the whole tree"


# --- #606: per-site reference YAML readers resolve the active site's path ---------------


def test_load_baseline_reads_fort_wayne_not_lima(
    fw_settings: Settings, lima_settings: Settings
) -> None:
    fw = load_baseline(fw_settings)
    assert fw is not None
    assert fw.fips == "18003"  # Allen County, Indiana — not Lima's 39003 (Allen County, OH)
    assert "Indiana" in fw.area_name
    # The Lima reader still resolves Lima — the slug-scoped split is symmetric.
    lima = load_baseline(lima_settings)
    assert lima is not None and lima.fips == "39003"


def test_load_consumer_energy_reads_indiana(fw_settings: Settings) -> None:
    fw = load_consumer_energy(fw_settings)
    assert fw is not None
    assert fw.area == "IN" and fw.area_name == "Indiana"


def test_load_grid_profile_reads_fort_wayne_utility(
    fw_settings: Settings, lima_settings: Settings
) -> None:
    fw = load_grid_profile(fw_settings)
    assert fw is not None
    assert "Indiana Michigan Power" in fw.serving_utility.utility.value
    assert "AEP Ohio" not in fw.serving_utility.utility.value
    lima = load_grid_profile(lima_settings)
    assert lima is not None and "AEP Ohio" in lima.serving_utility.utility.value


# --- #608: the FERC seam emits the active site's regulator / utility, not Ohio/PUCO/AEP --


def _seam_blob(settings: Settings) -> str:
    """Every cited string in the seam, flattened — so a leak anywhere is caught."""
    seam = derive_ferc_seam(settings=settings)
    b = seam.boundary
    parts = [
        b.ferc_scope.value,
        b.ferc_scope.citation,
        b.puco_scope.value,
        b.puco_scope.citation,
        b.campus_arrangement.value,
        b.campus_arrangement.citation,
        b.note,
        seam.form1.utility,
        seam.form1.pointer.value,
        seam.form1.pointer.citation,
        seam.note,
    ]
    return "\n".join(parts)


def test_ferc_seam_emits_indiana_iurc_not_ohio_puco(fw_settings: Settings) -> None:
    blob = _seam_blob(fw_settings)
    # The active site's regulator + serving utility.
    assert "IURC" in blob and "Indiana" in blob
    assert "Indiana Michigan Power" in blob
    # No Lima/Ohio leak anywhere in the seam.
    assert "PUCO" not in blob
    assert "Ohio" not in blob
    assert "AEP Ohio" not in blob
    # The Form-1 filer is I&M, not Ohio Power Company.
    seam = derive_ferc_seam(settings=fw_settings)
    assert "Indiana Michigan Power" in seam.form1.utility
    assert "Ohio Power Company" not in seam.form1.utility


def test_ferc_seam_still_correct_for_lima(lima_settings: Settings) -> None:
    blob = _seam_blob(lima_settings)
    assert "PUCO" in blob and "AEP Ohio" in blob and "Ohio Power Company" in blob
    assert "IURC" not in blob


# --- #607: the cooling basis takes the active facility's discharge, not Lima's FM-2 ------


def test_cooling_basis_does_not_leak_lima_fm2_for_other_site(
    fw_settings: Settings, lima_settings: Settings
) -> None:
    # Fort Wayne's facility discloses no cooling/industrial blowdown (blowdown_mgd=None) — the high
    # bound must fall back to the site's own power-derived consumptive, never Lima's FM-2 (CMAR) figure.
    fw_high = derive_cooling_basis(settings=fw_settings).consumptive_high
    assert "CMAR" not in (fw_high.citation or "")
    assert "FM2" not in (fw_high.citation or "") and "FM-2" not in (fw_high.citation or "")
    assert "no disclosed blowdown" in (fw_high.citation or "")
    # Lima still traces its cross-check to the disclosed FM-2 discharge (per its facility).
    lima = derive_cooling_basis(settings=lima_settings)
    assert "CMAR" in (lima.consumptive_high.citation or "")
    assert lima.it_load.value == pytest.approx(275.0)
    assert "P0138965" in (lima.it_load.citation or "")  # traces to the active facility's permit


def test_power_basis_traces_to_the_active_facilitys_permit_not_lima(
    fw_settings: Settings, lima_settings: Settings
) -> None:
    # #360/#607: Fort Wayne's power basis (the first non-Lima facility) must carry ITS OWN IDEM
    # permit + derived figures, never Lima's hardcoded P0138965 / 313 MW / 114 x 2.75 MW.
    fw = derive_power_basis(settings=fw_settings)
    assert fw is not None and fw.it_load.value == pytest.approx(90.0)
    assert fw.backup_power.value == pytest.approx(102.0, abs=0.1)  # 34 x 3.0
    blob = (
        " ".join(str(getattr(fw, f).citation or "") for f in ("backup_power", "it_load"))
        + fw.cooling_overhead_note
        + fw.generation_note
        + fw.method
    )
    assert "003-47378" in (fw.it_load.citation or "")  # the IDEM Title V permit
    for lima_literal in ("P0138965", "313", "114 x", "2.75", "250-300"):
        assert lima_literal not in blob, f"Lima literal {lima_literal!r} leaked into Fort Wayne"
    # Lima still carries its own permit.
    lima = derive_power_basis(settings=lima_settings)
    assert lima is not None and "P0138965" in (lima.it_load.citation or "")
