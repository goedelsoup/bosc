"""The `water-seasonal-field` feed — the seasonal climograph for the deck.gl water field (#1236).

Distinct from `air-dispersion-field`: the seasonal read `evaluate_seasonal` produces has real,
committed climate normals + Ottawa low flows, so unlike the AERMOD field it does *not* degrade in
CI — the reference export carries the twelve months of net-atmospheric-withdrawal surface. The
guards: the reference build emits the feed with `reference` provenance, the deficit boundary
(net = ET0 - precip) matches the growing-season flag, and the low-flow multiple screens the
*modeled* buildout draw (so it is [inference], never a measured withdrawal). Reference-site gated.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.site.export import export_bundle
from watermark.site.feeds import CONTRACT_VERSION

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_contract_version_bumped() -> None:
    """This feed landed at 1.22.0 (additive/MINOR); the contract has since advanced to 1.39.0
    (ProvenancedValue range 1.23.0 #760, contacts feed 1.24.0, facts feed 1.25.0 #1587, the
    passages feed 1.26.0 #1589, the open-questions feed 1.27.0 #1568, DocumentItem version/dedup
    metadata 1.27.1 #1590, the corpus-index feed 1.28.0 #1573, the manifest exports block
    1.29.0 #1574, the corpus-nodes feed 1.30.0 #1575, rsei top_water_chemicals 1.30.1 #1607,
    the effluent-credited dilution ratio 1.30.2 #1615, the routed-hydrograph reach
    subreaches/courant 1.30.3 (WS-09 #1609), the facility feed 1.31.0 #1628, the
    defense-contractors federal-award join 1.32.0 #1662, the hydrology-scenarios
    seasonal-floor + campus-discharge fields 1.32.1 #1633, the economics-baseline
    government-ownership + coverage/unit caveats 1.33.0 #1661, then the assimilative-check
    acute (1Q10) dilution pair 1.34.0 (WS-08 #1608), the enforcement/finance record groups
    1.34.0 (#1746), the grid-backdrop feed 1.35.0 (GP-E #1642), then the typed defense
    registers 1.36.0 (ME-D #1663), then the drawdown feed 1.37.0 (well-drawdown thread), then the
    dewatering feed + geo/dewatering map layer 1.38.0 (the documented construction-dewatering
    wellfield), then the dewatering discharge-screen + reservoir-recharge fields 1.39.0 (the
    where-did-the-water-go gage screen))."""
    assert CONTRACT_VERSION == "1.39.0"


@pytest.fixture(scope="module")
def lima_bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("seasonalfield") / "b"
    export_bundle(
        Settings(data_dir=REPO_ROOT / "data"),
        out_dir=out,
        generated_at="2026-01-01T00:00:00+00:00",
        skip_embeddings=True,
    )
    return out


def _field(bundle: Path) -> dict:
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    ref = next((f for f in manifest["feeds"] if f["name"] == "water-seasonal-field"), None)
    assert ref is not None, "reference build must emit the water-seasonal-field feed"
    assert ref["kind"] == "object"
    return json.loads((bundle / ref["path"]).read_text(encoding="utf-8"))


def test_reference_export_emits_the_seasonal_field(lima_bundle: Path) -> None:
    """The reference build ships `water-seasonal-field` with real months (climate normals are
    committed, so it does not degrade like the AERMOD field), `reference`-provenanced."""
    manifest = json.loads((lima_bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["contract_version"] == "1.39.0"

    field = _field(lima_bundle)
    assert field["site"] == "lima"
    assert field["scenario"] == "buildout"
    assert field["provenance"] == "reference"  # cited normals — the climograph is not an assumption
    assert field["available"] is True
    assert field["unit"] == "mm/day"
    # Twelve months, JAN..DEC, in order.
    assert [m["month"] for m in field["months"]] == [
        "JAN",
        "FEB",
        "MAR",
        "APR",
        "MAY",
        "JUN",
        "JUL",
        "AUG",
        "SEP",
        "OCT",
        "NOV",
        "DEC",
    ]
    # Lima's Ottawa low flows are cited, not fabricated.
    assert field["annual_7q10_cfs"] is not None
    assert field["summer_30q10_cfs"] is not None


def test_deficit_boundary_matches_the_growing_season(lima_bundle: Path) -> None:
    """The threshold isopleth is net = 0: a growing-season month is exactly one whose net
    atmospheric withdrawal (ET0 - precip) is positive — the FieldLayer contour and the flag agree."""
    field = _field(lima_bundle)
    for m in field["months"]:
        assert m["growing_season"] == (m["net_atmospheric_mm_day"] > 0), (
            f"{m['month']}: growing_season flag disagrees with the net=0 deficit boundary"
        )
        # net = ET0 - precip, the field scalar.
        assert m["net_atmospheric_mm_day"] == pytest.approx(
            m["et0_mm_day"] - m["precip_mm_day"], abs=1e-2
        )
    growing = {m["month"] for m in field["months"] if m["growing_season"]}
    assert growing == set(field["growing_season_months"])
    assert growing, "Lima's climate has a growing-season deficit window"


def test_growing_season_reads_against_the_tighter_summer_floor(lima_bundle: Path) -> None:
    """In the growing season the draw is screened against the cited summer 30Q10, not the annual
    7Q10 — the whole point of the seasonal field (the annual multiple understates the pinch)."""
    field = _field(lima_bundle)
    summer = [m for m in field["months"] if m["growing_season"]]
    assert summer and all(m["low_flow_basis"] == "30Q10 summer" for m in summer)
    # The seasonal (summer) multiple is the load-bearing headline the annual figure understates.
    assert field["summer_multiple"] is not None


def test_sibling_site_has_no_seasonal_field(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Reference-site gated like `routed-hydrograph`: a peer carries no seasonal field (its
    scenario + Ottawa low flows are Lima's, not the peer's) (#1236)."""
    out = tmp_path_factory.mktemp("fwseasonal") / "b"
    export_bundle(
        Settings(data_dir=REPO_ROOT / "data", site="fort-wayne"),
        out_dir=out,
        generated_at="2026-01-01T00:00:00+00:00",
        skip_embeddings=True,
    )
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert "water-seasonal-field" not in {f["name"] for f in manifest["feeds"]}
