"""SSURGO HSG connector: offline fixture replay + dominant-HSG tally + storm wire-in."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.connectors import OfflineError
from watermark.hydrology import geo
from watermark.hydrology.connectors import ssurgo
from watermark.hydrology.connectors._cache import cache_key
from watermark.pipeline.hydrology import run_storm

REPO_ROOT = Path(__file__).resolve().parents[1]
PARCELS = REPO_ROOT / "data" / "reference" / "periplus" / "bosc-parcels.geojson"

_SQUARE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-83.0, 40.0], [-83.0, 40.01], [-82.99, 40.01], [-82.99, 40.0], [-83.0, 40.0]]
                ],
            },
        }
    ],
}


def _seeded(tmp_path: Path, table: list[list[object]]) -> tuple[Path, Settings]:
    """A footprint + offline Settings whose committed-fixture slot holds ``table``.

    Lets a test hand the connector an exact SDA payload (ties, reordered columns, a
    drifted header) without a network call — the cache key is the deterministic point
    grid, so it is computable here the same way the connector computes it.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)  # callers may pass a fresh sub-path
    footprint = tmp_path / "square.geojson"
    footprint.write_text(json.dumps(_SQUARE))
    points = geo.grid_points_within(footprint, 6)
    key = cache_key({"points": [list(p) for p in points]})
    fixtures = tmp_path / "fixtures" / "ssurgo"
    fixtures.mkdir(parents=True)
    (fixtures / f"{key}.json").write_text(json.dumps({"payload": {"Table": table}}))
    # data_dir -> tmp_path so the real data/cache/hydrology/ can never shadow the fixture.
    settings = Settings(
        data_dir=tmp_path, hydro_offline=True, hydro_fixtures_dir=tmp_path / "fixtures"
    )
    return footprint, settings


def test_dominant_hsg_from_fixture(hydro_settings: Settings) -> None:
    survey = ssurgo.dominant_hsg(PARCELS, settings=hydro_settings)
    # The recorded SSURGO grid sample: dual B/D lowlands dominate, upland B second —
    # the cited "C" assumption is not what SSURGO shows for this footprint.
    assert survey.dominant_hsg == "B/D"
    # WS-20: the connector reports the group verbatim and has no default condition — the caller
    # states which one it is modeling, and the two letters are materially different soils.
    assert survey.dominant_is_dual is True
    assert survey.letter_for("drained") == "B"
    assert survey.letter_for("undrained") == "D"
    # 17 of 31 points (B/D 16 + C/D 1) are dual-rated — the share the switch moves.
    assert survey.dual_fraction == pytest.approx(0.548, abs=0.01)
    assert survey.n_points == 31
    groups = {d.hsg for d in survey.distribution}
    assert {"B/D", "B"} <= groups
    assert sum(d.points for d in survey.distribution) == survey.n_points
    # Shares sum to ~1 and the distribution is ordered by share descending.
    assert sum(d.fraction for d in survey.distribution) == pytest.approx(1.0, abs=0.02)
    assert [d.fraction for d in survey.distribution] == sorted(
        (d.fraction for d in survey.distribution), reverse=True
    )


def test_query_picks_one_component_per_point() -> None:
    # WS-19: co-dominant components (an exact comppct_r tie) must not each emit a row.
    sql = ssurgo._build_query([(-84.1, 40.8), (-84.2, 40.9)])
    assert "MAX(" not in sql  # the = MAX(comppct_r) predicate returns every tied row
    assert sql.count("SELECT TOP 1") == 2  # one deterministic winner per grid point
    assert sql.count("UNION ALL") == 1
    # The total order: dominant first, a rated group ahead of an unrated one, then stable.
    assert (
        sql.count(
            "ORDER BY co.comppct_r DESC, CASE WHEN co.hydgrp IS NULL THEN 1 ELSE 0 END, "
            "co.hydgrp, co.cokey"
        )
        == 2
    )


def test_tied_rows_cast_one_vote_per_point(tmp_path: Path) -> None:
    # A payload recorded before the single-winner query (or any server-side regression)
    # still collapses to one vote per point, so n_points can't exceed the sampled grid.
    footprint, settings = _seeded(
        tmp_path,
        [
            ["pt", "hsg"],
            ["0", "B"],
            ["0", "D"],  # co-dominant tie at point 0 — one location, not two samples
            ["1", "D"],
            ["2", None],  # sampled but unrated: skipped, never backfilled
        ],
    )
    survey = ssurgo.dominant_hsg(footprint, settings=settings)
    assert survey.n_points == 2  # points 0 and 1, not 3
    assert {d.hsg: d.points for d in survey.distribution} == {"B": 1, "D": 1}
    assert survey.dominant_hsg == "B"  # the tie broke to the lower hydgrp, deterministically


def test_hsg_read_by_column_name_not_position(tmp_path: Path) -> None:
    # Column order is not a contract: the header names it, so a reordered response reads
    # the same. (Positionally, this payload would tally the point ids as soil groups.)
    footprint, settings = _seeded(tmp_path, [["hsg", "pt"], ["C", "0"], ["C", "1"], ["B", "2"]])
    survey = ssurgo.dominant_hsg(footprint, settings=settings)
    assert survey.dominant_hsg == "C"
    assert survey.n_points == 3
    assert {d.hsg for d in survey.distribution} == {"C", "B"}


def test_unattributable_point_ids_raise(tmp_path: Path) -> None:
    # `pt` is the grid index this connector emitted; a row that doesn't echo one back
    # can't be attributed to a sampled location. Stringifying it would give each bad id a
    # key of its own — two more "points" in the tally, the n_points hole from the far side.
    footprint, settings = _seeded(tmp_path, [["pt", "hsg"], ["0", "B"], [None, "D"]])
    with pytest.raises(ssurgo.SsurgoError, match="non-numeric point id"):
        ssurgo.dominant_hsg(footprint, settings=settings)

    footprint, settings = _seeded(tmp_path / "b", [["pt", "hsg"], ["0", "B"], ["9999", "D"]])
    with pytest.raises(ssurgo.SsurgoError, match="outside the sampled grid"):
        ssurgo.dominant_hsg(footprint, settings=settings)


def test_missing_hsg_column_raises(tmp_path: Path) -> None:
    # Schema drift fails loudly rather than being read positionally into a wrong tally.
    footprint, settings = _seeded(tmp_path, [["pt", "hydgrp"], ["0", "B"]])
    with pytest.raises(ssurgo.SsurgoError, match="hsg"):
        ssurgo.dominant_hsg(footprint, settings=settings)


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
    from watermark.hydrology import stormwater

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise ssurgo.SsurgoError("no soil data")

    monkeypatch.setattr(stormwater, "dominant_hsg", _boom)
    basis = stormwater._resolve_hsg(
        stormwater._parcels_path(hydro_settings), settings=hydro_settings, live=True
    )
    assert basis.group == "C"
    assert basis.dual is False  # a single group — the drainage switch doesn't bind
    assert basis.pre_letter == basis.post_letter == "C"
    assert basis.pre_hsg.source == "assumption"
    assert basis.pre_hsg.value == pytest.approx(3.0)  # HSG C -> code 3
