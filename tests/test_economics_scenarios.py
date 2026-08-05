"""The economic argument as disciplined scenario bands (#1665, epic #1659 ME-F).

This cluster is the one in tension with the anti-modeling method of `docs/defense-nexus.md`, so
most of what is asserted here is the *refusals*: that a band cannot collapse to a point, that no
scenario can serialize as `verified` or above `low` confidence, that a site with no abatement
instrument on the record is not priced off another county's mills. The arithmetic is checked
against the numbers the deployed frontend model and the ledger essay already publish, so the
typed feed and the prose can be shown to agree rather than merely coexisting.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from watermark.config import Settings
from watermark.economics.model import (
    EconomicScenarios,
    ScenarioAxis,
    ScenarioBand,
    ScenarioLine,
    WithheldInput,
)
from watermark.economics.priors import load_industry_priors
from watermark.economics.scenarios import (
    abatement_usd,
    derive_economic_scenarios,
    exemption_usd,
    load_abatement_instrument,
    load_abatement_parameters,
)
from watermark.site.feeds import CONTRACT_VERSION

_CV = "1.54.0"
_PEER = "urbana"  # a selectable peer with no abatement instrument on the record


@pytest.fixture(scope="module")
def scenarios() -> EconomicScenarios:
    built = derive_economic_scenarios(Settings(site="lima"))
    assert built is not None, "the reference site's abatement instrument must price"
    return built


# --- the discipline, enforced in the type system -------------------------------
def test_a_band_cannot_collapse_to_a_point() -> None:
    """`low == high` is false precision wearing a band's clothes — the model refuses it, so a
    future parameters edit that flattens a knob fails loudly instead of publishing a figure."""
    with pytest.raises(ValidationError, match="must span a range"):
        ScenarioBand(low=0.35, central=0.35, high=0.35, unit="fraction")
    with pytest.raises(ValidationError, match="must span a range"):
        ScenarioBand(low=0.5, central=0.4, high=0.3, unit="fraction")


def test_a_band_central_must_lie_inside_it() -> None:
    with pytest.raises(ValidationError, match="outside the band"):
        ScenarioBand(low=0.2, central=0.9, high=0.45, unit="fraction")


@pytest.mark.parametrize(
    "make",
    [
        lambda **kw: ScenarioAxis(key="k", label="l", question="q?", **kw),
        lambda **kw: ScenarioLine(
            key="k", label="l", band=ScenarioBand(low=1, central=2, high=3, unit="usd"), **kw
        ),
        lambda **kw: WithheldInput(
            key="k", label="l", band=ScenarioBand(low=1, central=2, high=3, unit="usd"), **kw
        ),
    ],
    ids=["axis", "line", "withheld"],
)
def test_no_scenario_figure_can_read_as_an_assertion(make: Any) -> None:
    """The load-bearing refusal. A scenario is a labeled counterfactual: it can never carry the
    `verified` tag, and never a confidence above `low`. Both are structural — a caveat string
    could be dropped in a redesign, a validator cannot."""
    with pytest.raises(ValidationError, match="never carry the tag 'verified'"):
        make(tag="verified", confidence="low")
    with pytest.raises(ValidationError, match="must carry confidence 'low'"):
        make(tag="inference", confidence="high")
    with pytest.raises(ValidationError, match="must carry confidence 'low'"):
        make(tag="open", confidence="medium")


def test_the_model_as_a_whole_is_fixed_open_and_low(scenarios: EconomicScenarios) -> None:
    """`tag`/`confidence` on the container are `Literal`s, not defaults — the whole object is an
    open question at low confidence and cannot be constructed as anything else."""
    assert scenarios.tag == "open"
    assert scenarios.confidence == "low"
    for override in ({"tag": "verified"}, {"tag": "inference"}, {"confidence": "high"}):
        with pytest.raises(ValidationError):
            EconomicScenarios.model_validate({**scenarios.model_dump(), **override})


def test_every_published_figure_carries_low_confidence(scenarios: EconomicScenarios) -> None:
    rows: list[ScenarioAxis | ScenarioLine | WithheldInput] = [
        *scenarios.axes,
        *scenarios.lines,
        *scenarios.withheld,
    ]
    if scenarios.load_per_job is not None:
        rows.append(scenarios.load_per_job)
    for row in rows:
        assert row.confidence == "low", row
        assert row.tag != "verified", row


def test_a_single_corner_is_not_a_band() -> None:
    """Two corners is the floor: one profile priced across the ledger is a point estimate."""
    one = derive_economic_scenarios(Settings(site="lima"))
    assert one is not None
    with pytest.raises(ValidationError, match="at least two profiles"):
        EconomicScenarios.model_validate(
            {**one.model_dump(), "profiles": one.model_dump()["profiles"][:1]}
        )


# --- the instrument gate -------------------------------------------------------
def test_a_peer_with_no_abatement_instrument_is_not_priced() -> None:
    """`data/extracted` is one tree for the whole network, so the CRA file exists no matter which
    site is active. The gate is the PROFILE's declared parameters path — without it a peer reads
    None and its report locks and asks for its own agreement, exactly as `ledgerProfiles(site)`
    already answered null. This is the regression that would silently price Urbana's build off
    Allen County's mills."""
    peer = Settings(site=_PEER)
    assert load_abatement_parameters(peer) is None
    assert load_abatement_instrument(peer) is None
    assert derive_economic_scenarios(peer) is None


# --- the numbers reconcile with what is already published ----------------------
def test_the_instrument_is_read_not_re_keyed() -> None:
    """Every term comes off the committed CRA extraction, so a correction to the record moves the
    bands with it. Re-keying these into the parameters file is the drift this closes."""
    instrument = load_abatement_instrument(Settings(site="lima"))
    assert instrument is not None
    assert instrument.abatement_pct == 0.75  # Res #548-25
    assert instrument.term_years == 15  # CRA §3, per Building
    assert instrument.capex_usd == 500_000_000  # the `~500000000` approx marker survives
    assert instrument.stated_jobs == 50
    assert instrument.real_property_only is True
    # The single figure that would most narrow the band is withheld — and the model knows it.
    assert instrument.school_terms_public is False


def test_the_abatement_arithmetic_matches_the_deployed_model(scenarios: EconomicScenarios) -> None:
    """Pins the Python model to the figures `econLedger.test.ts` and `docs/the-economic-ledger.md`
    already publish: ~$43M at the stated 35% share, ~$62M at the GovCloud profile's 50%, and a
    ~$31M-$62M envelope over the four corners."""
    by_key = {p.key: p for p in scenarios.profiles}
    assert round(by_key["stated"].abatement_usd / 1e6) == 43
    assert round(by_key["govcloud"].abatement_usd / 1e6) == 62
    assert round(by_key["equipment"].abatement_usd / 1e6) == 31
    # The un-abated 25% the public still collects — the essay's ~$14.5M central.
    assert round(by_key["stated"].kept_usd / 1e6, 1) == 14.5

    line = next(line for line in scenarios.lines if line.key == "abatement")
    assert round(line.band.low / 1e6) == 31
    assert round(line.band.high / 1e6) == 62
    assert round(line.band.central / 1e6) == 43


def test_the_pure_arithmetic_is_a_function_of_its_arguments() -> None:
    """The formulas are site-agnostic (only their INPUTS are one county's instrument), so they can
    be checked directly — the same separation `econLedger.ts` keeps."""
    assert (
        round(
            abatement_usd(
                capex=500_000_000,
                building_share=0.35,
                effective_rate=0.35 * 0.063,
                pct=0.75,
                years=15,
            )
            / 1e6
        )
        == 43
    )
    # The exemption is the INVERSE of the building share: a shell-light build exempts more.
    heavy = exemption_usd(capex=500_000_000, building_share=0.25, sales_rate=0.0725, refresh=1.5)
    light = exemption_usd(capex=500_000_000, building_share=0.50, sales_rate=0.0725, refresh=1.5)
    assert heavy > light


def test_the_two_subsidies_are_anti_correlated_so_the_net_band_is_narrower(
    scenarios: EconomicScenarios,
) -> None:
    """A correction the typed model makes to the prose. The essay reached "~$45M-$90M" by adding
    the independent extremes of the abatement and exemption bands — but the building share moves
    them in OPPOSITE directions, so no single scenario sits at both extremes. Pricing each corner
    and taking the envelope gives a genuinely narrower net band, and that is the honest one."""
    lines = {line.key: line for line in scenarios.lines}
    ab, ex, net = lines["abatement"].band, lines["exemption"].band, lines["net"].band
    assert net.low > ab.low + ex.low
    assert net.high < ab.high + ex.high
    # Each corner's net is its own two lines summed — no cross-scenario mixing.
    for profile in scenarios.profiles:
        assert profile.net_subsidy_usd == round(profile.abatement_usd + profile.exemption_usd)


def test_the_exemption_line_stays_open_on_application(scenarios: EconomicScenarios) -> None:
    """The magnitude is computed, but whether this campus holds a DCTE agreement at all is a
    question the record does not answer — so the line is `[open]`, not `[inference]`."""
    line = next(line for line in scenarios.lines if line.key == "exemption")
    assert line.tag == "open"
    assert "DCTE" in line.note


def test_load_per_job_bands_the_prose_figure(scenarios: EconomicScenarios) -> None:
    """`docs/ECONOMICS.md` §3's "~5-6 MW per job" used the stated headcount alone. The typed band
    keeps that as its reference CORNER (275 MW / 50 jobs = 5.5) and widens honestly to the
    lean-ops corner — the prose number is the band's central, not its extent."""
    line = scenarios.load_per_job
    assert line is not None
    assert line.band.unit == "MW_per_job"
    assert line.band.central == 5.5
    assert line.band.low == 5.0  # 250 MW over the most jobs
    assert line.band.high == 10.0  # 300 MW over the fewest
    assert line.tag == "inference"


# --- the cited axes ------------------------------------------------------------
def test_the_axes_come_from_the_committed_priors_file_not_a_copy(
    scenarios: EconomicScenarios,
) -> None:
    """The GovCloud premium was a hand-copied "~20-30%" in two docs and a frontend array. It is
    now read from the file that cites it, so the feed and the prior cannot disagree."""
    priors = load_industry_priors(Settings(site="lima"))
    assert priors is not None
    axis = next(a for a in scenarios.axes if a.key == "govcloud_premium")
    prior = priors.require("govcloud_premium")
    assert axis.band is not None
    assert (axis.band.low, axis.band.high) == (prior.low, prior.high) == (0.20, 0.30)
    # An industry range is `[reference]`, and its application here stays open — that pairing is
    # what stops a real published premium being read as a fact about this campus.
    assert axis.tag == "reference"
    assert axis.site_status == "open"
    assert axis.sources, "an axis with no source is an assertion"


def test_a_corroboration_axis_asserts_no_band(scenarios: EconomicScenarios) -> None:
    """Two priors are qualitative findings from other jurisdictions/vendors, deliberately not
    promoted to a number. They still ship with their sources, so the claim is checkable — but a
    band-less axis must stay band-less rather than being given a synthesized range."""
    for key in ("ai_rack_refresh", "salestax_exemption_dominance"):
        axis = next(a for a in scenarios.axes if a.key == key)
        assert axis.band is None
        assert axis.sources


def test_every_axis_and_withheld_input_asks_a_question(scenarios: EconomicScenarios) -> None:
    """An axis exists to sharpen a question, not to answer one; a withheld input exists to name
    the disclosure that would collapse its band. Both obligations are in the row, not in a
    page-level caveat a redesign could drop."""
    for axis in scenarios.axes:
        assert axis.question.endswith("?"), axis.key
    for item in scenarios.withheld:
        assert item.resolving_record, item.key
        assert item.why, item.key


def test_the_withheld_inputs_are_the_four_that_move_the_sign(scenarios: EconomicScenarios) -> None:
    assert {w.key for w in scenarios.withheld} == {
        "building_share",
        "jobs",
        "equipment_refresh",
        "school_compensation",
    }
    school = next(w for w in scenarios.withheld if w.key == "school_compensation")
    assert school.band.low == 0  # genuinely undisclosed — a screening range, not an estimate
    assert school.band.dist == "uniform"  # so its central carries no information


def test_the_constants_all_carry_citations(scenarios: EconomicScenarios) -> None:
    """Every modeling constant is a `ProvenancedValue`, so a reader can audit the arithmetic
    without leaving the feed. The millage in particular must announce itself as an assumption."""
    by_key = {c.key: c.value for c in scenarios.constants}
    assert set(by_key) >= {
        "capital_investment",
        "abatement_percent",
        "term_years",
        "assessment_ratio",
        "effective_commercial_mills",
        "effective_rate",
        "sales_and_use_rate",
        "equipment_refresh",
    }
    for key, value in by_key.items():
        assert value.citation, key
    assert by_key["assessment_ratio"].source == "reference"  # R.C. 5715.01 — statutory
    mills = by_key["effective_commercial_mills"]
    assert mills.source == "assumption"  # NOT a cited Allen County rate
    assert mills.confidence == "low"
    assert mills.has_range  # the band it scales the whole ledger by


def test_the_govcloud_profile_disclaims_itself(scenarios: EconomicScenarios) -> None:
    """The most easily misread row in the feed. It is the top corner of the band precisely
    because it turns both knobs, so the row itself has to say it is not a defense finding."""
    govcloud = next(p for p in scenarios.profiles if p.key == "govcloud")
    assert govcloud.net_subsidy_usd == max(p.net_subsidy_usd for p in scenarios.profiles)
    assert "not a finding" in govcloud.note
    assert "defense" in govcloud.basis.lower()
    assert "not a defense finding" in scenarios.disclaimer or "NOT a claim" in scenarios.disclaimer


# --- the feed -----------------------------------------------------------------
def _feed(bundle: Path) -> dict[str, Any] | None:
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    ref = next((f for f in manifest["feeds"] if f["name"] == "economics-scenarios"), None)
    if ref is None:
        return None
    assert ref["kind"] == "object"
    assert ref["count"] == 1
    payload: dict[str, Any] = json.loads((bundle / ref["path"]).read_text(encoding="utf-8"))
    return payload


def test_contract_version_bumped_for_the_scenarios_feed() -> None:
    """One new feed → MINOR (1.42.0 → 1.43.0, since advanced by the `impact-study`
    feed 1.44.0 #1804 and the `cooling-reconciliation` feed 1.45.0 #1805): a pre-1.43 reader is unaffected and a pre-1.43 bundle simply has no scenario
    bands to render."""
    assert CONTRACT_VERSION == _CV


def test_the_reference_bundle_publishes_the_scenario_bands(lima_bundle: Path) -> None:
    """The acceptance criterion: the frontend reads a typed feed instead of a hardcoded array."""
    manifest = json.loads((lima_bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["contract_version"] == _CV
    feed = _feed(lima_bundle)
    assert feed is not None, "the reference build must publish the scenario bands"
    assert feed["site"] == "lima"
    assert feed["tag"] == "open"
    assert feed["confidence"] == "low"
    assert {p["key"] for p in feed["profiles"]} == {
        "stated",
        "equipment",
        "hyperscale",
        "govcloud",
    }
    assert feed["instrument_record"].endswith("cra-agreement.cra.yaml")


def test_a_peer_bundle_carries_no_scenario_bands(
    site_bundle: Any,
) -> None:
    """A peer must not inherit the reference site's instrument — the feed is simply absent, which
    is what makes the frontend's lock-and-ask behaviour correct rather than a cosmetic guard."""
    assert _feed(site_bundle(_PEER)) is None


def test_the_feed_round_trips_through_the_model(lima_bundle: Path) -> None:
    """The published JSON revalidates — so every refusal above also holds for anything that reads
    the bundle back, not only for what this process constructed."""
    feed = _feed(lima_bundle)
    assert feed is not None
    reloaded = EconomicScenarios.model_validate(feed)
    assert reloaded.has_material_content
    assert len(reloaded.profiles) == 4
    assert len(reloaded.lines) == 5
