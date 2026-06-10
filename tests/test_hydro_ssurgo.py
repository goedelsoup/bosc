"""SSURGO HSG connector: offline fixture replay + dominant-HSG tally + storm wire-in."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bosc.config import Settings
from bosc.connectors import OfflineError
from bosc.hydrology.connectors import ssurgo
from bosc.pipeline.hydrology import run_storm

REPO_ROOT = Path(__file__).resolve().parents[1]
PARCELS = REPO_ROOT / "data" / "reference" / "periplus" / "bosc-parcels.geojson"


def test_dominant_hsg_from_fixture(hydro_settings: Settings) -> None:
    survey = ssurgo.dominant_hsg(PARCELS, settings=hydro_settings)
    # The recorded SSURGO grid sample: dual B/D lowlands dominate, upland B second —
    # the cited "C" assumption is not what SSURGO shows for this footprint.
    assert survey.dominant_hsg == "B/D"
    assert survey.hsg_letter == "B"  # cn_for input: a dual group reads as its drained letter
    assert survey.n_points == 31
    groups = {d.hsg for d in survey.distribution}
    assert {"B/D", "B"} <= groups
    assert sum(d.points for d in survey.distribution) == survey.n_points
    # Shares sum to ~1 and the distribution is ordered by share descending.
    assert sum(d.fraction for d in survey.distribution) == pytest.approx(1.0, abs=0.02)
    assert [d.fraction for d in survey.distribution] == sorted(
        (d.fraction for d in survey.distribution), reverse=True
    )


def test_dominant_hsg_offline_miss_raises(hydro_settings: Settings, tmp_path: Path) -> None:
    # A footprint with no committed fixture must fail loudly (hermetic), never fabricate.
    fp = tmp_path / "elsewhere.geojson"
    fp.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [-83.0, 40.0],
                                    [-83.0, 40.01],
                                    [-82.99, 40.01],
                                    [-82.99, 40.0],
                                    [-83.0, 40.0],
                                ]
                            ],
                        },
                    }
                ],
            }
        )
    )
    with pytest.raises(OfflineError):
        ssurgo.dominant_hsg(fp, settings=hydro_settings)


def test_storm_uses_connector_sourced_hsg(hydro_settings: Settings) -> None:
    # live=True + offline fixtures: HSG comes from SSURGO (connector), not the assumption.
    runoff, _ = run_storm(return_period_yr=25, settings=hydro_settings, live=True)
    assert runoff.hsg.source == "connector"
    assert "SSURGO" in (runoff.hsg.citation or "")
    assert runoff.hsg.value == pytest.approx(2.0)  # HSG B -> code 2 (A=1..D=4)


def test_storm_hsg_falls_back_to_assumption(
    hydro_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    # When SSURGO can't be sourced, HSG falls back to the cited "C" assumption (flagged).
    from bosc.hydrology import stormwater

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise ssurgo.SsurgoError("no soil data")

    monkeypatch.setattr(stormwater, "dominant_hsg", _boom)
    letter, code = stormwater._resolve_hsg(
        stormwater._parcels_path(hydro_settings), settings=hydro_settings, live=True
    )
    assert letter == "C"
    assert code.source == "assumption"
    assert code.value == pytest.approx(3.0)  # HSG C -> code 3
