"""Public-subsidy vs. public-benefit ledger for the data-center CRA abatement."""

from __future__ import annotations

from pathlib import Path

from watermark import ledger
from watermark.config import Settings

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
    """The deciding figures the public can't see are recorded as withheld."""
    led = ledger.build_ledger(hydro_settings)
    whats = " ".join(w.what.lower() for w in led.withheld)
    assert "cost-benefit" in whats  # PRR item 4
    assert "compensation" in whats  # school district comp agreement $
    assert (
        "land-assembly" in whats or "purchase prices" in whats
    )  # blank DTE-100 transfer-tax forms
    # The findings name the §22 indemnity (private subsidy for public secrecy).
    assert any("§22" in f or "attorney fees" in f for f in led.findings)


def test_new_aedg_burdens_folded_in(hydro_settings: Settings) -> None:
    """The AEDG-bundle figures (roadwork, TMDL wastewater, CAUV) join the burden ledger."""
    led = ledger.build_ledger(hydro_settings)
    threads = {b.thread for b in led.burdens}
    assert {"roadwork (PAAC)", "wastewater x TMDL", "land conversion (CAUV)"} <= threads
    # The roadwork burden carries the $14.5M contribution figure.
    assert any("14,500,000" in b.headline for b in led.burdens)
    # A finding names the parallel roadwork channel and the surfaced school PILOT.
    assert any("Roadwork Development Agreement" in f for f in led.findings)
    assert any("PILOT" in f for f in led.findings)


def test_sanitary_capital_and_pattern_findings(hydro_settings: Settings) -> None:
    """The commissioners sanitary economics + abatement-pattern findings fold in."""
    led = ledger.build_ledger(hydro_settings)
    threads = {b.thread for b in led.burdens}
    assert "sanitary capital (BOSC)" in threads
    san = next(b for b in led.burdens if b.thread == "sanitary capital (BOSC)")
    assert "3,125,000" in san.headline and "32,000,000" in san.headline
    # Findings: the abatement is a standing pattern (Nutrien) and the (G)(8) shield is BOSC-first.
    assert any("Nutrien" in f for f in led.findings)
    assert any("121.22(G)(8)" in f for f in led.findings)


def test_burdens_span_the_prior_threads(hydro_settings: Settings) -> None:
    """The ledger pulls each cross-thread burden from its committed artifact."""
    led = ledger.build_ledger(hydro_settings)
    threads = {b.thread for b in led.burdens}
    # Toxics, cooling, drainage, federal, and the air permit should all be represented.
    assert {"toxics x dilution", "cooling withdrawal", "drainage scope", "federal nexus"} <= threads
    assert any("genset" in b.headline for b in led.burdens)
    # Every burden cites a committed source.
    assert all(b.source for b in led.burdens)


def test_air_burden_cites_the_modeled_cap_breach(hydro_settings: Settings) -> None:
    """The air burden is model-cited now (#1181): the committed Tier-0 air scenario, not a static
    headline — the event-anchored ceiling breaches the synthetic-minor NOx cap."""
    air = next(b for b in ledger.build_ledger(hydro_settings).burdens if b.thread == "air permit")
    assert "235.62 tpy" in air.headline  # the exact synthetic-minor NOx cap survives (not rounded)
    assert "breach" in air.headline and "132% of cap" in air.headline
    # The source points at the committed air scenario artifact, not just the static permit.
    assert "data/scenarios/lima.air-reliability_dispatch_event_high.scenario.yaml" in air.source


def test_air_burden_falls_back_to_static_permit_fact(tmp_path: Path) -> None:
    """Without a committed air scenario, _burden_air degrades to the static permit fact (#1181)."""
    # A minimal data dir with the permit extraction but no air scenario artifact (scenarios_dir
    # is derived from data_dir, so a fresh tmp tree has an empty scenarios/).
    permit_src = REPO_ROOT / "data" / "extracted" / "permits" / "4132514.epa.yaml"
    permit_dst = tmp_path / "extracted" / "permits" / "4132514.epa.yaml"
    permit_dst.parent.mkdir(parents=True)
    permit_dst.write_text(permit_src.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "scenarios").mkdir()
    item = ledger._burden_air(Settings(data_dir=tmp_path))
    assert item is not None
    assert "synthetic-minor" in item.headline
    assert "P0138965" in item.source  # the static permit citation, not the scenario
