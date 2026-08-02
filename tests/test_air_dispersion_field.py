"""The `air-dispersion-field` feed — the gridded AERMOD surface for the deck.gl viz (#1232).

Two guards: the gridding factory reshapes a real AERMOD plotfile onto its receptor grid
(round-tripping the committed `sample.annual.plt` fixture), and the reference-site export emits
the feed with the geometry/geo_ref/NAAQS lines resolved, the `assumption` provenance marker, and
the bumped bundle contract version — degrading to empty `values` (never fabricated) when the
AERMOD binary is absent (as it is in CI).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from watermark.air.aermod.engine import parse_plotfile
from watermark.site.feeds import CONTRACT_VERSION, DispersionField, DispersionGeoRef, DispersionGrid

REPO_ROOT = Path(__file__).resolve().parents[1]
_PLT = REPO_ROOT / "tests" / "fixtures" / "air" / "aermod" / "sample.annual.plt"

# The fixture is a 3x3 grid centered on the source (500 m spacing), with no receptor at the
# source cell (0, 0) — the hole AERMOD leaves at the stack.
_FIXTURE_GRID = DispersionGrid(nx=3, ny=3, dx_m=500.0, dy_m=500.0, x0_m=-500.0, y0_m=-500.0)
_ZERO_GEO = DispersionGeoRef(
    source_lon=-84.122,
    source_lat=40.792,
    sw_lon=-84.13,
    sw_lat=40.78,
    ne_lon=-84.11,
    ne_lat=40.80,
)


def test_contract_version_bumped() -> None:
    """The air-dispersion-field feed advanced the contract to 1.19.0 (MINOR); it has since
    moved on additively — assert it is at least there (compare parsed components, not strings,
    so multi-digit minors/patches order correctly)."""
    version = tuple(int(p) for p in CONTRACT_VERSION.split("."))
    assert version >= (1, 19, 0)


def test_sample_plotfile_round_trips_onto_the_grid() -> None:
    """`parse_plotfile` → `DispersionField.from_receptors` reshapes the fixture onto its grid."""
    recs = parse_plotfile(_PLT.read_text(encoding="utf-8"), ave_period="ANNUAL")
    assert len(recs) == 8, "the fixture has 8 receptors (the source cell is empty)"

    field = DispersionField.from_receptors(
        site="lima",
        pollutant="NOx",
        grid=_FIXTURE_GRID,
        geo_ref=_ZERO_GEO,
        period_receptors={"ANNUAL": [(r.x_m, r.y_m, r.conc) for r in recs]},
        naaqs={"ANNUAL": 100.0},
        available=True,
    )

    # Provenance is the whole point of the feed: assumed CBI-redacted stack ⇒ [inference].
    assert field.provenance == "assumption"
    assert field.available is True
    assert (field.grid.nx, field.grid.ny) == (3, 3)

    period = field.periods[0]
    assert period.averaging_period == "ANNUAL"
    # Row-major values[iy * nx + ix]; the source cell (index 4) has no receptor → null.
    assert len(period.values) == 9
    assert period.values[4] is None
    assert period.values == [0.8421, 1.0532, 0.7911, 1.1204, None, 2.3187, 0.665, 0.9123, 0.7041]
    # Peak is the (500, 0) receptor; it clears the annual NO2 NAAQS (100 µg/m³).
    assert period.max_conc_ug_m3 == 2.3187
    assert period.naaqs_ug_m3 == 100.0
    assert period.exceeds_naaqs is False


def test_degraded_run_grids_to_empty_values_not_fabricated() -> None:
    """With no receptors (binary/met absent) the grid is real but `values` is empty — not faked."""
    field = DispersionField.from_receptors(
        site="lima",
        pollutant="NOx",
        grid=_FIXTURE_GRID,
        geo_ref=_ZERO_GEO,
        period_receptors={"1": [], "ANNUAL": []},
        naaqs={"1": 188.0, "ANNUAL": 100.0},
        available=False,
    )
    assert field.available is False
    assert [p.values for p in field.periods] == [[], []]
    assert [p.max_conc_ug_m3 for p in field.periods] == [None, None]
    # The NAAQS lines still resolve even when nothing was modeled.
    assert [p.naaqs_ug_m3 for p in field.periods] == [188.0, 100.0]


# `lima_bundle` / `site_bundle` are conftest's session-wide, cross-worker exports (#1773).
def test_reference_export_emits_the_field_feed(lima_bundle: Path) -> None:
    """The reference build ships `air-dispersion-field` with real geometry, geo_ref and NAAQS
    lines — `assumption`-provenanced, degrading to empty `values` when AERMOD is absent (CI)."""
    manifest = json.loads((lima_bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["contract_version"] == "1.51.0"
    ref = next((f for f in manifest["feeds"] if f["name"] == "air-dispersion-field"), None)
    assert ref is not None, "reference build must emit the air-dispersion-field feed"

    rows = json.loads((lima_bundle / ref["path"]).read_text(encoding="utf-8"))
    assert {r["pollutant"] for r in rows} == {"NOx", "CO"}
    for row in rows:
        assert row["provenance"] == "assumption", (
            "every field value is [inference], never [verified]"
        )
        # The screening grid is the full ±2.5 km @ 100 m surface (51x51), not the fixture stub.
        assert (row["grid"]["nx"], row["grid"]["ny"]) == (51, 51)
        assert row["geo_ref"]["crs"].startswith("WGS84")
        assert row["periods"], "each pollutant carries its averaging-period fields"
        # No binary in CI ⇒ degraded, but the NAAQS reference lines still resolve.
        assert row["available"] is False
        assert all(p["values"] == [] for p in row["periods"])
        assert any(p["naaqs_ug_m3"] is not None for p in row["periods"])


def test_sibling_site_has_no_field_feed(site_bundle: Callable[[str], Path]) -> None:
    """Reference-site gated like `routed-hydrograph`: a peer carries no field feed (#1232)."""
    out = site_bundle("fort-wayne")
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert "air-dispersion-field" not in {f["name"] for f in manifest["feeds"]}
