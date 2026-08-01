"""The international candidates funnel (#1388/#1390/#1393, epic #1387).

Two halves: the priors connectors driven offline against committed fixtures, and the pure
model/matching logic driven with synthetic observations (no fixture needed, and none wanted —
these tests are about the evidentiary rules, which must hold for any input).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from watermark.config import Settings
from watermark.connectors.priors import (
    OSM_LICENSE,
    PEERINGDB_LICENSE,
    fetch_osm_data_centers,
    fetch_peeringdb_facilities,
)
from watermark.international.aois import AOIS
from watermark.international.model import (
    Candidate,
    CoolingType,
    Corroboration,
    DetectionBasis,
    OperatorAttribution,
    PriorObservation,
    PriorSource,
    build_candidate,
    haversine_m,
)
from watermark.international.register import (
    build_register,
    cluster_observations,
    register_path,
    render_register,
)

QUERETARO = AOIS["queretaro"]


def _obs(
    source: PriorSource,
    source_id: str,
    lat: float,
    lon: float,
    *,
    name: str | None = None,
    operator: str | None = None,
) -> PriorObservation:
    return PriorObservation(
        source=source,
        source_id=source_id,
        url=f"https://example.invalid/{source.value}/{source_id}",
        latitude=lat,
        longitude=lon,
        name=name,
        operator=operator,
        license="test",
        retrieved_at="2026-08-01",
    )


# --- connectors (offline, committed fixtures) --------------------------------------------


def test_peeringdb_parses_and_drops_uncoordinated_rows(priors_settings: Settings) -> None:
    """Rows come back typed, with the licence riding along; a row without coordinates is dropped
    rather than defaulted — (0, 0) is in the Gulf of Guinea, not in Querétaro."""
    rows = fetch_peeringdb_facilities(QUERETARO.country, settings=priors_settings)
    assert rows, "fixture should carry Querétaro facilities"
    assert all(r.latitude and r.longitude for r in rows)
    assert all(r.url.startswith("https://www.peeringdb.com/fac/") for r in rows)
    # The fixture deliberately includes one uncoordinated row; it must not survive.
    assert all(r.country == "MX" for r in rows)


def test_osm_parses_nodes_and_ways(priors_settings: Settings) -> None:
    """Both element kinds resolve to a point — a node from its own lat/lon, a way from Overpass's
    computed ``center`` — and ``is_area`` records which."""
    rows = fetch_osm_data_centers(QUERETARO.overpass_bbox, settings=priors_settings)
    assert rows
    assert all(r.latitude and r.longitude for r in rows)
    assert all(r.element.split("/")[0] in {"node", "way", "relation"} for r in rows)
    assert all(r.is_area == r.element.startswith(("way/", "relation/")) for r in rows)


def test_connectors_are_hermetic_without_a_fixture() -> None:
    """Offline with no fixture is a loud, actionable failure naming the key — never a silent
    empty result that would read as 'this AOI has no data centers'."""
    from watermark.connectors.priors import PriorsOfflineError

    settings = Settings(priors_offline=True, priors_fixtures_dir=None)
    with pytest.raises(PriorsOfflineError, match="no fresh cache/fixture"):
        fetch_peeringdb_facilities("ZZ", settings=settings)


# --- the evidentiary rules, enforced at the type level ------------------------------------


def test_no_basis_is_ever_verified() -> None:
    """The register's central claim: nothing in this funnel can be ``[verified]``."""
    assert {b.tag for b in DetectionBasis} == {"reference", "inference"}
    assert DetectionBasis.PRIORS_ONLY.tag == "reference"
    assert DetectionBasis.VISION_ADJUDICATED.tag == "inference"


def test_uncited_operator_attribution_is_refused() -> None:
    with pytest.raises(ValidationError, match="cited or it is"):
        OperatorAttribution(operator="Definitely Google")


def test_open_attribution_cannot_carry_a_dangling_citation() -> None:
    with pytest.raises(ValidationError, match="carries no citation"):
        OperatorAttribution(citation="https://example.invalid")


def test_priors_only_candidate_cannot_claim_pixels_or_cooling() -> None:
    """A priors-only entry adjudicated nothing, so it may not carry scene ids, and no open
    register publishes cooling design."""
    obs = [_obs(PriorSource.OSM, "node/1", 20.5, -100.3)]
    with pytest.raises(ValidationError, match="adjudicated no pixels"):
        Candidate(
            key="k",
            aoi="queretaro",
            country="MX",
            latitude=20.5,
            longitude=-100.3,
            observations=obs,
            scene_ids=["S2A_1"],
        )
    with pytest.raises(ValidationError, match="leave it `unknown`"):
        Candidate(
            key="k",
            aoi="queretaro",
            country="MX",
            latitude=20.5,
            longitude=-100.3,
            observations=obs,
            cooling=CoolingType.EVAPORATIVE,
        )


def test_adjudicated_candidate_must_record_its_scenes() -> None:
    """The chain-of-custody rule, inverted: once pixels are read, say which."""
    obs = [_obs(PriorSource.OSM, "node/1", 20.5, -100.3)]
    with pytest.raises(ValidationError, match="must record the scene ids"):
        Candidate(
            key="k",
            aoi="queretaro",
            country="MX",
            latitude=20.5,
            longitude=-100.3,
            observations=obs,
            basis=DetectionBasis.VISION_ADJUDICATED,
        )


# --- attribution: the ladder leads, it does not silently resolve --------------------------


def test_disagreeing_sources_produce_a_contested_attribution() -> None:
    """The Querétaro case: PeeringDB says Equinix, OSM says Axtel. The ladder promotes one and
    keeps the other visible rather than discarding it."""
    candidate = build_candidate(
        aoi="queretaro",
        country="MX",
        observations=[
            _obs(PriorSource.PEERINGDB, "8434", 20.5569, -100.2778, operator="Equinix, Inc."),
            _obs(PriorSource.OSM, "way/741133950", 20.5573, -100.2779, operator="Axtel"),
        ],
    )
    assert candidate.attribution.operator == "Equinix, Inc."  # ladder: PeeringDB outranks OSM
    assert candidate.attribution.is_contested
    assert [c.operator for c in candidate.attribution.contested] == ["Axtel"]


def test_spelling_variants_are_not_a_disagreement() -> None:
    """Containment after casefolding — "Equinix" and "Equinix, Inc." are one claim, not two."""
    candidate = build_candidate(
        aoi="dublin",
        country="IE",
        observations=[
            _obs(PriorSource.PEERINGDB, "164", 53.29, -6.41, operator="Equinix, Inc."),
            _obs(PriorSource.OSM, "way/1", 53.29, -6.41, operator="Equinix"),
        ],
    )
    assert not candidate.attribution.is_contested


def test_unnamed_operator_stays_open() -> None:
    candidate = build_candidate(
        aoi="johor", country="MY", observations=[_obs(PriorSource.OSM, "node/9", 1.5, 103.7)]
    )
    assert candidate.attribution.operator is None
    assert candidate.attribution.tag == "open"


# --- matching -----------------------------------------------------------------------------


def test_two_rows_from_one_source_never_merge() -> None:
    """The structural constraint that fixes dense markets: each register deduplicates itself, so
    two of its rows are two facilities however close together they sit."""
    groups = cluster_observations(
        [
            _obs(PriorSource.PEERINGDB, "1", 53.4000, -6.3500),
            _obs(PriorSource.PEERINGDB, "2", 53.4001, -6.3501),  # ~14 m away
        ]
    )
    assert len(groups) == 2


def test_nearest_cross_source_pair_wins() -> None:
    """Greedy shortest-first matching: the OSM row pairs with the PeeringDB row it is closest to,
    not with whichever happened to sort first."""
    near = _obs(PriorSource.PEERINGDB, "near", 53.40000, -6.35000)
    far = _obs(PriorSource.PEERINGDB, "far", 53.40100, -6.35100)  # ~135 m
    osm = _obs(PriorSource.OSM, "way/1", 53.40002, -6.35002)
    groups = cluster_observations([far, near, osm])
    paired = next(g for g in groups if len(g) == 2)
    assert {o.source_id for o in paired} == {"near", "way/1"}


def test_beyond_the_radius_stays_separate() -> None:
    groups = cluster_observations(
        [
            _obs(PriorSource.PEERINGDB, "1", 53.4000, -6.3500),
            _obs(PriorSource.OSM, "way/1", 53.4100, -6.3500),  # ~1.1 km
        ]
    )
    assert len(groups) == 2


def test_corroboration_counts_distinct_sources() -> None:
    single = build_candidate(
        aoi="dublin", country="IE", observations=[_obs(PriorSource.OSM, "way/1", 53.4, -6.35)]
    )
    both = build_candidate(
        aoi="dublin",
        country="IE",
        observations=[
            _obs(PriorSource.OSM, "way/1", 53.4, -6.35),
            _obs(PriorSource.PEERINGDB, "1", 53.4, -6.35),
        ],
    )
    assert single.corroboration is Corroboration.SINGLE_SOURCE
    assert both.corroboration is Corroboration.CORROBORATED


def test_haversine_is_metres() -> None:
    # One degree of latitude is ~111 km.
    assert haversine_m(0.0, 0.0, 1.0, 0.0) == pytest.approx(111_195, rel=0.01)


# --- the assembled register ----------------------------------------------------------------


def test_register_round_trips_offline(priors_settings: Settings) -> None:
    record = build_register(
        generated_at="2026-08-01", aoi_slugs=["queretaro"], settings=priors_settings
    )
    assert record.scope == "seeded"
    assert record.candidates
    assert record.corroborated
    # Every entry relays a published register, so every entry is [reference] — never [verified].
    assert {c.tag for c in record.candidates} == {"reference"}
    assert all(c.scene_ids == [] for c in record.candidates)
    # The licence audit rides in the artifact, not only in a README.
    licenses = {t.license for t in record.sources}
    assert licenses == {PEERINGDB_LICENSE, OSM_LICENSE}


def test_register_is_deterministic(priors_settings: Settings) -> None:
    """Same priors + same stamp → byte-identical artifact, so a re-run is a no-op in git."""
    a = build_register(generated_at="2026-08-01", aoi_slugs=["queretaro"], settings=priors_settings)
    b = build_register(generated_at="2026-08-01", aoi_slugs=["queretaro"], settings=priors_settings)
    assert a.model_dump(mode="json") == b.model_dump(mode="json")
    assert render_register(a) == render_register(b)


def test_swept_aoi_is_recorded_even_when_thin(priors_settings: Settings) -> None:
    """Negative/thin results are results — the AOI row exists with its raw counts regardless."""
    record = build_register(
        generated_at="2026-08-01", aoi_slugs=["queretaro"], settings=priors_settings
    )
    (result,) = record.aois
    assert result.slug == "queretaro"
    assert result.selection_basis  # the locked "follow the operators" driver, restated per AOI
    assert set(result.observations_by_source) == {"peeringdb", "osm"}


def test_prose_escapes_pipes_in_register_supplied_names() -> None:
    """A register name containing `|` (OSM has one) must not shift the markdown table's columns."""
    from watermark.international.model import CandidatesRegister

    candidate = build_candidate(
        aoi="dublin",
        country="IE",
        observations=[
            _obs(PriorSource.OSM, "way/1", 53.4, -6.35, name="Keppel | Keppel DC Dublin 1"),
            _obs(PriorSource.PEERINGDB, "1", 53.4, -6.35, name="Keppel", operator="Keppel"),
        ],
    )
    text = render_register(
        CandidatesRegister(
            scope="t",
            generated_at="2026-08-01",
            corroboration_radius_m=250.0,
            candidates=[candidate],
        )
    )
    assert "Keppel \\| Keppel DC Dublin 1" in text


def test_register_path_is_outside_every_site_collection() -> None:
    """The register belongs to no watershed point; filing it under one would fold an international
    candidate into that site's record."""
    settings = Settings()
    path = register_path(settings, "seeded")
    assert path.parent.name == "international"
    assert path.name == "data-center-candidates.seeded.yaml"
