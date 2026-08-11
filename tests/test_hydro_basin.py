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
    # 10 since #1460 (closing #352): the Findlay WPCC (OH0025135, the Blanchard's 15 MGD
    # anchor POTW) gains its own overlay correction from NPDES fact sheet 2PD00008, so it
    # too leaves no_receiving_water and screens — a fourth violation.
    assert c.screened == len(screen.checks) == 10
    # Honest coverage: most of the basin is unscreenable, surfaced explicitly. 77 after the
    # #1698 refresh — ECHO dropped the receiving water it used to carry for Harrison Lake
    # State Park (re-keyed to a general permit) and Miller City HS, and the new Toledo row
    # has none; 76 after the Findlay correction moved one row out of the bucket.
    assert c.no_receiving_water == 76
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
    # 17 since #1120: the Hamilton WRF (OH0025445, 32 MGD) reads "GREAT MIAMI RIVER, TWO MILE
    # CREEK" in ECHO — two different waters, and nothing in ECHO says which carries the design
    # flow — so `_match_low_flow` refuses it instead of crediting the larger of the two.
    assert c.screened == len(screen.checks) == 17
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
    # Every denominator is the derived at-gage screening proxy EXCEPT the Sidney WWTP, which is
    # the basin's one permit-scoped cited value (#1992). Before it was bound, this line read
    # `all(... == "derived")` — which recorded that no cited Great Miami value existed, not that
    # none should. Sidney's outfall now resolves through `permits:` to Ohio EPA's own figure.
    by_source = {ch.discharger: ch.design_low_flow.source for ch in screen.checks}
    assert by_source["SIDNEY WWTP"] == "document"
    assert all(src == "derived" for name, src in by_source.items() if name != "SIDNEY WWTP")
    # And the cited value is the one the regulator computed AT that outfall — 24.0 cfs (fact
    # sheet 1PD00009, Table 14) against the 10.83 cfs design flow — not the 407.67 cfs derived
    # Hamilton mainstem proxy, which would have overstated available dilution by 17x and read
    # `ok` instead of `tight`. This is the #1458 failure mode; assert the band, not just the source.
    sidney = next(ch for ch in screen.checks if ch.discharger == "SIDNEY WWTP")
    assert sidney.design_low_flow.value == pytest.approx(24.0)
    assert sidney.dilution_ratio == pytest.approx(2.216, abs=0.01)
    assert sidney.flag == "tight"
    # The bare river name still belongs to the derived proxy — a permit-scoped value must never
    # leak into the name-keyed lookup every OTHER discharger on this river reads.
    assert basin.build_low_flow_lookup(settings=springfield)[
        basin._norm("great miami river")
    ].value == pytest.approx(407.67)
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
    # The Fort Wayne WWTP discharges to "Baldwin Ditch, Maumee R …" — an ungaged ditch AND a
    # gaged mainstem, with nothing in ECHO saying which carries the 74 MGD. It is correctly left
    # unscreened (omit, don't guess): the headwaters 7Q10 is a documented at-mainstem proxy,
    # never auto-credited to a Baldwin Ditch discharger.
    lookup = basin.ScreenLowFlows(by_name=basin.load_derived_low_flows(settings=data_settings))
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
    # A receiving water naming TWO different waters is refused, whichever order they are in:
    # ECHO's field is a permit-level aggregate over every outfall, so it does not say which
    # water carries the design flow, and crediting the larger would overstate dilution into a
    # false "ok". Reading only the first form made the guard an accident of list order (#1120).
    lookup = basin.load_derived_low_flows(settings=data_settings)
    assert basin._match_low_flow("Baldwin Ditch, Maumee River", lookup) is None
    assert basin._match_low_flow("Maumee River, Baldwin Ditch", lookup) is None
    assert basin._match_low_flow("Maumee River", lookup) is not None
    # One water under two surface forms still matches — but only because BOTH forms are
    # registered aliases of that gage, which is the only reviewed way to say they are one water.
    assert basin._match_low_flow("ST JOSEPH R, ST JOSEPH RIVER", lookup) is not None
    assert basin._match_low_flow("AUGLAIZE RIVER, AUGLAZE RIVER", lookup) is not None
    # An unregistered second form is, by construction, a second water.
    assert basin._match_low_flow("MAUMEE RIVER, MAUMEE RIVER (LOWER)", lookup) is None


def test_west_union_screens_the_ohio_brush_creek_inventory() -> None:
    # #1120: west-union is the first direct-to-Ohio site, screening HUC-8 05090201 — a two-bank
    # Ohio River corridor unit, not a watershed. Pinned because a typo in the basin slug, the
    # HUC-8 or the file_stem does not raise: `_inventory_path` falls back to a conventional name
    # and an absent file screens an empty set, silently reverting this to 0/0.
    west_union = Settings(data_dir=REPO_ROOT / "data", site="west-union")
    screen = basin.check_basin_assimilative(settings=west_union)
    c = screen.coverage
    assert c.total == 23  # the committed ohio-brush-creek POTW inventory
    assert c.screened == len(screen.checks) == 5
    assert c.no_receiving_water == 13  # ECHO carries no CWPStateWaterBodyName
    assert c.no_7q10 == 5
    assert c.no_design_flow == 0
    assert c.screened + c.no_receiving_water + c.no_7q10 + c.no_design_flow == c.total
    # Every screened row is on the Ohio River mainstem itself; no sibling tributary of Ohio
    # Brush Creek borrows a denominator it has no claim to.
    assert {ch.receiving_water.upper() for ch in screen.checks} == {"OHIO RIVER"}
    assert all(ch.flag == "ok" for ch in screen.checks)
    # New Richmond WWTP (OH0021156, 1.1 MGD) reads "OHIO RIVER, TWELVE MILE CREEK" — two waters,
    # so it is refused rather than credited with the Ohio's 9,463 cfs at 5,560:1.
    assert "NEW RICHMOND WWTP" not in {ch.discharger for ch in screen.checks}
    # The West Union WWTP itself is unscreened: ECHO has no receiving water for it.
    assert "WEST UNION WWTP" not in {ch.discharger for ch in screen.checks}


def test_ohio_river_denominator_is_scoped_to_its_own_basin(data_settings: Settings) -> None:
    # The Greenup Dam gage is conservative only for the HUC-8 whose river frontage lies below
    # it. "OHIO RIVER" is a receiving water in every Ohio tributary basin's inventory, at
    # reaches hundreds of river miles apart, so the entry declares `basins:` and the shared
    # derived table serves it to that basin alone (#1120).
    west_union = Settings(data_dir=REPO_ROOT / "data", site="west-union")
    ohio = basin.load_derived_low_flows(settings=west_union)[basin._norm("ohio river")]
    assert ohio.source == "derived"
    assert ohio.value == pytest.approx(9463.62, abs=1.0)  # USGS 03216600 LP3 7Q10
    # `data_settings` is Lima — a Maumee site, which must not see it at all.
    assert basin._norm("ohio river") not in basin.load_derived_low_flows(settings=data_settings)
    # An unscoped entry is still shared, so the scoping is opt-in, not a per-basin partition.
    assert basin._norm("maumee river") in basin.load_derived_low_flows(settings=data_settings)


def test_gage_note_reaches_the_file_the_screen_reads(data_settings: Settings) -> None:
    # A gage's note states why THIS gage and what the choice costs; the screen reads the derived
    # file, never the curated table, so the note is copied across with the cited blocks (#1120).
    import yaml as _yaml

    path = REPO_ROOT / "data" / "reference" / "hydrology" / "low-flow-7q10.derived.yaml"
    streams = _yaml.safe_load(path.read_text(encoding="utf-8"))["streams"]
    curated = basin.load_mainstem_gages(settings=data_settings)
    for river, spec in curated.items():
        if spec.note is None or river.lower() not in streams:
            continue
        assert streams[river.lower()]["note"] == spec.note
    assert "NAVIGATION-REGULATED" in streams["ohio river"]["note"]
    assert streams["ohio river"]["basins"] == ["ohio-brush-creek"]


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


# --- the cited denominator layer (#1458) -----------------------------------------------------
def test_fact_sheet_low_flow_is_permit_scoped_not_river_scoped(data_settings: Settings) -> None:
    """One river, two binding denominators — bound by permit, never by name.

    Ohio EPA computes the design low flow AT THE OUTFALL, so the Blanchard carries 0.21 cfs at
    Findlay's RM 56.42 and 7.78 cfs at Ottawa's RM 22.1. Name-keying cannot hold both (``_normalize``
    strips ``at …`` on purpose), and whichever won would silently become the other plant's
    denominator.
    """
    by_permit = basin.load_permit_low_flows(settings=data_settings)
    assert by_permit["oh0025135"].value == pytest.approx(0.21)
    assert by_permit["oh0026921"].value == pytest.approx(7.78)
    # The Ohio EPA permit number reaches the same entry, with its issuance suffix stripped: the
    # design low flow is a property of the outfall, not of which renewal is current.
    assert by_permit["2pd00008"].value == pytest.approx(0.21)
    assert basin.normalize_permit("2PD00008*VD") == "2pd00008"
    # Neither reach entry leaks into the name-keyed lookup as "blanchard river" — that key still
    # belongs to the derived at-gage proxy, which is what any OTHER Blanchard discharger gets.
    by_name = basin.build_low_flow_lookup(settings=data_settings)
    assert by_name[basin._norm("blanchard river")].source == "derived"


def test_findlay_screens_on_its_own_outfall_not_the_gage_below_it(data_settings: Settings) -> None:
    """The reconciliation itself (#1458), pinned end to end.

    USGS 04189000 sits DOWNSTREAM of outfall 2PD00008001, so screening the Findlay WPCC against
    its LP3 7Q10 put the plant's own effluent into its own denominator. The permit-scoped cited
    value must win, and the check must say so.
    """
    lookup = basin.build_screen_lookup(settings=data_settings)
    fac = {
        "name": "CITY OF FINDLAY WATER POLLUTION CONTROL CENTER",
        "npdes_id": "OH0025135",
        "receiving_water": "Blanchard River",
        "design_flow_mgd": 15.0,
    }
    check, status = basin.screen_facility(fac, lookup)
    assert status == "screened" and check is not None
    assert check.design_low_flow.value == pytest.approx(0.21)  # NOT the derived 8.67
    assert check.dilution_ratio == pytest.approx(0.009, abs=0.001)
    assert check.flag == "violation"
    assert "cited AT THIS OUTFALL" in check.detail
    # A different Blanchard discharger with no fact sheet of its own still falls back to the
    # derived proxy — the permit-scoped value is not a river-wide override.
    other = dict(fac, name="MILLER CITY HS WWTP", npdes_id="OH0126535")
    other_check, other_status = basin.screen_facility(other, lookup)
    assert other_status == "screened" and other_check is not None
    assert other_check.design_low_flow.value == pytest.approx(8.67, abs=0.01)


def test_regulated_gage_carries_its_caveat_into_the_committed_derived_entry(
    data_settings: Settings,
) -> None:
    """A demoted denominator has to SAY it is demoted, and survive the next regen saying it.

    The `published` / `regulation` / `cross_check_gages` blocks are authored in the curated
    ``mainstem-gages.yaml`` and copied forward by the derivation, so a hand-edit of the generated
    file would be reverted. This asserts the committed file matches what the emitter would produce
    **in both directions** — no annotation missing, none left over from an earlier curation that
    the reference table no longer declares — which is the property that makes those blocks
    trustworthy.
    """
    import yaml

    spec = basin.load_mainstem_gages(settings=data_settings)["Blanchard River"]
    assert spec.regulation is not None and spec.regulation.status == "regulated"
    assert "Findlay Reservoir" in (spec.regulation.remark or "")
    assert spec.published is not None and spec.published.seven_q10_cfs == pytest.approx(2.7)

    emitted = basin._cited_annotations(spec)
    assert emitted["confidence"] == "low"  # regulated ⇒ demoted from the default `medium`

    path = data_settings.reference_dir / "hydrology" / "low-flow-7q10.derived.yaml"
    committed = (yaml.safe_load(path.read_text(encoding="utf-8")) or {})["streams"][
        "blanchard river"
    ]
    # `confidence` is a base key the overlay REPLACES, so it is compared by value below rather
    # than counted here; the rest exist only because the curated table declares them.
    annotation_keys = {"published", "regulation", "cross_check_gages", "confidence_reason"}
    assert annotation_keys & committed.keys() == annotation_keys & emitted.keys(), (
        "committed derived entry has annotations mainstem-gages.yaml no longer declares "
        "(or is missing ones it does) — re-emit it through write_derived_low_flows"
    )
    for key, value in emitted.items():
        assert committed[key] == value, (
            f"committed derived entry drifted from mainstem-gages.yaml: {key}"
        )

    # The published counterweight and the unregulated cross-checks are what make the demotion
    # legible rather than an assertion: 0-0.03 cfs where the Blanchard is not regulated.
    unregulated = {
        g["gage"]: g["seven_q10_cfs"]
        for g in emitted["cross_check_gages"]
        if g.get("regulation") == "unregulated"
    }
    assert unregulated == {"04188337": 0.03, "04188496": 0.0}


def test_a_permit_cannot_have_two_design_low_flows(tmp_path: Path) -> None:
    # Two entries claiming one permit would make the screened denominator depend on YAML order.
    import yaml

    ref = tmp_path / "reference" / "hydrology"
    ref.mkdir(parents=True)
    (ref / "low-flow-7q10.yaml").write_text(
        yaml.safe_dump(
            {
                "streams": {
                    "a reach": {"seven_q10_cfs": 1.0, "permits": ["OH0000001"]},
                    "b reach": {"seven_q10_cfs": 2.0, "permits": ["OH0000001*UD"]},
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="claimed by two entries"):
        basin.load_permit_low_flows(settings=Settings(data_dir=tmp_path))
