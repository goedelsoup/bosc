"""Independent cooling corroborators — air-permit PM + Tier II chemistry (#1680, A4 of #1676).

The properties under test: the air-permit corroborator reads a REAL committed permit (Lima's
lists 36 cooling towers as PM sources) and reconciles it against the claimed archetype — the same
listing CORROBORATES an evaporative claim and CONTRADICTS a dry one; a permit with no cooling-tower
PM is a cited absence; no permit is an [open] not-on-record seam. Tier II chemistry is a forward
seam (not-on-record for the live cohort). Everything is a SECONDARY corroborator — the classifier's
outcome is exercised in ``test_hydro_cooling_reconcile.py``.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from watermark.config import Settings
from watermark.hydrology import cooling_corroborators as cc
from watermark.sites import SITES, CoolingModelType, SiteFacility

# Lima's real, committed final air PTI (P0138965) — 36 non-contact cooling towers with drift
# eliminators, permitted as ~4.0 tpy PM10 / ~1.4 tpy PM2.5 sources. The one facility with an air
# permit on file today, so the air-permit corroborator has real-data coverage.
_LIMA_PERMIT_RELPATH = "permits/4132514.epa.yaml"


def _dry_facility(**kw: object) -> SiteFacility:
    base: dict[str, object] = {
        "name": "Test Dry Campus",
        "status": "confirmed",
        "it_load_mw": 150.0,
        "it_load_low_mw": 120.0,
        "it_load_high_mw": 180.0,
        "it_load_citation": "test",
        "it_load_source": "screening",
        "cooling_model": CoolingModelType.CLOSED_LOOP_DRY,
        "cooling_model_source": "reference",
        "cooling_model_citation": "[reference] closed-loop claim",
    }
    base.update(kw)
    return SiteFacility(**base)  # type: ignore[arg-type]


# --------------------------------------------------------------------- air permit (real data)


def test_lima_air_permit_lists_cooling_tower_pm_corroborates_its_evaporative_claim() -> None:
    # Lima's own facility (Shawnee Energy Campus, evaporative_tower) against its real air permit:
    # the 36 permitted cooling-tower PM units CORROBORATE the evaporative claim. Real-data coverage
    # of the reconciliation — "at least the cohort with air permits on file" (the acceptance).
    lima_fac = SITES["lima"].facilities[0]
    assert lima_fac.air_permit_relpath == _LIMA_PERMIT_RELPATH  # guard the fixture assumption
    sig = cc.air_permit_corroborator(lima_fac, settings=Settings())
    assert sig.state is cc.AirPermitState.PM_SOURCE_LISTED
    assert sig.stance is cc.CorroboratorStance.CORROBORATES  # a wet claim + a listed tower agree
    assert sig.tower_count == 36
    assert sig.pm10_tpy is not None and 3.5 <= sig.pm10_tpy <= 4.5  # ~4.0 tpy, approx marker parsed
    assert sig.tag == "[verified]"  # an on-record air-permit fact
    assert "P0138965" in sig.citation
    # The permit states ~4.0 tpy PM10 (approximate) — the ``~`` marker must be preserved, not dropped.
    assert "~4 tpy PM10" in sig.citation


def test_same_cooling_tower_pm_listing_contradicts_a_dry_claim() -> None:
    # The reconciliation direction flips with the CLAIM: the identical real permit (36 cooling
    # towers as PM sources) CONTRADICTS a closed_loop_dry claim — a dry loop is not a permitted PM
    # source. The heart of the air-permit corroborator.
    dry = _dry_facility(air_permit_relpath=_LIMA_PERMIT_RELPATH)
    sig = cc.air_permit_corroborator(dry, settings=Settings())
    assert sig.state is cc.AirPermitState.PM_SOURCE_LISTED
    assert sig.stance is cc.CorroboratorStance.CONTRADICTS
    assert sig.tag == "[verified]"
    assert "documentary contradiction" in sig.finding
    # Corroborating only — the finding says so (never the sole basis for a re-archetype).
    assert "not itself the [verified] instrument" in sig.finding


def test_no_air_permit_on_file_is_not_on_record_and_silent() -> None:
    sig = cc.air_permit_corroborator(_dry_facility(), settings=Settings())
    assert sig.state is cc.AirPermitState.NOT_ON_RECORD
    assert sig.stance is cc.CorroboratorStance.SILENT
    assert sig.tag == "[open]"  # a seam, never read as "no cooling tower"
    assert sig.tower_count is None
    assert "never read as 'no cooling tower'" in sig.finding


def test_air_permit_without_a_cooling_tower_block_is_a_cited_absence(tmp_path: Path) -> None:
    # A permit on file that lists NO cooling-tower PM unit is a [verified] absence — corroborates a
    # dry claim (its mirror is: it would contradict a wet claim). Uses a synthetic extraction under
    # an overridden data_dir so the read path is exercised without a fabricated commit.
    permit = tmp_path / "extracted" / "permits" / "no-towers.epa.yaml"
    permit.parent.mkdir(parents=True)
    permit.write_text(
        yaml.safe_dump({"action": {"permit_no": "P-NOTOWERS", "emission_unit_groups": {}}}),
        encoding="utf-8",
    )
    settings = Settings(data_dir=tmp_path)
    dry = _dry_facility(air_permit_relpath="permits/no-towers.epa.yaml")
    sig = cc.air_permit_corroborator(dry, settings=settings)
    assert sig.state is cc.AirPermitState.NO_PM_SOURCE
    assert sig.stance is cc.CorroboratorStance.CORROBORATES  # a dry claim + no tower agree
    assert sig.tag == "[verified]"
    assert "P-NOTOWERS" in sig.finding


def test_exact_permit_pm_figure_is_not_marked_approximate(tmp_path: Path) -> None:
    # A permit that states an EXACT cooling-tower PM10 (no ``~``) must not gain a fabricated
    # approximation marker — the inverse of the repo's approx-marker discipline (preserve ``~``
    # where the source had it; never invent it). The regression for the display-provenance fix.
    permit = tmp_path / "extracted" / "permits" / "exact-pm.epa.yaml"
    permit.parent.mkdir(parents=True)
    permit.write_text(
        yaml.safe_dump(
            {
                "action": {
                    "permit_no": "P-EXACT",
                    "emission_unit_groups": {"cooling_towers": {"count": 12}},
                    "cooling_tower_limits": {"combined_pm10_tpy": 5.0},  # EXACT, no ~
                }
            }
        ),
        encoding="utf-8",
    )
    settings = Settings(data_dir=tmp_path)
    wet = _dry_facility(
        air_permit_relpath="permits/exact-pm.epa.yaml",
        cooling_model=CoolingModelType.EVAPORATIVE_TOWER,
        cooling_model_citation="[reference] evaporative claim",
    )
    sig = cc.air_permit_corroborator(wet, settings=settings)
    assert sig.state is cc.AirPermitState.PM_SOURCE_LISTED
    assert sig.pm10_tpy == 5.0
    assert "5 tpy PM10" in sig.citation  # the exact figure appears...
    assert "~5" not in sig.citation  # ...unmarked — no fabricated approximation


# --------------------------------------------------------------------- Tier II (forward seam)


def test_tier2_chemistry_is_a_forward_seam_not_on_record() -> None:
    sig = cc.tier2_chemistry_corroborator(_dry_facility(), settings=Settings())
    assert sig.state is cc.TierIIState.NOT_ON_RECORD
    assert sig.stance is cc.CorroboratorStance.SILENT
    assert sig.tag == "[open]"
    assert sig.chemicals == []
    assert "records-request item" in sig.finding


# --------------------------------------------------------------------- combined


def test_resolve_corroborators_combines_and_a_contradiction_dominates_net_stance() -> None:
    # A dry claim with the real cooling-tower-PM permit: air contradicts, Tier II silent → the net
    # stance is CONTRADICTS (a single contradiction dominates a silent signal).
    dry = _dry_facility(air_permit_relpath=_LIMA_PERMIT_RELPATH)
    combined = cc.resolve_corroborators(dry, settings=Settings())
    assert combined.air_permit.stance is cc.CorroboratorStance.CONTRADICTS
    assert combined.tier2_chemistry.stance is cc.CorroboratorStance.SILENT
    assert combined.net_stance is cc.CorroboratorStance.CONTRADICTS
    assert "contradict" in combined.summary


def test_resolve_corroborators_all_silent_when_nothing_on_record() -> None:
    combined = cc.resolve_corroborators(_dry_facility(), settings=Settings())
    assert combined.net_stance is cc.CorroboratorStance.SILENT
    assert "Neither corroborator is on record" in combined.summary
