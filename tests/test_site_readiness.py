"""Tests for domain-activation readiness (#1220 / #1221).

The readiness model is *additive*: a site is the domains that actually have a story there,
each ``absent | seeded | live`` from ``(SiteProfile, feed counts)`` alone, with a single tier
derived from that vector. These tests pin the five canonical shapes named in the epic —
Lima (``reference``), Fort Wayne + Urbana (``case``), a backdrop-staged site (``backdrop``),
and a stub (``stub``) — plus the per-domain predicate boundaries.
"""

from __future__ import annotations

import pytest

from watermark.site.readiness import (
    BACKDROP_FLOOR_FEEDS,
    DOMAINS,
    INQUIRY_LIVE_THRESHOLD,
    INQUIRY_SEED_THRESHOLD,
    RECORD_KEYED_CHAPTERS,
    RECORD_LIVE_THRESHOLD,
    compute_readiness,
    domain_states,
    site_tier,
)
from watermark.sites import SITES, ItLoadGrounding, is_reference_site

# A full floor — every always-pull feed present (so backdrop is live).
FLOOR = dict.fromkeys(BACKDROP_FLOOR_FEEDS, 1)


def _counts(**extra: int) -> dict[str, int]:
    """Feed counts with the floor present by default; override/extend with kwargs."""
    return {**FLOOR, **extra}


# --- backdrop -------------------------------------------------------------------------------
def test_backdrop_live_seeded_absent() -> None:
    prof = SITES["findlay"]
    assert domain_states(prof, _counts())["backdrop"] == "live"
    # Only one floor feed → seeded.
    partial = {BACKDROP_FLOOR_FEEDS[0]: 1}
    assert domain_states(prof, partial)["backdrop"] == "seeded"
    # No floor feeds → absent.
    assert domain_states(prof, {})["backdrop"] == "absent"


# --- facility -------------------------------------------------------------------------------
def test_facility_states() -> None:
    # Facility readiness grades on DOCUMENTARY DEPTH (#1630), independent of the demand-pressure
    # feed: instrument-grounded → live, screening/announcement → seeded, facility-less → absent.
    # The feed no longer floats facility — pass it in or not, the grade is the same.
    # Permit-grounded → live (Fort Wayne's IDEM Title V); feed presence is now irrelevant.
    fw = SITES["fort-wayne"]
    assert fw.facility is not None and fw.facility.it_load_grounding is ItLoadGrounding.PERMIT
    assert domain_states(fw, _counts())["facility"] == "live"
    assert domain_states(fw, _counts(**{"economics-demand-pressure": 1}))["facility"] == "live"
    # Filed-disclosure-grounded → live (Findlay's SEC S-1: 30 MW operating / 150 MW take-or-pay).
    findlay = SITES["findlay"]
    assert findlay.facility is not None
    assert findlay.facility.it_load_grounding is ItLoadGrounding.DISCLOSURE
    assert domain_states(findlay, _counts())["facility"] == "live"
    # Screening-only [inference] → seeded (Urbana's floor-area bracket, MW [open], #1327). No longer
    # floated to `live` by its demand-pressure feed — distinguished from Lima / Fort Wayne (#1630).
    urbana = SITES["urbana"]
    assert urbana.facility is not None
    assert urbana.facility.it_load_grounding is ItLoadGrounding.SCREENING
    assert (
        domain_states(urbana, _counts(**{"economics-demand-pressure": 1}))["facility"] == "seeded"
    )
    # Announced-ceiling [reference] → seeded (Springfield's 5C FAQ / AMD supercluster announcement).
    springfield = SITES["springfield"]
    assert springfield.facility is not None
    assert springfield.facility.it_load_grounding is ItLoadGrounding.REFERENCE
    assert (
        domain_states(springfield, _counts(**{"economics-demand-pressure": 1}))["facility"]
        == "seeded"
    )
    # No facility disclosed → absent (grid backdrop only, no fabricated campus load share).
    xenia = SITES["xenia"]
    assert xenia.facility is None
    assert domain_states(xenia, _counts(**{"economics-demand-pressure": 1}))["facility"] == "absent"


def test_facility_grading_distinguishes_permit_from_screening() -> None:
    """The #1630 acceptance: a permit-grounded and a screening-only facility produce DISTINGUISHABLE
    readiness (they collapsed to one ``live`` label before). Same floor, same (irrelevant) feeds —
    only the facility grade differs, driven by the profile's own documentary depth."""
    counts = _counts(**{"economics-demand-pressure": 1})
    permit = SITES["lima"]  # air-permit-grounded (OEPA PTI)
    screening = SITES["urbana"]  # floor-area [inference] screening, MW [open]
    assert permit.facility is not None and permit.facility.is_instrument_grounded
    assert screening.facility is not None and not screening.facility.is_instrument_grounded
    assert domain_states(permit, counts)["facility"] == "live"
    assert domain_states(screening, counts)["facility"] == "seeded"
    assert domain_states(permit, counts)["facility"] != domain_states(screening, counts)["facility"]


# --- places ---------------------------------------------------------------------------------
def test_places_states() -> None:
    prof = SITES["urbana"]
    # Committed campus geometry exported → live.
    assert domain_states(prof, _counts(**{"geo/campus": 5}))["places"] == "live"
    # Place records without footprint geometry → seeded.
    assert domain_states(prof, _counts(places=3))["places"] == "seeded"
    # Neither → absent (even though gis_parcel is set — the statewide schema does not gate).
    assert prof.gis_parcel is not None
    assert domain_states(prof, _counts())["places"] == "absent"


# --- record ---------------------------------------------------------------------------------
def test_record_threshold() -> None:
    prof = SITES["urbana"]
    assert domain_states(prof, _counts())["record"] == "absent"
    # Below the live threshold → seeded.
    assert domain_states(prof, _counts(records=RECORD_LIVE_THRESHOLD - 1))["record"] == "seeded"
    # At/above threshold on extracted records → live.
    assert domain_states(prof, _counts(records=RECORD_LIVE_THRESHOLD))["record"] == "live"


def test_record_live_requires_extracted_records_not_catalogued_scans() -> None:
    # `documents` counts source-scan COLLECTION dirs (one row each), not extracted content, so a
    # site with raw scans in ≥2 collections but zero extractions must NOT read as a live record —
    # catalogued-but-unworked scans seed the domain; they never lift it (#1364).
    prof = SITES["urbana"]
    assert domain_states(prof, _counts(documents=2))["record"] == "seeded"
    assert domain_states(prof, _counts(documents=9))["record"] == "seeded"
    # One extracted record plus its catalogued source is still below the two-item live bar → seeded.
    assert domain_states(prof, _counts(records=1, documents=1))["record"] == "seeded"


def test_record_excludes_network_global_boilerplate() -> None:
    # concepts/defense-contractors ship on every bundle, and the entities feed merges the
    # network-global defense-contractor cross-match (General Dynamics on every site) — none of
    # them may float the record domain to live. Only the corpus-scoped records/documents count.
    prof = SITES["findlay"]
    counts = _counts(concepts=8, entities=2, **{"defense-contractors": 1})
    assert domain_states(prof, counts)["record"] == "absent"


# --- inquiry (#1971) ------------------------------------------------------------------------
def _study(substantive: int, *, record_backed: bool) -> dict[str, str]:
    """A synthetic chapter → verdict map with ``substantive`` answered chapters.

    The record-keyed pair (``assembly``/``governance``) is answered or gapped explicitly, and any
    remaining substantive count is padded with connector-shaped chapter ids — which is exactly the
    shape the predicate has to tell apart.
    """
    out: dict[str, str] = {}
    remaining = substantive
    for chapter in RECORD_KEYED_CHAPTERS:
        if record_backed and remaining > 0:
            out[chapter], remaining = "partial", remaining - 1
        else:
            out[chapter] = "gap"
    padding = [
        "method",
        "labor",
        "missing",
        "project",
        "power",
        "discharge",
        "balance",
        "air",
        "heat",
        "groundwater",
        "stormwater",
        "water-supply",
        "fiscal",
    ]
    for chapter in padding:
        out[chapter] = "data" if remaining > 0 else "gap"
        remaining -= 1 if remaining > 0 else 0
    return out


def test_inquiry_needs_the_study_to_answer_over_a_record_that_exists() -> None:
    """``live`` takes BOTH a substantive count and a record-keyed chapter that answered."""
    prof = SITES["van-wert"]
    live = _study(INQUIRY_LIVE_THRESHOLD, record_backed=True)
    assert domain_states(prof, _counts(), live)["inquiry"] == "live"
    # Same count, but nothing the site's OWN corpus grounds → seeded, never live. This is the
    # springfield case the whole rename exists for: nine of the fifteen chapters derive from
    # connector pulls and the facility profile, so a site with zero records can post a respectable
    # count without its record having said anything.
    assert (
        domain_states(prof, _counts(), _study(INQUIRY_LIVE_THRESHOLD, record_backed=False))[
            "inquiry"
        ]
        == "seeded"
    )
    # Record-backed but thin → seeded.
    assert domain_states(prof, _counts(), _study(2, record_backed=True))["inquiry"] == "seeded"
    # One under the live bar, record-backed → still seeded (the threshold is a real boundary).
    assert (
        domain_states(prof, _counts(), _study(INQUIRY_LIVE_THRESHOLD - 1, record_backed=True))[
            "inquiry"
        ]
        == "seeded"
    )


def test_inquiry_is_absent_without_a_study_at_all() -> None:
    """No study to read degrades to ``absent`` — it never guesses from the other domains."""
    prof = SITES["lima"]
    assert domain_states(prof, _counts(leads=14), None)["inquiry"] == "absent"
    assert domain_states(prof, _counts(leads=14), {})["inquiry"] == "absent"
    # A study that answers nothing is absent too, however many chapters it ships.
    assert domain_states(prof, _counts(), _study(0, record_backed=False))["inquiry"] == "absent"
    # …and below the seed bar with no record-keyed answer stays absent.
    assert (
        domain_states(prof, _counts(), _study(INQUIRY_SEED_THRESHOLD - 1, record_backed=False))[
            "inquiry"
        ]
        == "absent"
    )


def test_inquiry_no_longer_reads_leads_or_authored_prose() -> None:
    """The two signals the retired ``story`` domain ran on are both inert now (#1971).

    This is the regression pin on the finding: a site could reach a higher tier by committing a
    leads YAML and registering an unreadable walk, and could not move it with a worked corpus.
    """
    prof = SITES["lima"]
    study = _study(INQUIRY_LIVE_THRESHOLD, record_backed=True)
    assert domain_states(prof, _counts(leads=0), study)["inquiry"] == "live"
    assert domain_states(prof, _counts(leads=99), study)["inquiry"] == "live"
    # And leads alone buy nothing at all.
    assert domain_states(prof, _counts(leads=99), {})["inquiry"] == "absent"


def test_inquiry_never_gates_the_tier() -> None:
    """The tier reads the four record-bearing domains; ``inquiry`` is reported beside them."""
    prof = SITES["fort-wayne"]
    counts = _counts(**{"geo/campus": 1, "records": 9, "documents": 4})
    answered = compute_readiness(prof, counts, _study(INQUIRY_LIVE_THRESHOLD, record_backed=True))
    silent = compute_readiness(prof, counts, None)
    assert answered["tier"] == silent["tier"], "inquiry must not move the tier"
    assert answered["domains"]["inquiry"] == "live"  # type: ignore[index]
    assert silent["domains"]["inquiry"] == "absent"  # type: ignore[index]


# --- the five canonical tiers ---------------------------------------------------------------
def test_tier_reference_lima() -> None:
    lima = SITES["lima"]
    counts = _counts(
        **{"economics-demand-pressure": 1, "geo/campus": 2},
        records=5,
        documents=2,
        leads=14,
    )
    states = domain_states(lima, counts, _study(INQUIRY_LIVE_THRESHOLD, record_backed=True))
    assert all(states[d] == "live" for d in DOMAINS), states
    assert site_tier(states) == "reference"
    # And the tier does not depend on that study: `reference` is the four record-bearing domains.
    assert site_tier(domain_states(lima, counts)) == "reference"


def test_tier_reference_fort_wayne_after_dropping_the_story_gate() -> None:
    # Fort Wayne is one of the two sites #1971 PROMOTES, and it reads as the honest new value
    # rather than a loosened assertion: all four record-bearing domains are live, and the only
    # thing that had been holding it at `case` was the retired `story` domain — which it could
    # have cleared by committing a leads YAML (#1457 was literally that issue).
    fw = SITES["fort-wayne"]
    counts = _counts(**{"economics-demand-pressure": 1, "geo/campus": 11}, records=3, documents=1)
    states = domain_states(fw, counts)
    assert states["facility"] == "live"
    assert states["places"] == "live"
    assert states["record"] == "live"
    assert site_tier(states) == "reference"


def test_tier_case_via_record_only() -> None:
    # A single above-floor domain (record) live over the floor is enough for `case`.
    fw = SITES["fort-wayne"]
    states = domain_states(fw, _counts(records=2))
    assert states["record"] == "live"
    assert site_tier(states) == "case"


def test_tier_case_urbana() -> None:
    # Urbana's real shape (#1327 / #1328): the floor, plus a committed parcel footprint (places
    # live, geo/campus) and its scoped Highland55 / OEPA document corpus (record live). The
    # disclosed Urbana Technology Hub facility is SCREENING-only ([inference] floor-area load, MW
    # [open]) → facility `seeded`, not live (#1630) — its demand-pressure feed no longer floats it.
    # Places + record live over the floor still ⇒ `case`. `inquiry` is not passed here and so reads
    # `absent` (#1971) — the tier must not care either way, which is the point.
    urbana = SITES["urbana"]
    states = domain_states(
        urbana,
        _counts(
            **{"geo/campus": 5, "economics-demand-pressure": 1}, records=3, documents=2, leads=1
        ),
    )
    assert states["record"] == "live"
    assert states["places"] == "live"
    assert (
        states["facility"] == "seeded"
    )  # screening-only, distinguished from permit-grounded (#1630)
    assert states["inquiry"] == "absent"
    assert site_tier(states) == "case"


def test_tier_backdrop_leads_only() -> None:
    # The floor-plus-a-leads-board-only shape: no facility, no structured corpus, no committed
    # parcels. record/places/facility absent, so the tier is `backdrop`. A leads board buys NOTHING
    # now (#1971): it fed the retired `story` domain, and a site could once ride it to a higher
    # tier. (Springfield was this shape pre-#1412; Xenia carries it now.)
    xenia = SITES["xenia"]
    assert xenia.facility is None
    states = domain_states(xenia, _counts(leads=2))
    assert states["record"] == "absent"
    assert states["places"] == "absent"
    assert states["facility"] == "absent"
    assert states["inquiry"] == "absent", "a leads board is not an answered study"
    assert site_tier(states) == "backdrop"


def test_tier_backdrop_staged() -> None:
    # Floor on disk, nothing above → backdrop. Uses xenia (facility=None) —
    # Findlay now carries a disclosed SiteFacility (#1459), so it is a Case site, not a backdrop one.
    prof = SITES["xenia"]
    states = domain_states(prof, _counts())
    assert states["backdrop"] == "live"
    assert all(states[d] == "absent" for d in DOMAINS if d != "backdrop")
    assert site_tier(states) == "backdrop"


def test_tier_stub() -> None:
    # No floor feeds at all → stub, regardless of profile.
    prof = SITES["coshocton"]
    states = domain_states(prof, {})
    assert states["backdrop"] == "absent"
    assert site_tier(states) == "stub"


# --- compute_readiness block + invariants ---------------------------------------------------
def test_compute_readiness_block_shape() -> None:
    block = compute_readiness(SITES["xenia"], _counts(leads=2))
    assert set(block) == {"domains", "tier"}
    assert set(block["domains"]) == set(DOMAINS)  # type: ignore[arg-type]
    assert block["tier"] == "backdrop"


def test_reference_tier_is_not_the_reference_role() -> None:
    # A stub Lima-shaped bundle is still `stub` — the readiness tier is derived from data, not
    # from the network-global-host role. is_reference_site stays a separate, role-only flag.
    assert is_reference_site("lima")
    assert site_tier(domain_states(SITES["lima"], {})) == "stub"


@pytest.mark.parametrize("slug", ["lima", "fort-wayne", "urbana", "findlay", "coshocton"])
def test_domain_states_total_and_pure(slug: str) -> None:
    states = domain_states(SITES[slug], _counts())
    assert set(states) == set(DOMAINS)
    assert all(v in ("absent", "seeded", "live") for v in states.values())
