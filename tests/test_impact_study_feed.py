"""Tests for the ``impact-study`` feed (#1804, epic #1803 P1).

The projector tests are pure (no corpus load) — they pin the verdict rules (row counts +
content probes, never presence alone; ``na`` watch states for a facility-less site's
project-dependent chapters), the JS-parity formatting primitives (the shipped display
strings must be byte-identical to what ``web/packages/core/src/study.ts`` composes — the
frontend's ``study.parity.test.ts`` is the cross-language referee over every committed
bundle), the curated gap → lead joins (a dangling id fails the export loudly), and the
serialized camelCase shape the frontend renders verbatim. Integration tests read the shared
Lima bundle and assert the feed ships at the new contract with the expected verdicts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from watermark.site.impact_study import (
    STUDY_GAP_LEADS,
    _fmt_mult,
    _fmt_ranged,
    _js_num,
    _js_round,
    _js_to_fixed,
    _stat_decimals,
    build_impact_study,
)
from watermark.site.readiness import State

_CV = "2.1.0"

_CHAPTER_IDS = [
    "method",
    "project",
    "assembly",
    "water-supply",
    "discharge",
    "heat",
    "groundwater",
    "stormwater",
    "air",
    "labor",
    "power",
    "fiscal",
    "governance",
    "balance",
    "missing",
]


def _facility(**extra: Any) -> dict[str, Any]:
    """A serialized FacilityItem row, minimal for the projector's reads."""
    return {
        "key": "campus-x",
        "name": "Campus X",
        "is_primary": True,
        "status": "investigation",
        "cooling_model": "evaporative_tower",
        "cooling_model_source": "assumption",
        "it_load_mw": 150.0,
        "it_load_low_mw": None,
        "it_load_high_mw": None,
        "air_permit_citation": None,
        "disclosed_investment_usd": None,
        **extra,
    }


def _scenario(name: str = "buildout", loss: float = 3.0, **extra: Any) -> dict[str, Any]:
    """A serialized ScenarioResult row, minimal for the projector's reads."""
    return {
        "scenario": {"name": name, "cooling_model": "evaporative_tower", "basis": None},
        "cooling_model": "evaporative_tower",
        "consumptive_loss": {
            "value": loss,
            "unit": "cfs",
            "source": "derived",
            "low": None,
            "high": None,
        },
        "receiving_7q10": {
            "value": 0.2,
            "unit": "cfs",
            "source": "document",
            "low": None,
            "high": None,
        },
        "receiving_water_name": "Test River",
        "assimilative": [],
        **extra,
    }


def _build(
    payloads: dict[str, Any],
    counts: dict[str, int],
    *,
    site: str = "testsite",
    facility_domain: State = "seeded",
) -> dict[str, Any]:
    """Run the projector and index the rows by chapter."""
    rows = build_impact_study(
        payloads, site=site, feed_counts=counts, facility_domain=facility_domain
    )
    assert [r.chapter for r in rows] == _CHAPTER_IDS  # 15 chapters, registry order, always
    return {r.chapter: r for r in rows}


# --- verdicts: row counts + probes, never presence alone -----------------------------------
def test_facility_less_site_watches_instead_of_scolding() -> None:
    by = _build({}, {}, facility_domain="absent")
    # Project-dependent chapters are `na` (watch state) — never `gap` — and carry nothing.
    for chapter in (
        "water-supply",
        "heat",
        "groundwater",
        "stormwater",
        "air",
        "fiscal",
        "balance",
    ):
        m = by[chapter].model
        assert m.status == "na"
        assert m.stats == [] and m.gaps == []
    # The project chapter is the finding itself: a disclosed project is the missing record.
    assert by["project"].model.status == "gap"
    assert by["project"].model.gaps[0].missing_record.startswith("a disclosed project")
    # Every row keys site-level (facility_key null) so the frontend's null match holds.
    assert all(r.facility_key is None for r in by.values())


def test_present_but_empty_feed_is_not_on_the_record() -> None:
    # fort-wayne's case: `hydrology-scenarios` ships with 0 rows — the chapter must read
    # gap off the COUNT, not data off presence.
    payloads = {"facility": [_facility()], "hydrology-scenarios": []}
    counts = {"facility": 1, "hydrology-scenarios": 0}
    by = _build(payloads, counts)
    assert by["water-supply"].model.status == "gap"
    # ... and the discharge chapter carries only the baseline-burden caveat, no fabricated stat.
    assert by["discharge"].model.stats == []


def test_optional_feed_alone_reads_baseline_partial() -> None:
    payloads = {"facility": [_facility()], "rsei": {"facilities": []}}
    counts = {"facility": 1, "rsei": 1}
    by = _build(payloads, counts)
    m = by["discharge"].model
    assert m.status == "partial"
    assert m.status_reasons == [
        "baseline context only — the project-side record has not been produced"
    ]


def test_any_required_alternative_suffices() -> None:
    payloads = {"facility": [_facility()], "dewatering": {"wells": []}}
    counts = {"facility": 1, "dewatering": 1}
    by = _build(payloads, counts)
    assert by["groundwater"].model.status == "data"


def test_cooling_probe_brackets_the_water_chapter() -> None:
    payloads = {
        "facility": [_facility(cooling_model="unknown")],
        "hydrology-scenarios": [_scenario()],
    }
    counts = {"facility": 1, "hydrology-scenarios": 1}
    by = _build(payloads, counts)
    m = by["water-supply"].model
    assert m.status == "partial"
    assert "cooling method undisclosed" in m.status_reasons[0]
    # The probe-level ask rides as a gap panel even though the chapter is not `gap`.
    assert any("bracketed range across candidate archetypes" in g.missing_record for g in m.gaps)


def test_power_withholds_the_screening_bracket_until_grounded() -> None:
    grid = {
        "utility_profile": {"utility": "Test Power", "retail_sales_gwh": {"value": 1000.0}},
        "ba_profile": {"ba": "PJM"},
        "load_share": None,
        "note": "",
    }
    payloads = {"facility": [_facility()], "grid": grid}
    counts = {"facility": 1, "grid": 1}
    by = _build(payloads, counts, facility_domain="seeded")
    m = by["power"].model
    assert m.status == "partial"
    assert "withheld until an instrument grounds it" in m.status_reasons[0]
    assert any("an instrument that grounds the IT load" in g.missing_record for g in m.gaps)
    # A live (instrument-grounded) facility clears the probe.
    by_live = _build(payloads, counts, facility_domain="live")
    assert by_live["power"].model.status == "data"
    assert by_live["power"].model.gaps == []


def test_balance_synthesizes_the_screened_chapters() -> None:
    payloads = {"facility": [_facility()], "hydrology-scenarios": [_scenario()]}
    counts = {"facility": 1, "hydrology-scenarios": 1}
    by = _build(payloads, counts)
    m = by["balance"].model
    assert m.status == "partial"
    assert m.status_reasons[0].startswith("synthesizes the screened chapters —")


# --- the gap grammar (the frontend guardrail, enforced at the producer) --------------------
def test_gap_copy_is_a_noun_phrase() -> None:
    by = _build({}, {}, facility_domain="absent")
    for row in by.values():
        for g in row.model.gaps:
            assert not g.missing_record.lower().startswith("no "), (
                f"{row.chapter}: gap copy must complete 'Computing it requires ___'"
            )


# --- curation: one board, one ask — a dangling join refuses the write ----------------------
def test_curated_leads_ride_the_gaps_and_validate_against_the_board() -> None:
    leads = [{"id": lid} for ids in STUDY_GAP_LEADS["lima"].values() for lid in ids]
    by = _build({"leads": leads}, {"leads": len(leads)}, site="lima", facility_domain="absent")
    fiscal = by["fiscal"]
    assert fiscal.model.status == "na"  # facility-less: fiscal watches; the joins still ship
    assert fiscal.lead_ids == ["PRR-04", "GH-35"]
    # An uncurated site ships clean rows — never a borrowed or fuzzy-matched join.
    assert _build({}, {}, site="urbana", facility_domain="absent")["fiscal"].lead_ids == []


def test_unknown_curated_lead_fails_the_export() -> None:
    with pytest.raises(ValueError, match="not on the site's leads board"):
        build_impact_study(
            {"leads": [{"id": "SOMETHING-ELSE"}]},
            site="lima",
            feed_counts={"leads": 1},
            facility_domain="live",
        )


def test_gap_level_joins_attach_only_where_a_gap_has_none() -> None:
    leads = [{"id": lid} for ids in STUDY_GAP_LEADS["lima"].values() for lid in ids]
    payloads = {
        "leads": leads,
        "facility": [_facility(cooling_model="unknown")],
        "hydrology-scenarios": [_scenario()],
    }
    counts = {"leads": len(leads), "facility": 1, "hydrology-scenarios": 1}
    by = _build(payloads, counts, site="lima")
    gaps = by["water-supply"].model.gaps
    assert gaps and gaps[0].lead_ids == ["FORCEMAIN-MGD", "LIMA-WWTP-SHARE", "H1-DRAW"]


# --- JS-parity formatting primitives -------------------------------------------------------
def test_js_number_formatting() -> None:
    assert _js_num(6.0) == "6"  # JS `${6}` — integral floats print bare
    assert _js_num(0.2) == "0.2"
    assert _js_num(_js_round(0.128, 1)) == "0.1"
    assert _js_num(_js_round(347.9)) == "348"
    assert _js_round(2.5) == 3.0  # Math.round half-up, not banker's
    assert _js_to_fixed(5.64, 2) == "5.64"
    assert _js_to_fixed(0.25, 1) == "0.3"  # toFixed on the exact binary value
    # A ratio below 0.05 keeps two significant figures instead of flattening to "0.0x" (#1265).
    # These are the network's two real dilution ratios: Lima's tightest chronic screen and
    # Findlay's. Both published as "0.0x" before the vanish-guard, which reads as *no dilution
    # problem* rather than as the two most effluent-dominated reaches on the network.
    assert _fmt_mult(0.04308778944) == "0.043\u00d7"
    assert _fmt_mult(0.006987209098378379) == "0.0070\u00d7"
    assert _fmt_mult(0.0090484357824) == "0.0090\u00d7"
    # The sub-1 rule widened in #1267, and `_fmt_mult` shares it: a ratio in [0.05, 1) now keeps
    # two significant figures too. The ratio case wanted that already by the argument above.
    assert _fmt_mult(0.42010594704) == "0.42\u00d7"
    assert _fmt_mult(2.2159434569142853) == "2.2\u00d7"
    assert _fmt_mult(12.4) == "12\u00d7"
    assert _fmt_ranged(4.9, None, None, 1) == "4.9"
    assert _fmt_ranged(250.0, 200.0, 300.0, 1) == "250 ± ~50"  # symmetric band → ±
    assert _fmt_ranged(250.0, 240.0, 300.0, 1) == "250 (240\u2013300)"  # asymmetric → range


# --- serialization: the exact camelCase shape the frontend renders verbatim ----------------
def test_model_serializes_with_the_frontend_field_names() -> None:
    by = _build({}, {}, facility_domain="absent")
    row = by["project"].model_dump(mode="json", by_alias=True)
    assert set(row) == {"chapter", "facility_key", "lead_ids", "model"}
    model = row["model"]
    assert {"id", "facilityKey", "status", "statusReasons", "stats", "gaps", "caveats"} <= set(
        model
    )
    gap = model["gaps"][0]
    assert {"wouldScreen", "missingRecord", "producer"} <= set(gap)
    # Plain JSON round-trip — the model IS the frontend's `StudyChapterModel`.
    assert json.loads(json.dumps(row)) == row


# --- integration: the real Lima bundle -----------------------------------------------------
# `lima_bundle` is conftest's session-wide, cross-worker export (#1773) — this module reads
# one feed off it, so it must never pay for an export of its own.
def _impact_study(bundle: Path) -> list[dict[str, Any]]:
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    ref = next(f for f in manifest["feeds"] if f["name"] == "impact-study")
    assert ref["kind"] == "collection"
    return cast(
        "list[dict[str, Any]]", json.loads((bundle / ref["path"]).read_text(encoding="utf-8"))
    )


def test_feed_emitted_at_contract_version(lima_bundle: Path) -> None:
    manifest = json.loads((lima_bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["contract_version"] == _CV
    rows = _impact_study(lima_bundle)
    assert [r["chapter"] for r in rows] == _CHAPTER_IDS


def test_lima_reads_data_dominant_with_fiscal_the_one_gap(lima_bundle: Path) -> None:
    rows = _impact_study(lima_bundle)
    statuses = {r["chapter"]: r["model"]["status"] for r in rows}
    assert statuses["fiscal"] == "gap"
    # The two corpus-keyed chapters (#1969) read `data` on the reference build: Lima's records
    # feed carries 6 `deeds` rows and a `local-legislation` row beside 46 meetings.
    assert statuses["assembly"] == "data"
    assert statuses["governance"] == "data"
    assert sum(1 for s in statuses.values() if s == "data") == 14
    # The reference build's rows are facility-keyed to the primary campus.
    assert {r["facility_key"] for r in rows} == {"project-bosc"}
    assert all(r["model"]["facilityKey"] == r["facility_key"] for r in rows)


def test_lima_fiscal_gap_carries_the_curated_joins(lima_bundle: Path) -> None:
    rows = _impact_study(lima_bundle)
    fiscal = next(r for r in rows if r["chapter"] == "fiscal")
    assert fiscal["lead_ids"] == ["PRR-04", "GH-35"]
    assert fiscal["model"]["gaps"][0]["leadIds"] == ["PRR-04", "GH-35"]


def test_a_real_figure_never_renders_as_zero() -> None:
    """One decimal at or above 1, two significant figures below — the peer of `statDecimals`.

    Two findings shaped this, and both are about a design low flow being a sub-1 number that one
    decimal cannot carry.

    A value that VANISHED (#1995): Sidney's contracted cooling draw is 0.0146 cfs (3.44M gal/yr,
    stated in an executed service agreement) and its headline stat read "0 cfs", which a reader
    takes as *no draw* rather than *a very small one*.

    A value that merely SHIFTED (#1267), live in three committed bundles: Van Wert's Town Creek
    7Q10 is 0.16 cfs and published as "0.2" — off by 25% on the denominator its whole
    effluent-dominance finding rests on. It never rounded to zero, so the first guard never fired.

    Hence one rule for the whole sub-1 range rather than a patch per symptom. Four committed
    stats moved when this landed, three of them the receiving low flow itself.
    """
    assert _stat_decimals(24.0) == 1
    assert _stat_decimals(1.0) == 1
    assert _stat_decimals(6.19) == 1  # Van Wert's design discharge
    # Below 1, two significant figures (#1267). The old rule only caught a value that ROUNDED TO
    # ZERO, so Van Wert's 0.16 cfs Town Creek 7Q10 published as "0.2" — off by 25% on the
    # denominator its whole effluent-dominance finding rests on. Findlay's 0.21 shifted the same way.
    assert _stat_decimals(0.16) == 2  # Van Wert — the case that forced the widening
    assert _stat_decimals(0.21) == 2  # Findlay
    assert _stat_decimals(0.2) == 2
    # Two SIGNIFICANT FIGURES, not two decimals: the count tracks the leading zeros, so a value an
    # order of magnitude smaller gets an order of magnitude more places ("0.050").
    assert _stat_decimals(0.05) == 3
    assert _stat_decimals(0.0) == 1  # a real zero stays a zero
    assert _stat_decimals(None) == 1
    assert _stat_decimals(0.0146) == 3
    assert _stat_decimals(-0.0146) == 3
    assert _stat_decimals(0.00061) == 5
    assert _fmt_ranged(0.0146, None, None, _stat_decimals(0.0146), "cfs") == "0.015 cfs"
    assert _fmt_ranged(4.85, None, None, _stat_decimals(4.85), "cfs") == "4.9 cfs"
