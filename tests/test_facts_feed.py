"""Tests for the normalized ``facts`` feed (#1587).

The projector tests are pure (no corpus load) — they pin the subject/predicate grammar, the
``status`` mapping onto the evidence vocabulary, the verbatim value copy, and the chain-of-custody
page-honesty rule (a projected fact never invents a page). One integration test exports a real Lima
bundle and asserts the feed emits, every ``(subject, predicate)`` is unique, and the issue's
motivating ``genset_count x genset_rating`` example resolves.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from watermark.config import Settings
from watermark.site.export import export_bundle
from watermark.site.facts import (
    _project_air_scenarios,
    _project_consumer_energy,
    _project_economics_baseline,
    _project_greenops,
    _project_hydrology_scenarios,
    build_facts,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

_CV = "1.30.0"


def _pv(value: Any, unit: str, source: str, **extra: Any) -> dict[str, Any]:
    """A serialized ProvenancedValue, as it appears in an assembled feed."""
    return {"value": value, "unit": unit, "source": source, "citation": None, **extra}


# --- status mapping onto the evidence vocabulary -------------------------------------------
def test_status_maps_source_kind_to_the_evidence_tags() -> None:
    feed = {
        "fips": "39003",
        "area_name": "Allen County, Ohio",
        "latest": {
            "total_employment": _pv(49690.0, "jobs", "connector"),  # -> verified
            "avg_annual_pay": _pv(58790.0, "USD/year", "document"),  # -> verified
            "sectors": [],
        },
        "median_household_income": _pv(62001.0, "USD/yr", "reference"),  # -> reference
    }
    by_pred = {f.predicate: f for f in _project_economics_baseline(feed, "lima")}
    assert by_pred["total_employment"].status == "verified"
    assert by_pred["total_employment"].evidence.verified is True
    assert by_pred["avg_annual_pay"].status == "verified"
    assert by_pred["median_household_income"].status == "reference"
    assert by_pred["median_household_income"].evidence.verified is False


def test_derived_and_assumption_are_inference() -> None:
    feed = {
        "headline": [
            {"key": "electricity", "value": _pv(1234.0, "kWh", "derived")},
            {"key": "compute", "value": _pv(6366.0, "vCPU-hrs", "derived")},
        ],
        "water": {"budget_cap": _pv(150.0, "gal", "assumption")},
    }
    by_pred = {f.predicate: f for f in _project_greenops(feed, "lima")}
    assert by_pred["electricity"].status == "inference"
    assert by_pred["water_budget_cap"].status == "inference"
    assert by_pred["water_budget_cap"].subject == "platform:bosc"


# --- subject / predicate grammar -----------------------------------------------------------
def test_economics_subject_grammar_county_and_sector() -> None:
    feed = {
        "fips": "39003",
        "area_name": "Allen County, Ohio",
        "latest": {
            "total_employment": _pv(49690.0, "jobs", "connector"),
            "sectors": [
                {
                    "naics": "62",
                    "sector_name": "Health Care & Social Assistance",
                    "annual_avg_employment": _pv(9452.0, "jobs", "connector"),
                    "location_quotient": _pv(1.4, "ratio", "derived"),
                }
            ],
        },
    }
    facts = _project_economics_baseline(feed, "lima")
    county = next(f for f in facts if f.predicate == "total_employment")
    assert county.subject == "county:39003"
    assert county.subject_kind == "county"
    assert county.subject_label == "Allen County, Ohio"
    sector = next(f for f in facts if f.predicate == "annual_avg_employment")
    assert sector.subject == "sector:39003:62"
    assert sector.subject_kind == "sector"
    assert "Health Care" in sector.subject_label


def test_consumer_energy_predicate_is_fuel_metric() -> None:
    feed = {
        "area": "OH",
        "area_name": "Ohio",
        "prices": [
            {
                "fuel": "electricity",
                "metric": "price",
                "value": _pv(16.96, "cents/kWh", "connector"),
            },
            {"fuel": "natural_gas", "metric": "price", "value": _pv(13.85, "$/Mcf", "connector")},
        ],
    }
    by_pred = {f.predicate: f for f in _project_consumer_energy(feed, "lima")}
    assert set(by_pred) == {"electricity_price", "natural_gas_price"}
    assert by_pred["electricity_price"].subject == "state:oh"
    assert by_pred["electricity_price"].subject_kind == "state"


def test_air_scenarios_pollutant_predicate_and_subject() -> None:
    rows = [
        {
            "scenario": {"name": "baseline"},
            "engine_mw": _pv(2.75, "MW", "document"),
            "emissions": [{"pollutant": "NOx", "tpy": _pv(69.255, "tpy", "derived")}],
        }
    ]
    facts = _project_air_scenarios(rows, "lima")
    by_pred = {f.predicate: f for f in facts}
    assert by_pred["engine_mw"].subject == "air-scenario:baseline"
    assert by_pred["engine_mw"].status == "verified"
    assert by_pred["nox_tpy"].value == 69.255
    assert by_pred["nox_tpy"].status == "inference"


def test_hydrology_scenario_subject_labelled_by_receiving_water() -> None:
    rows = [
        {
            "scenario": {"name": "buildout", "cooling_demand": _pv(3.2, "MGD", "assumption")},
            "receiving_water_name": "Ottawa River",
            "consumptive_loss": _pv(4.8, "cfs", "derived"),
            "receiving_7q10": _pv(1.1, "cfs", "document"),
        }
    ]
    facts = _project_hydrology_scenarios(rows, "lima")
    loss = next(f for f in facts if f.predicate == "consumptive_loss")
    assert loss.subject == "hydrology-scenario:buildout"
    assert loss.subject_label == "buildout — Ottawa River"
    assert {f.predicate for f in facts} == {"consumptive_loss", "receiving_7q10", "cooling_demand"}


# --- value + evidence discipline -----------------------------------------------------------
def test_value_and_band_are_copied_verbatim_and_page_never_invented() -> None:
    feed = {
        "fips": "39003",
        "area_name": "Allen County, Ohio",
        "latest": {
            "total_employment": _pv(
                49690.0, "jobs", "connector", low=48000.0, high=51000.0, confidence="high"
            ),
            "sectors": [],
        },
    }
    fact = _project_economics_baseline(feed, "lima")[0]
    assert fact.value == 49690.0 and fact.unit == "jobs"
    assert (fact.low, fact.high) == (48000.0, 51000.0)  # uncertainty band carried through
    assert fact.evidence.confidence == "high"
    assert fact.evidence.page is None  # a ProvenancedValue carries no page — never fabricated


def test_bare_repo_path_citation_is_lifted_into_source() -> None:
    feed = {
        "fips": "39003",
        "area_name": "Allen County",
        "latest": {
            "total_employment": _pv(1.0, "jobs", "document", citation="data/reference/x.yaml"),
            "sectors": [],
        },
    }
    fact = _project_economics_baseline(feed, "lima")[0]
    assert fact.evidence.source == "data/reference/x.yaml"  # a bare path is linkable
    # A prose/formula citation is NOT a path — kept as text only.
    feed["latest"]["total_employment"]["citation"] = "347.9 MW x 8760 h (formula)"
    fact2 = _project_economics_baseline(feed, "lima")[0]
    assert fact2.evidence.source is None
    assert fact2.evidence.citation == "347.9 MW x 8760 h (formula)"


# --- integration: a real Lima bundle -------------------------------------------------------
@pytest.fixture(scope="module")
def bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("facts-bundle") / "b"
    settings = Settings(data_dir=REPO_ROOT / "data")
    export_bundle(
        settings, out_dir=out, generated_at="2026-01-01T00:00:00+00:00", skip_embeddings=True
    )
    return out


def _facts(bundle: Path) -> list[dict[str, Any]]:
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    ref = next(f for f in manifest["feeds"] if f["name"] == "facts")
    assert ref["kind"] == "collection"
    path = bundle / "feeds" / ("facts.ndjson" if "ndjson" in ref["media_type"] else "facts.json")
    text = path.read_text(encoding="utf-8")
    if "ndjson" in ref["media_type"]:
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return json.loads(text)


def test_facts_feed_emitted_at_contract_version(bundle: Path) -> None:
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["contract_version"] == _CV
    facts = _facts(bundle)
    assert len(facts) > 0


def test_every_subject_predicate_is_unique(bundle: Path) -> None:
    facts = _facts(bundle)
    keys = [(f["subject"], f["predicate"]) for f in facts]
    assert len(keys) == len(set(keys)), "duplicate (subject, predicate) survived dedup"


def test_no_fabricated_pages_and_statuses_are_grammar(bundle: Path) -> None:
    facts = _facts(bundle)
    assert all(f["evidence"]["page"] is None for f in facts)  # Lima's PVs carry no page
    assert all(f["status"] in {"verified", "inference", "reference", "open"} for f in facts)
    # `verified` is derived, never asserted independently of source_kind.
    for f in facts:
        assert f["evidence"]["verified"] == (
            f["evidence"]["source_kind"] in {"document", "connector"}
        )


def test_motivating_generator_example_resolves(bundle: Path) -> None:
    """genset_count x genset_rating → backup MW, both [verified] off the air permit (#1587)."""
    facts = {(f["subject"], f["predicate"]): f for f in _facts(bundle)}
    count = facts[("facility:lima", "genset_count")]
    rating = facts[("facility:lima", "genset_rating")]
    assert count["status"] == "verified" and rating["status"] == "verified"
    assert count["value"] == 114.0 and rating["value"] == 2.75
    assert count["value"] * rating["value"] == pytest.approx(313.5)


def test_build_facts_skips_absent_feeds() -> None:
    # No payloads + a facility-bearing site still yields the derived PowerBasis facts, and never
    # crashes on missing feeds.
    settings = Settings(data_dir=REPO_ROOT / "data")
    facts = build_facts({}, settings=settings)
    assert all(f.feed == "facility-power" for f in facts)  # only PowerBasis, no feed payloads
