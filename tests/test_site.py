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
    # home.md (the CustomMill theme owns the root index.html as its SPA shell).
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

    # The GIS findings map page + its committed GeoJSON asset are staged.
    gis = web / "gis-map.md"
    assert gis.is_file()
    body = gis.read_text(encoding="utf-8")
    assert 'id="bosc-map"' in body and "leaflet" in body.lower()
    assert (web / "assets" / "gis-findings.geojson").is_file()


def test_gis_findings_geojson_is_valid() -> None:
    import json

    path = REPO_ROOT / "data" / "site" / "gis-findings.geojson"
    fc = json.loads(path.read_text(encoding="utf-8"))
    assert fc["type"] == "FeatureCollection"
    layers = {f["properties"]["layer"] for f in fc["features"]}
    assert {"campus", "jsmc", "wwtp", "floodway", "floodplain"} <= layers
    # Every feature has non-empty geometry (polygons for areas, points for WWTPs).
    for f in fc["features"]:
        assert f["geometry"]["type"] in ("Polygon", "MultiPolygon", "Point")
        assert f["geometry"]["coordinates"]
