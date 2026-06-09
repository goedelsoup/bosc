"""POI merge: block resolved candidates into deduplicated groups + the auto/review gate."""

from __future__ import annotations

from bosc.config import Settings
from bosc.poi.merge import Item, merge_candidates, merge_resolutions
from bosc.poi.model import POICandidate
from bosc.poi.resolve import Resolution


def _cand(kind: str, value: str, citations: list[str]) -> POICandidate:
    return POICandidate(
        kind=kind,  # type: ignore[arg-type]
        value=value,
        normalized=value.upper(),
        occurrences=len(citations),
        citations=citations,
    )


def _res(kind: str, value: str, parcel_no: str | None, conf: str, auto: bool) -> Resolution:
    method = "parcel-id" if kind == "parcel-id" else "geocode+parcel-at-point"
    return Resolution(
        kind=kind,
        value=value,
        method=method,  # type: ignore[arg-type]
        confidence=conf,  # type: ignore[arg-type]
        parcel_no=parcel_no,
        parcel=None,
        point=None,
        matched_address=None,
        auto_mergeable=auto,
    )


def test_merge_blocks_and_gates(poi_settings: Settings) -> None:
    items: list[Item] = [
        # exact parcel-id to a NEW parcel + an address to the SAME parcel → one 'auto' group
        (
            _cand("parcel-id", "11-1111-11-111.111", ["a.yaml"]),
            _res("parcel-id", "x", "11111111111111", "high", True),
        ),
        (
            _cand("address", "100 Foo St, Lima, OH", ["b.yaml"]),
            _res("address", "x", "11111111111111", "medium", False),
        ),
        # address-only to another NEW parcel → 'review' (rests on a geocode)
        (
            _cand("address", "200 Bar Rd, Lima, OH", ["c.yaml"]),
            _res("address", "x", "22222222222222", "medium", False),
        ),
        # a campus parcel already in the store → 'covered'
        (
            _cand("parcel-id", "36-0100-03-002.000", ["d.yaml"]),
            _res("parcel-id", "x", "36010003002000", "high", True),
        ),
        # nothing resolved → the 'unresolved' bucket
        (_cand("address", "Mystery Place", ["e.yaml"]), _res("address", "x", None, "low", False)),
    ]
    groups = merge_resolutions(items, settings=poi_settings)
    by_parcel = {g.parcel_no: g for g in groups}

    auto = by_parcel["11111111111111"]
    assert auto.status == "auto" and auto.has_exact_id is True
    assert len(auto.members) == 2 and {m.kind for m in auto.members} == {"parcel-id", "address"}

    review = by_parcel["22222222222222"]
    assert review.status == "review" and review.has_exact_id is False

    assert by_parcel["36010003002000"].status == "covered"  # in the store
    assert by_parcel[None].status == "unresolved"

    # Sorted by actionability: 'auto' first, 'covered' last.
    assert groups[0].status == "auto"
    assert groups[-1].status == "covered"


def test_merge_candidates_integration(poi_offline_settings: Settings) -> None:
    # End-to-end resolve + merge over the two candidates we have real fixtures for.
    cands = [
        POICandidate(
            kind="parcel-id",
            value="36-0100-03-002.000",
            normalized="36010003002000",
            occurrences=1,
            citations=["x"],
        ),
        POICandidate(
            kind="address",
            value="3640 Spencerville Road, Lima, OH",
            normalized="3640 SPENCERVILLE ROAD, LIMA, OH",
            occurrences=1,
            citations=["y"],
        ),
    ]
    groups = merge_candidates(cands, settings=poi_offline_settings)
    by_parcel = {g.parcel_no: g for g in groups}

    assert by_parcel["36010003002000"].status == "covered"  # a campus parcel
    spencerville = by_parcel["46040202001000"]
    assert spencerville.status == "review"  # geocoded, not yet a POI
    assert spencerville.has_exact_id is False
