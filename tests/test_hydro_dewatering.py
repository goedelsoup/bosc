"""Construction-dewatering cone-of-impact model over the committed campus wellfield (hermetic).

Runs on the reviewed ``data/reference/ohio-waterwells/lima-campus-dewatering.csv`` (44 wells) +
the Allen census; no network. Guards the wellfield reconciliation (43 sealed, 1 active), the
per-well cones, and the composite superposition onto nearby domestic wells.
"""

from __future__ import annotations

from datetime import date

from watermark.config import Settings
from watermark.hydrology import dewatering as dw

ASOF = date(2026, 7, 28)


def test_wellfield_loads_and_reconciles(hydro_settings: Settings) -> None:
    wells = dw.load_dewatering_wells(settings=hydro_settings)
    assert len(wells) == 44
    assert all((w.well_use or "").upper() == "DEWATERING" for w in wells)
    active = [w for w in wells if w.active]
    assert len(active) == 1 and active[0].record_no == "3027949"  # "all but one sealed"
    assert sum(1 for w in wells if not w.active) == 43


def test_well_geometry_and_operating_days(hydro_settings: Settings) -> None:
    wells = {w.record_no: w for w in dw.load_dewatering_wells(settings=hydro_settings)}
    a = wells["3027949"]  # active well, completed 2025-12-19
    assert a.saturated_thickness_ft is not None and a.saturated_thickness_ft > 0
    # Active -> operating days run to `asof`; a sealed well runs to its sealing date.
    assert a.operating_days(ASOF) == (ASOF - date(2025, 12, 19)).days
    sealed = next(w for w in wells.values() if not w.active)
    assert sealed.operating_days(ASOF) < a.operating_days(ASOF)


def test_well_cone_bracket_is_monotonic_in_k(hydro_settings: Settings) -> None:
    wells = {w.record_no: w for w in dw.load_dewatering_wells(settings=hydro_settings)}
    cone = dw.well_cone(wells["3027949"], asof=ASOF, settings=hydro_settings)
    assert cone is not None
    r0 = cone.radius_of_influence_ft
    # r0 ~ sqrt(K), so the influence radius is monotonic in the K bracket.
    assert r0.low is not None and r0.high is not None and r0.low < r0.value < r0.high
    assert cone.transmissivity_ft2_day.source == "reference"  # literature K [reference]
    assert cone.q_gpm == 75.0


def test_composite_exceeds_a_single_well(hydro_settings: Settings) -> None:
    wells = dw.load_dewatering_wells(settings=hydro_settings)
    lat, lon = 40.7954, -84.1209  # near the wellfield
    composite = dw.composite_drawdown_at(wells, lat, lon, asof=ASOF, settings=hydro_settings)
    one = dw.composite_drawdown_at(wells[:1], lat, lon, asof=ASOF, settings=hydro_settings)
    assert composite > one > 0  # 44 wells superimpose to more than any single cone


def test_impact_on_domestic_census_wells(hydro_settings: Settings) -> None:
    impact = dw.load_dewatering_impact(asof=ASOF, settings=hydro_settings)
    assert impact is not None
    assert impact.well_count == 44 and impact.active_count == 1
    assert impact.total_capacity_mgd == 4.9  # 3400 gpm combined
    assert impact.operating_window == "2025-12-16 to 2026-05-28"
    # ~10 domestic wells drawn down > 1 ft; the worst several by > 5 ft.
    assert 5 <= len(impact.impacted_wells) <= 20
    assert sum(1 for w in impact.impacted_wells if w.composite_drawdown_ft.value > 5) >= 3
    # sorted worst-first, every bracket contains its central value, all domestic.
    vals = [w.composite_drawdown_ft.value for w in impact.impacted_wells]
    assert vals == sorted(vals, reverse=True)
    for w in impact.impacted_wells:
        d = w.composite_drawdown_ft
        assert d.low is not None and d.high is not None and d.low <= d.value <= d.high
        assert (w.well_use or "").upper() == "DOMESTIC"


def test_findings_surface_the_impact(hydro_settings: Settings) -> None:
    impact = dw.load_dewatering_impact(asof=ASOF, settings=hydro_settings)
    assert impact is not None
    findings = dw.dewatering_findings(impact)
    field = next(f for f in findings if f.check == "dewatering-wellfield")
    assert "4.9 MGD" in field.detail and field.ok is True
    dom = next(f for f in findings if f.check == "dewatering-domestic-impact")
    assert dom.ok is False and "domestic census wells" in dom.detail  # a surfaced impact
