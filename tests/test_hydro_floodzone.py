"""FEMA floodzone connector + campus floodplain finding + dossier weave (hermetic)."""

from __future__ import annotations

from bosc.config import Settings
from bosc.hydrology.connectors import lima_gis
from bosc.hydrology.floodplain import load_campus_floodzone, load_wwtp_floodzones
from bosc.hydrology.report import render_report


def _footprint(settings: Settings):  # type: ignore[no-untyped-def]
    return settings.data_dir / "reference" / "periplus" / "bosc-parcels.geojson"


def test_floodzone_catalog(hydro_settings: Settings) -> None:
    cat = lima_gis.floodzone_catalog(settings=hydro_settings)
    assert sum(c.polygon_count for c in cat) == 368
    assert all(c.sfha for c in cat)  # only Special Flood Hazard Areas are mapped
    assert cat[0].fld_zone == "AE" and cat[0].polygon_count == 304  # largest class leads
    floodway = next(c for c in cat if c.zone_subtype == "FLOODWAY")
    assert floodway.fld_zone == "AE" and floodway.polygon_count == 31


def test_footprint_is_floodplain_adjacent_not_sited(hydro_settings: Settings) -> None:
    fp = _footprint(hydro_settings)
    # The recorded parcels intersect no SFHA polygon...
    assert lima_gis.footprint_floodzones(fp, distance_m=0, settings=hydro_settings) == []
    # ...but AE floodplain + floodway come within 50 m.
    nearby = lima_gis.footprint_floodzones(fp, distance_m=50, settings=hydro_settings)
    assert len(nearby) == 2
    assert {f.fld_zone for f in nearby} == {"AE"}
    assert any(f.zone_subtype == "FLOODWAY" for f in nearby)
    assert all(f.source_cit == "39003C_FIS5" for f in nearby)
    # The -9999 BFE sentinel is normalized to None, not surfaced as an elevation.
    assert all(f.static_bfe is None for f in nearby)


def test_campus_floodzone_finding_loads(hydro_settings: Settings) -> None:
    cf = load_campus_floodzone(settings=hydro_settings)
    assert cf is not None
    assert cf.in_parcels_zones == []
    assert cf.in_floodplain is False
    assert cf.nearby_zones == ["AE", "AE (FLOODWAY)"]
    assert cf.nearby_buffer_m == 50
    assert "39003C" in cf.firm


def test_point_floodzones_at_and_near_a_wwtp(hydro_settings: Settings) -> None:
    # American II (OH0037338): not in SFHA at its point, AE within 50 m, floodway by 150 m.
    assert lima_gis.point_floodzones(-84.17824, 40.78016, settings=hydro_settings) == []
    near = lima_gis.point_floodzones(-84.17824, 40.78016, distance_m=50, settings=hydro_settings)
    assert {f.fld_zone for f in near} == {"AE"}
    wider = lima_gis.point_floodzones(-84.17824, 40.78016, distance_m=150, settings=hydro_settings)
    assert any(f.zone_subtype == "FLOODWAY" for f in wider)
    # American-Bath (OH0023841) is clear: nothing within 50 m.
    assert (
        lima_gis.point_floodzones(-84.12803, 40.78226, distance_m=50, settings=hydro_settings) == []
    )


def test_load_wwtp_floodzones_finding(hydro_settings: Settings) -> None:
    wf = load_wwtp_floodzones(settings=hydro_settings)
    assert wf is not None
    by_npdes = {p.npdes: p for p in wf.plants}
    assert set(by_npdes) == {"OH0037338", "OH0023841", "OH0023850"}
    # None of the facility points is inside the SFHA.
    assert all(not p.in_sfha for p in wf.plants)
    am2 = by_npdes["OH0037338"]
    assert am2.nearest_buffer(contains="AE") == 50
    assert am2.nearest_buffer(contains="FLOODWAY") == 150
    bath = by_npdes["OH0023841"]
    assert bath.nearest_buffer(contains="AE") == 400  # well clear


def test_report_weaves_floodplain_proximity(hydro_settings: Settings) -> None:
    md = render_report(settings=hydro_settings)
    assert "just outside the FEMA floodplain" in md
    assert "AE (FLOODWAY)" in md
    assert "regulatory" in md and "floodway" in md
    # The WWTP-outfall flood-exposure table is woven into section 1.
    assert "Outfall flood exposure" in md
    assert "Nearest floodway" in md
