"""Smoke test for the static-site generator (`bosc site build`)."""

from __future__ import annotations

from pathlib import Path

from bosc.config import Settings
from bosc.site import build_site

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_build_site_stages_expected_pages(tmp_path: Path) -> None:
    """Building against the committed corpus emits the core pages + record kinds."""
    settings = Settings(data_dir=REPO_ROOT / "data")
    web = tmp_path / "web"

    result = build_site(settings, web_dir=web)

    # Top-level generated pages exist and are non-empty. The landing page is
    # staged as home.md; the renderer emits it as the root index.html.
    for name in ("home.md", "timeline.md", "entities.md", "exhibits.md"):
        page = web / name
        assert page.is_file(), f"missing {name}"
        assert page.read_text(encoding="utf-8").strip()

    # The records index plus at least the deeds + permits kind pages were rendered.
    assert (web / "records" / "index.md").is_file()
    slugs = {p.slug for p in result.record_pages}
    assert {"deeds", "permits-epa", "permits-npdes"} <= slugs

    # Cross-document layer ran and reported real counts.
    assert result.n_records > 0
    assert result.n_entities > 0
    assert result.n_events > 0

    # Narrative + raw artifacts were mirrored at repo-relative paths so the
    # existing cross-links resolve (the dossier and a raw extraction both land).
    assert (web / "docs" / "DOSSIER.md").is_file()
    assert (web / "data" / "extracted" / "aedg" / "roundabouts.summary.opc.yaml").is_file()

    # The entity graph page carries a Mermaid diagram.
    assert "```mermaid" in (web / "entities.md").read_text(encoding="utf-8")

    # The RSEI toxic-release inventory page is staged with the ranked facilities.
    rsei_page = web / "rsei.md"
    assert rsei_page.is_file()
    rsei_body = rsei_page.read_text(encoding="utf-8")
    assert "RSEI toxic-release inventory" in rsei_body
    assert "GENERAL DYNAMICS LAND SYSTEMS" in rsei_body
    assert result.n_rsei_facilities >= 40

    # The GLEIF entity-LEI page is staged with the resolved corridor entities.
    lei_page = web / "lei.md"
    assert lei_page.is_file()
    lei_body = lei_page.read_text(encoding="utf-8")
    assert "Corridor entity LEIs" in lei_body
    assert "GENERAL DYNAMICS" in lei_body.upper()
    assert result.n_lei_records >= 5

    # The GIS findings map page + its committed GeoJSON asset are staged, with the
    # toggleable RSEI overlay wired in.
    gis = web / "gis-map.md"
    assert gis.is_file()
    body = gis.read_text(encoding="utf-8")
    assert 'id="bosc-map"' in body and "leaflet" in body.lower()
    assert "RSEI toxic-release facilities" in body
    assert (web / "assets" / "gis-findings.geojson").is_file()


def test_gis_findings_geojson_is_valid() -> None:
    import json

    path = REPO_ROOT / "data" / "site" / "gis-findings.geojson"
    fc = json.loads(path.read_text(encoding="utf-8"))
    assert fc["type"] == "FeatureCollection"
    layers = {f["properties"]["layer"] for f in fc["features"]}
    assert {"campus", "jsmc", "wwtp", "floodway", "floodplain", "rsei"} <= layers
    # The corridor view layers it in: a study-area polygon + the roadwork road centerline.
    assert {"corridor", "roadwork"} <= layers
    # Every feature has non-empty geometry (polygons for areas, points for WWTPs/RSEI,
    # a line for the corridor roadwork centerline).
    for f in fc["features"]:
        assert f["geometry"]["type"] in (
            "Polygon",
            "MultiPolygon",
            "Point",
            "LineString",
            "MultiLineString",
        )
        assert f["geometry"]["coordinates"]
    # RSEI points carry a graduated radius + score for the sized overlay markers.
    rsei = [f for f in fc["features"] if f["properties"]["layer"] == "rsei"]
    assert len(rsei) >= 40
    assert all(f["geometry"]["type"] == "Point" for f in rsei)
    assert all("radius" in f["properties"] and "score" in f["properties"] for f in rsei)


def test_merge_rsei_layer_is_idempotent() -> None:
    """Merging RSEI points twice yields the same single rsei layer (no duplication)."""
    from bosc.config import Settings
    from bosc.rsei import load_inventory
    from bosc.site.gismap import merge_rsei_layer

    inv = load_inventory(Settings(data_dir=REPO_ROOT / "data").reference_dir)
    assert inv is not None
    base: dict = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [0, 0]},
                "properties": {"layer": "wwtp", "label": "x"},
            }
        ],
    }
    once, n1 = merge_rsei_layer(base, inv)
    twice, n2 = merge_rsei_layer(once, inv)
    assert n1 == n2 > 0
    rsei_once = [f for f in once["features"] if f["properties"]["layer"] == "rsei"]
    rsei_twice = [f for f in twice["features"] if f["properties"]["layer"] == "rsei"]
    assert len(rsei_once) == len(rsei_twice) == n1
    # The pre-existing non-rsei feature is preserved.
    assert any(f["properties"]["layer"] == "wwtp" for f in twice["features"])


def test_merge_rsei_layer_rings_flagged_water_dischargers() -> None:
    """With the toxic screen, critical water dischargers get a water_flag property."""
    from bosc.config import Settings
    from bosc.hydrology import toxics
    from bosc.rsei import load_inventory
    from bosc.site.gismap import merge_rsei_layer

    ref = Settings(data_dir=REPO_ROOT / "data").reference_dir
    inv = load_inventory(ref)
    screen = toxics.build_screen(Settings(data_dir=REPO_ROOT / "data"))
    assert inv is not None
    base: dict = {"type": "FeatureCollection", "features": []}
    fc, _ = merge_rsei_layer(base, inv, screen)
    flagged = [f for f in fc["features"] if f["properties"].get("water_flag")]
    # The three Ottawa-corridor majors plus the one elevated terminal.
    assert {f["properties"]["water_flag"] for f in flagged} <= {"critical", "elevated"}
    assert sum(1 for f in flagged if f["properties"]["water_flag"] == "critical") == 3
    # A ringed feature names its receiving water in the popup label.
    crit = next(f for f in flagged if f["properties"]["water_flag"] == "critical")
    assert "toxic water discharger" in crit["properties"]["label"]
    # Without the screen, no rings.
    plain, _ = merge_rsei_layer({"type": "FeatureCollection", "features": []}, inv)
    assert not any(f["properties"].get("water_flag") for f in plain["features"])
