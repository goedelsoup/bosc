"""Curated receiving-water overlay (#1698) — the non-destructive ECHO refresh path.

The regression this guards: a raw `watermark npdes --basin maumee` re-pull used to clobber
the hand-edited receiving waters for Lima WWTP and Van Wert WWTP, dropping both back to
`no_receiving_water` and taking the basin's two starkest effluent-dominance findings with
them. The overlay must survive a re-pull, and must REFUSE the write rather than silently
override ECHO when it has moved.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from watermark.config import Settings
from watermark.hydrology.connectors import echo, echo_curation

from .conftest import REPO_ROOT

# The Auglaize (04100007) is where every committed Maumee correction lives.
_HUC = "04100007"
_OTHER_HUC = "04100008"


def _facility(**over: Any) -> echo.Facility:
    """A minimal ECHO row: everything null but identity, as ECHO actually returns it."""
    base: dict[str, Any] = {
        "name": "LIMA WWTP",
        "frs_registry_id": "110000760659",
        "npdes_id": "OH0026069",
        "npdes_ids_all": "OH0026069",
        "facility_type": "POTW",
        "facility_type_code": None,
        "permit_type": "NPDES Individual Permit",
        "design_flow_mgd": 18.5,
        "receiving_water": None,
        "huc8": _HUC,
        "huc12": None,
        "latitude": None,
        "longitude": None,
        "county": "ALLEN",
        "federal_agency": None,
        "compliance_status": None,
        "informal_enf_count": None,
        "formal_enf_count": None,
        "queried_huc8": _HUC,
    }
    return echo.Facility(**{**base, **over})


def _overlay_doc(**over: Any) -> dict[str, Any]:
    correction: dict[str, Any] = {
        "npdes_id": "OH0026069",
        "frs_registry_id": "110000760659",
        "facility": "LIMA WWTP",
        "huc8": _HUC,
        "receiving_water": "Ottawa River",
        "echo_value": None,
        "mode": "field",
        "issue": 1536,
        "citation": "Ohio EPA NPDES permit 2PE00000*OD cover page",
        "caveat": "receiving_water was null for OH0026069 in ECHO; corrected per permit.",
    }
    return {
        "meta": {
            "subject": "test overlay",
            "basin": "maumee",
            "rationale": "test",
        },
        "corrections": [{**correction, **over}],
    }


def _settings_with(tmp_path: Path, doc: dict[str, Any] | None) -> Settings:
    """Settings rooted at a tmp data dir, optionally carrying a Maumee overlay."""
    if doc is not None:
        path = tmp_path / "reference" / "echo" / "curation" / "maumee-wwtp.receiving-water.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return Settings(data_dir=tmp_path)


# --- the committed Maumee overlay -----------------------------------------------------


def test_committed_overlay_survives_a_repull() -> None:
    """The whole point: a fresh pull carrying ECHO's nulls still emits the curated water."""
    settings = Settings(data_dir=REPO_ROOT / "data")
    facilities = [
        _facility(),
        _facility(
            name="VAN WERT WWTP",
            frs_registry_id="110006645176",
            npdes_id="OH0027910",
            npdes_ids_all="OH0027910",
            design_flow_mgd=4.0,
            county="VAN WERT",
        ),
        _facility(
            name="CITY OF VAN WERT",
            frs_registry_id="110008587421",
            npdes_id="OH0135569",
            npdes_ids_all="OH0135569",
            facility_type="NON-POTW",
            design_flow_mgd=None,
            county="VAN WERT",
        ),
    ]
    curation = echo_curation.curate(facilities, echo.MAUMEE, settings=settings)
    outcomes = {a.correction.npdes_id: a.outcome for a in curation.applied}
    assert outcomes == {
        "OH0026069": "applied",
        "OH0027910": "applied",
        "OH0135569": "documented",
    }
    # `field` corrections land on the model, so the connector's derived flags follow.
    assert facilities[0].receiving_water == "Ottawa River"
    assert facilities[1].receiving_water == "Town Creek"
    # The `caveat` correction leaves ECHO's value strictly alone (#379).
    assert facilities[2].receiving_water is None


def test_committed_inventory_carries_the_curated_provenance() -> None:
    """The committed refresh output advertises the curation instead of hiding it."""
    potw = yaml.safe_load(
        (REPO_ROOT / "data" / "reference" / "echo" / "maumee-wwtp.potw.yaml").read_text()
    )
    lima = next(f for f in potw["facilities"] if f["npdes_id"] == "OH0026069")
    assert lima["receiving_water"] == "Ottawa River"
    assert lima["receiving_water_source"] == "curated"
    assert lima["receiving_water_echo"] is None  # ECHO's own value, preserved verbatim
    assert "2PE00000" in lima["receiving_water_citation"]
    assert lima["ottawa_discharge"] is True  # derived from the curated value

    block = potw["meta"]["receiving_water_curation"]
    assert block["overlay"] == "reference/echo/curation/maumee-wwtp.receiving-water.yaml"
    # The POTW-only file must not advertise the non-POTW OH0135569 correction it lacks.
    assert {c["npdes_id"] for c in block["corrections"]} == {"OH0026069", "OH0027910"}

    all_doc = yaml.safe_load(
        (REPO_ROOT / "data" / "reference" / "echo" / "maumee-wwtp.all-npdes.yaml").read_text()
    )
    wtp = next(f for f in all_doc["facilities"] if f["npdes_id"] == "OH0135569")
    assert wtp["receiving_water"] is None  # `mode: caveat` — the field still mirrors ECHO
    assert wtp["receiving_water_documented"] == "LOWER TOWN CREEK"


# --- outcomes -------------------------------------------------------------------------


def test_absent_overlay_is_not_an_error(tmp_path: Path) -> None:
    # Most basins have nothing to correct; that must pull exactly as before.
    curation = echo_curation.curate(
        [_facility()], echo.MAUMEE, settings=_settings_with(tmp_path, None)
    )
    assert curation.relpath is None and curation.applied == []


def test_conflict_refuses_the_write(tmp_path: Path) -> None:
    # ECHO now names a DIFFERENT water than the reviewed document. Overriding that
    # silently would bury a real disagreement, so the pull must stop.
    settings = _settings_with(tmp_path, _overlay_doc())
    fac = _facility(receiving_water="AUGLAIZE RIVER")
    with pytest.raises(echo_curation.CurationError, match="conflict"):
        echo_curation.curate([fac], echo.MAUMEE, settings=settings)
    assert fac.receiving_water == "AUGLAIZE RIVER"  # untouched


def test_superseded_defers_to_echo(tmp_path: Path) -> None:
    # ECHO caught up and supplies the same water: the entry is redundant, not wrong.
    settings = _settings_with(tmp_path, _overlay_doc())
    fac = _facility(receiving_water="ottawa  river")  # matched case/whitespace-insensitively
    curation = echo_curation.curate([fac], echo.MAUMEE, settings=settings)
    assert [a.outcome for a in curation.applied] == ["superseded"]
    assert fac.receiving_water == "ottawa  river"  # ECHO's own value stands
    assert curation.by_frs() == {}  # so the row carries no curation provenance


def test_stale_entry_refuses_the_write(tmp_path: Path) -> None:
    # The facility is gone from a pull that DID cover its subbasin — a terminated or
    # re-keyed permit is a reviewable event, not a silent drop.
    settings = _settings_with(tmp_path, _overlay_doc())
    other = _facility(frs_registry_id="999", npdes_id="OH9999999", npdes_ids_all="OH9999999")
    with pytest.raises(echo_curation.CurationError, match="stale"):
        echo_curation.curate([other], echo.MAUMEE, settings=settings)


def test_out_of_scope_pull_is_not_stale(tmp_path: Path) -> None:
    # A single-HUC pull must not be blocked by corrections belonging to other subbasins.
    settings = _settings_with(tmp_path, _overlay_doc())
    elsewhere = _facility(
        frs_registry_id="999",
        npdes_id="OH9999999",
        npdes_ids_all="OH9999999",
        huc8=_OTHER_HUC,
        queried_huc8=_OTHER_HUC,
    )
    curation = echo_curation.curate([elsewhere], echo.MAUMEE, settings=settings)
    assert [a.outcome for a in curation.applied] == ["out_of_scope"]
    assert curation.by_frs() == {}


def test_renamed_facility_still_matches(tmp_path: Path) -> None:
    # ECHO renames facilities routinely ("SHAWNEE NO 2 WWTP" -> "SHAWNEE II WWTP"); the FRS
    # id is the identity assertion, so a rename must not fail the pull.
    settings = _settings_with(tmp_path, _overlay_doc())
    fac = _facility(name="CITY OF LIMA WASTEWATER TREATMENT PLANT")
    curation = echo_curation.curate([fac], echo.MAUMEE, settings=settings)
    assert [a.outcome for a in curation.applied] == ["applied"]
    assert fac.receiving_water == "Ottawa River"


def test_overlay_declaring_another_basin_is_rejected(tmp_path: Path) -> None:
    # A misfiled overlay would attach a citation to the wrong facility.
    doc = _overlay_doc()
    doc["meta"]["basin"] = "scioto"
    with pytest.raises(echo_curation.CurationError, match="declares basin"):
        echo_curation.load_overlay(echo.MAUMEE, settings=_settings_with(tmp_path, doc))


# --- end-to-end through the writer ----------------------------------------------------


def _huc_result(facilities: list[echo.Facility]) -> echo.HucResult:
    return echo.HucResult(
        huc8=_HUC,
        name="Auglaize",
        query_id="1",
        reported_count=len(facilities),
        stats={},
        facilities=facilities,
    )


def test_write_inventory_emits_curation(tmp_path: Path) -> None:
    out = tmp_path / "out"
    settings = _settings_with(tmp_path, _overlay_doc())
    paths = echo.write_inventory(
        [_huc_result([_facility()])], out, basin=echo.MAUMEE, settings=settings
    )
    doc = yaml.safe_load(paths["potw"].read_text())
    row = doc["facilities"][0]
    assert row["receiving_water"] == "Ottawa River"
    assert row["receiving_water_source"] == "curated"
    assert row["ottawa_discharge"] is True
    # The reviewed prose rides on the overlay entry, not on hand-edited output.
    assert _overlay_doc()["corrections"][0]["caveat"] in doc["meta"]["caveats"]
    assert doc["meta"]["receiving_water_curation"]["corrections"][0]["outcome"] == "applied"


def test_write_inventory_refuses_on_conflict(tmp_path: Path) -> None:
    # Nothing may be written when the overlay doesn't reconcile — a half-reviewed
    # inventory is worse than no refresh at all.
    out = tmp_path / "out"
    settings = _settings_with(tmp_path, _overlay_doc())
    results = [_huc_result([_facility(receiving_water="AUGLAIZE RIVER")])]
    with pytest.raises(echo_curation.CurationError):
        echo.write_inventory(results, out, basin=echo.MAUMEE, settings=settings)
    assert not out.exists()


def test_caveat_mode_records_without_touching_the_field(tmp_path: Path) -> None:
    settings = _settings_with(tmp_path, _overlay_doc(mode="caveat"))
    paths = echo.write_inventory(
        [_huc_result([_facility()])], tmp_path / "out", basin=echo.MAUMEE, settings=settings
    )
    row = yaml.safe_load(paths["potw"].read_text())["facilities"][0]
    assert row["receiving_water"] is None  # ECHO's value, verbatim
    assert row["receiving_water_documented"] == "Ottawa River"
    assert row["ottawa_discharge"] is False  # the derived flag follows ECHO, not the note
