"""Basin-wide low-flow assimilative screen over the ECHO Maumee POTW inventory.

Hermetic: the screen reads only committed reference data (the cited + derived 7Q10
tables and the ECHO POTW inventory) — no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.hydrology import basin

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def data_settings() -> Settings:
    return Settings(data_dir=REPO_ROOT / "data")


def test_derived_low_flows_loaded(data_settings: Settings) -> None:
    derived = basin.load_derived_low_flows(settings=data_settings)
    maumee = derived[basin._norm("maumee river")]
    assert maumee.source == "derived"
    assert maumee.unit == "cfs"
    assert maumee.value == pytest.approx(114.15, abs=0.5)  # USGS 04193500 LP3 7Q10
    # Every St. Joseph surface form resolves to the same derived value.
    sj = {basin._norm(a) for a in ("st joseph river", "st joseph r", "st. joseph river")}
    assert sj <= set(derived)
    assert len({derived[k].value for k in sj}) == 1


def test_basin_screen_coverage(data_settings: Settings) -> None:
    screen = basin.check_basin_assimilative(settings=data_settings)
    c = screen.coverage
    # 130 since the #1698 whole-basin refresh: ECHO added Toledo Bay View Park WWTP
    # (OH0027740) to the Lower Maumee POTW set.
    assert c.total == 130
    # 9 since #1536: the Lima WWTP (OH0026069) now carries a document-cited receiving
    # water (Ottawa River, from permit 2PE00000), so it moves out of no_receiving_water
    # and screens (28.62 cfs into the Ottawa's 0.2 cfs 7Q10 — a fresh violation). The
    # curated receiving-water overlay re-applies that correction (and Van Wert's) on every
    # pull, so a refresh can no longer silently drop either back to no_receiving_water.
    assert c.screened == len(screen.checks) == 9
    # Honest coverage: most of the basin is unscreenable, surfaced explicitly. 77 after the
    # refresh — ECHO dropped the receiving water it used to carry for Harrison Lake State
    # Park (re-keyed to a general permit) and Miller City HS, and the new Toledo row has none.
    assert c.no_receiving_water == 77
    assert c.screened + c.no_receiving_water + c.no_7q10 + c.no_design_flow == c.total
    # The cited Lima-loop violation (American Bath -> Pike Run) is still caught.
    cited = [ch for ch in screen.checks if ch.design_low_flow.source == "document"]
    assert any("PIKE RUN" in ch.receiving_water.upper() for ch in cited)
    assert c.violations >= 1
    # Major mainstem dischargers now screen via derived 7Q10 (e.g. Defiance -> Maumee).
    derived = [ch for ch in screen.checks if ch.design_low_flow.source == "derived"]
    assert len(derived) >= 5
    assert all(ch.discharge.source == "reference" for ch in screen.checks)


def test_great_miami_mainstems_derived(data_settings: Settings) -> None:
    # The Great Miami basin's mainstem 7Q10s share the one derived table, keyed by name.
    derived = basin.load_derived_low_flows(settings=data_settings)
    mad = derived[basin._norm("mad river")]
    assert mad.source == "derived"
    assert mad.value == pytest.approx(166.55, abs=0.5)  # USGS 03269500 (Springfield reach) LP3 7Q10
    gm = derived[basin._norm("great miami river")]
    assert gm.value == pytest.approx(407.67, abs=0.5)  # USGS 03274000 (Hamilton, mouth-ward)


def test_scioto_mainstems_derived(data_settings: Settings) -> None:
    # The Scioto basin's mainstem 7Q10s share the one derived table, keyed by name.
    derived = basin.load_derived_low_flows(settings=data_settings)
    scioto = derived[basin._norm("scioto river")]
    assert scioto.source == "derived"
    assert scioto.value == pytest.approx(
        515.73, abs=1.0
    )  # USGS 03234500 (Higby, mouth-ward) LP3 7Q10
    bw = derived[basin._norm("big walnut creek")]
    assert bw.value == pytest.approx(
        35.43, abs=0.5
    )  # USGS 03229500 (Rees) — the New Albany receiving water
    assert derived[basin._norm("olentangy river")].value == pytest.approx(13.53, abs=0.5)


def test_basin_screen_follows_active_basin(data_settings: Settings) -> None:
    # A Great Miami site screens the Great Miami inventory, never the Maumee one.
    springfield = Settings(data_dir=REPO_ROOT / "data", site="springfield")
    screen = basin.check_basin_assimilative(settings=springfield)
    c = screen.coverage
    assert c.total == 81  # the committed great-miami POTW inventory
    assert c.screened == len(screen.checks) == 18
    assert c.screened + c.no_receiving_water + c.no_7q10 + c.no_design_flow == c.total
    # Screened denominators are Great Miami basin streams only — no Maumee stream leaks in.
    # Greenville Creek + Stillwater River added when Darke County gages (03264000/03265000)
    # were registered in _MAINSTEM_GAGES (#512). Loramie Creek added for Sidney onboarding
    # (#508), enabling Botkins WWTP (OH0022217) to be screened against the Lockington gage.
    # (Normalize whitespace: ECHO uses "Mad  River".)
    waters = {" ".join(ch.receiving_water.upper().split()) for ch in screen.checks}
    assert waters <= {
        "MAD RIVER",
        "GREAT MIAMI RIVER",
        "GREENVILLE CREEK",
        "STILLWATER RIVER",
        "LORAMIE CREEK",
    }
    assert all(ch.design_low_flow.source == "derived" for ch in screen.checks)
    # The City of Springfield WWTP is in the inventory but ECHO has no receiving water for it,
    # so it is reported unscreened (omit, don't guess) — not silently dropped.
    assert c.no_receiving_water >= 1


def test_headwaters_confluence_derived(data_settings: Settings) -> None:
    # The synthesized Maumee-at-Fort-Wayne 7Q10 (#358) = St. Joseph-near-FW + St. Marys-near-FW.
    derived = basin.load_derived_low_flows(settings=data_settings)
    hw = derived[basin._norm("maumee river at fort wayne")]
    assert hw.source == "derived"
    assert hw.confidence == "low"  # sum-of-tributaries is a conservative inference
    assert hw.value == pytest.approx(69.71, abs=0.5)  # 04180500 (54.06) + 04182000 (15.65)
    # All point-specific aliases resolve to the same value...
    for alias in (
        "maumee river at fort wayne",
        "maumee river (fort wayne headwaters)",
        "maumee river headwaters",
    ):
        assert derived[basin._norm(alias)].value == pytest.approx(69.71, abs=0.5)
    # ...and the bare "maumee river" is UNCHANGED — still the lower-basin Waterville proxy,
    # not shadowed by the Fort Wayne headwaters value.
    assert derived[basin._norm("maumee river")].value == pytest.approx(114.15, abs=0.5)


def test_fort_wayne_wwtp_unscreened_by_discipline(data_settings: Settings) -> None:
    # The Fort Wayne WWTP discharges to "Baldwin Ditch, Maumee R …"; its PRIMARY receiver is an
    # ungaged ditch, so it is correctly left unscreened (omit, don't guess) — the headwaters 7Q10
    # is a documented at-mainstem proxy, never auto-credited to a Baldwin Ditch discharger.
    lookup = basin.load_derived_low_flows(settings=data_settings)
    fac = {
        "name": "FORT WAYNE WWTP",
        "npdes_id": "IN0032191",
        "receiving_water": "BALDWIN DITCH, MAUMEE R TO ST MARYS RIVER, MAUMEE RIVER",
        "design_flow_mgd": 74.0,
    }
    check, status = basin.screen_facility(fac, lookup)
    assert check is None
    assert status == "no_7q10"


def test_screen_omits_tributary_compounds(data_settings: Settings) -> None:
    # A discharger whose PRIMARY receiver is a ditch must not borrow a downstream
    # mainstem's larger 7Q10 (that would overstate dilution). Omit, don't guess.
    lookup = basin.load_derived_low_flows(settings=data_settings)
    assert basin._match_low_flow("Baldwin Ditch, Maumee River", lookup) is None
    assert basin._match_low_flow("Maumee River", lookup) is not None
    # The St. Joseph typo/synonym compound still matches on its primary form.
    assert basin._match_low_flow("ST JOSEPH R, ST JOSEPH RIVER", lookup) is not None


def test_gage_schema_rejects_malformed_reference_data() -> None:
    # The curated gage table is schema-validated at load, so a YAML edit that guts a
    # gage/confluence fails fast rather than screening against silently-wrong data.
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        basin.MainstemGage.model_validate({"gage": "04193500", "aliases": []})  # no alias
    with pytest.raises(ValidationError):
        basin.MainstemGage.model_validate({"gaeg": "04193500", "aliases": ["x"]})  # typo key
    with pytest.raises(ValidationError):
        # a confluence reduced to a single tributary is meaningless
        basin.HeadwatersConfluence.model_validate(
            {"components": [{"gage": "04180500", "label": "St. Joseph"}], "aliases": ["x"]}
        )
    with pytest.raises(ValidationError):
        # a top-level table missing the mainstems section is not a silently-empty screen
        basin._GageTable.model_validate({"headwaters_confluences": {}})


def test_gage_table_rejects_empty_sections() -> None:
    # A truncated mainstem-gages.yaml that keeps the keys but empties a section must fail
    # fast, not load into a silently-partial (or empty) basin screen.
    from pydantic import ValidationError

    good_main = {"maumee river": {"gage": "04193500", "aliases": ["maumee river"]}}
    good_conf = {
        "maumee headwaters": {
            "components": [
                {"gage": "04180500", "label": "St. Joseph"},
                {"gage": "04182000", "label": "St. Marys"},
            ],
            "aliases": ["maumee river at fort wayne"],
        }
    }
    # A fully-populated table is accepted (the baseline for the negatives below).
    basin._GageTable.model_validate({"mainstems": good_main, "headwaters_confluences": good_conf})

    with pytest.raises(ValidationError):  # empty mainstems -> useless screen
        basin._GageTable.model_validate({"mainstems": {}, "headwaters_confluences": good_conf})
    with pytest.raises(ValidationError):  # empty confluences
        basin._GageTable.model_validate({"mainstems": good_main, "headwaters_confluences": {}})
    with pytest.raises(ValidationError):  # both empty
        basin._GageTable.model_validate({"mainstems": {}, "headwaters_confluences": {}})
