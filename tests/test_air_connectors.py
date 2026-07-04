"""AERMET/AERMAP preprocessing connectors: offline fixture replay + emitters (#1179)."""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.air.connectors import aermap, aermet, igra, isd, ned
from watermark.air.connectors._cache import AirOfflineError
from watermark.config import Settings

# --- ISD surface ---------------------------------------------------------------------


def test_isd_surface_offline(air_settings: Settings) -> None:
    surf = isd.fetch_surface(settings=air_settings)

    assert surf.station_id == "725330-14827"
    assert surf.call_sign == "KFWA"
    assert surf.latitude == pytest.approx(40.978, abs=0.001)
    assert surf.longitude == pytest.approx(-85.195, abs=0.001)
    assert surf.elevation_m == pytest.approx(250.0)
    assert surf.year == 2023
    assert surf.coverage_fraction() > 0

    first = surf.observations[0]
    assert first.time == "2023-01-01T00:00:00Z"
    assert first.wind_dir_deg == 180
    assert first.wind_speed_ms == pytest.approx(5.0)
    assert first.air_temp_c == pytest.approx(-1.1)
    assert first.dew_point_c == pytest.approx(-4.5)
    assert first.ceiling_m == 22000
    assert first.sea_level_pressure_hpa == pytest.approx(1015.2)
    # Raw ISHD text is passed through verbatim for the AERMET surface input.
    assert surf.raw_ishd.strip().splitlines()[0].startswith("0100725330")


def test_isd_missing_sentinels_become_none(air_settings: Settings) -> None:
    surf = isd.fetch_surface(settings=air_settings)
    last = surf.observations[-1]  # the all-nines sentinel line
    assert last.wind_dir_deg is None
    assert last.wind_speed_ms is None
    assert last.air_temp_c is None
    assert last.ceiling_m is None
    assert last.sea_level_pressure_hpa is None


def test_isd_offline_unfetched_station_raises(air_settings: Settings) -> None:
    with pytest.raises(AirOfflineError) as exc:
        isd.fetch_surface(station="999999-99999", year=2023, settings=air_settings)
    assert "isd" in str(exc.value)


def test_isd_bad_station_raises() -> None:
    with pytest.raises(ValueError, match="USAF-WBAN"):
        isd.fetch_surface(station="notastation", settings=Settings())


# --- IGRA upper air ------------------------------------------------------------------


def test_igra_upperair_offline(air_settings: Settings) -> None:
    ua = igra.fetch_upperair(settings=air_settings)

    assert ua.station_id == "USM00072426"
    assert ua.latitude == pytest.approx(40.978, abs=0.001)
    assert ua.longitude == pytest.approx(-85.195, abs=0.001)
    # The fixture payload is already year-filtered (what fetch() caches): all soundings 2023.
    assert {s.time[:4] for s in ua.soundings} == {"2023"}
    assert len(ua.soundings) == 4

    s0 = ua.soundings[0]
    assert s0.time == "2023-01-01T00:00:00Z"
    assert s0.release_time == "00:00"
    assert s0.n_levels == 4
    lev = s0.levels[0]
    assert lev.pressure_hpa == pytest.approx(1013.0)
    assert lev.height_m == 250
    assert lev.temperature_c == pytest.approx(1.5)
    assert lev.dewpoint_depression_c == pytest.approx(2.0)
    assert lev.wind_dir_deg == 270
    assert lev.wind_speed_ms == pytest.approx(3.5)


def test_igra_filter_year_drops_other_years() -> None:
    header_2022 = "#USM00072426 2022 01 01 00 0000    1 x        x         409780 -0851950"
    header_2023 = "#USM00072426 2023 06 15 12 1200    1 x        x         409780 -0851950"
    level = "21 -9999 101300A  250A   15A   50   20    270    35"
    text = "\n".join([header_2022, level, header_2023, level])
    filtered = igra._filter_year(text, 2023)
    assert "2023" in filtered
    assert "2022" not in filtered


def test_igra_offline_unfetched_station_raises(air_settings: Settings) -> None:
    with pytest.raises(AirOfflineError):
        igra.fetch_upperair(station="USM00099999", year=2023, settings=air_settings)


# --- NED terrain ---------------------------------------------------------------------


def test_ned_terrain_offline(air_settings: Settings) -> None:
    dom = ned.fetch_terrain(settings=air_settings)
    assert dom.source == "fixture DEM (offline)"
    assert dom.epsg == 4326
    assert dom.width > 0 and dom.height > 0
    assert dom.bbox[0] < dom.center_lon < dom.bbox[2]

    pts = ned.sample_points(dom, [("REC1", dom.center_lat, dom.center_lon), ("OUT", 10.0, 10.0)])
    assert pts[0].elevation_m is not None and pts[0].elevation_m > 0
    assert pts[1].elevation_m is None  # outside the DEM domain


def test_ned_offline_miss_raises(air_settings: Settings) -> None:
    with pytest.raises(AirOfflineError):
        ned.fetch_terrain(center_lat=0.0, center_lon=0.0, settings=air_settings)


# --- AERMET emitter ------------------------------------------------------------------


def test_aermet_emitter_stages_inputs(air_settings: Settings, tmp_path: Path) -> None:
    surf = isd.fetch_surface(settings=air_settings)
    ua = igra.fetch_upperair(settings=air_settings)
    inputs = aermet.write_aermet_inputs(surf, ua, out_dir=tmp_path, site_label="lima")

    assert inputs.surface_station == "725330-14827"
    assert inputs.upperair_station == "USM00072426"
    assert inputs.start_date == "2023-01-01"
    assert inputs.n_soundings == 4

    runstream = Path(inputs.runstream_path).read_text()
    assert "SURFACE" in runstream and "ISHD" in runstream
    assert "UPPERAIR" in runstream and "IGRA" in runstream
    assert "MERGE" in runstream
    # METPREP surface characteristics stay a commented template — never fabricated met.
    assert "** METPREP" in runstream
    assert "\nMETPREP" not in runstream
    # The surface file is the raw ISHD, byte-for-byte.
    assert Path(inputs.surface_path).read_text(encoding="latin-1") == surf.raw_ishd


def test_aermet_utc_offset_override(air_settings: Settings, tmp_path: Path) -> None:
    surf = isd.fetch_surface(settings=air_settings)
    ua = igra.fetch_upperair(settings=air_settings)
    inputs = aermet.write_aermet_inputs(surf, ua, out_dir=tmp_path, site_label="lima", utc_offset=5)
    assert inputs.utc_offset == 5


# --- AERMAP emitter ------------------------------------------------------------------


def test_aermap_build_offline(air_settings: Settings, tmp_path: Path) -> None:
    outputs = aermap.build_aermap(out_dir=tmp_path, site_label="lima", settings=air_settings)

    assert outputs.n_points == 1
    assert outputs.utm_epsg == 32617  # Lima UTM 17N, profile-filled
    assert outputs.dem_source == "fixture DEM (offline)"
    assert outputs.elevations[0].elevation_m is not None

    control = Path(outputs.control_path).read_text()
    assert "CO STARTING" in control and "DATAFILE" in control
    assert "SO STARTING" in control and "RE STARTING" in control

    elev_doc = Path(outputs.elevations_path).read_text()
    assert "[derived]" in elev_doc
    assert "aermap" in elev_doc
