"""Public-subsidy vs. public-benefit ledger for the data-center CRA abatement."""

from __future__ import annotations

from pathlib import Path

from bosc import ledger
from bosc.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_cra_extraction_committed() -> None:
    """The CRA extraction parses with the headline terms."""
    cra = ledger._load_cra(Settings(data_dir=REPO_ROOT / "data"))
    assert cra["abatement"]["percent"] == 75
    assert cra["abatement"]["term_years"] == 15
    assert ledger._num(cra["company_estimates"]["jobs"]) == 50
    # The Fortune-100 parent assurance and non-public school comp are recorded.
    assert cra["beneficiary_assurance"]["parent_is_fortune_100"] is True
    assert cra["school_compensation"]["amounts_public"] is False


def test_ledger_builds(hydro_settings: Settings) -> None:
    led = ledger.build_ledger(hydro_settings)
    ft = led.foregone_tax
    assert ft.capital_usd == 500_000_000
    assert ft.abatement_pct == 75 and ft.term_years == 15
    # Abated = 75% of full; term = annual x 15.
    assert ft.annual_abated_low == round(ft.annual_full_tax_low * 0.75)
    assert ft.term_abated_high == ft.annual_abated_high * 15
    # Per-job abatement is in the millions — worse than the ~$1M/job Ohio comparable.
    assert led.benefit.jobs == 50
    assert led.benefit.abatement_per_job_low > 1_000_000


def test_foregone_is_a_tagged_screening_range(hydro_settings: Settings) -> None:
    """The effective rate is a stated assumption band, not a cited figure."""
    ft = ledger.build_ledger(hydro_settings).foregone_tax
    assert ft.effective_rate_low < ft.effective_rate_high
    assert ft.assessment_ratio == 0.35  # cited Ohio statutory ratio
    assert "assumption" in ft.basis.lower()
    assert ft.term_abated_low < ft.term_abated_high


def test_withheld_records_are_the_pivot(hydro_settings: Settings) -> None:
    """Both deciding figures the public can't see are recorded as withheld."""
    led = ledger.build_ledger(hydro_settings)
    whats = " ".join(w.what.lower() for w in led.withheld)
    assert "cost-benefit" in whats  # PRR item 4
    assert "compensation" in whats  # school district comp agreement $
    # The findings name the §22 indemnity (private subsidy for public secrecy).
    assert any("§22" in f or "attorney fees" in f for f in led.findings)


def test_burdens_span_the_prior_threads(hydro_settings: Settings) -> None:
    """The ledger pulls each cross-thread burden from its committed artifact."""
    led = ledger.build_ledger(hydro_settings)
    threads = {b.thread for b in led.burdens}
    # Toxics, cooling, drainage, federal, and the air permit should all be represented.
    assert {"toxics x dilution", "cooling withdrawal", "drainage scope", "federal nexus"} <= threads
    assert any("genset" in b.headline for b in led.burdens)
    # Every burden cites a committed source.
    assert all(b.source for b in led.burdens)
