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
    RECORD_LIVE_THRESHOLD,
    STORY_SLUGS,
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


# --- story ----------------------------------------------------------------------------------
def test_story_states() -> None:
    lima = SITES["lima"]
    assert "lima" in STORY_SLUGS
    assert domain_states(lima, _counts(leads=14))["story"] == "live"
    # Registered story, no leads → seeded (Fort Wayne today).
    fw = SITES["fort-wayne"]
    assert "fort-wayne" in STORY_SLUGS
    assert domain_states(fw, _counts())["story"] == "seeded"
    # Both signals → live, even though the walk is HELD (#1466). Findlay registers the ``flagpole``
    # story as ``comingSoon`` in the ``sites.ts`` overlay because the site is not yet ``selectable``.
    # ``STORY_SLUGS`` mirrors the overlay's KEYS, not its readable subset, so the domain is live on
    # the evidence (a walk exists over this record) while the frontend's ``story`` facet — which
    # gates on ``surfacedStories`` — stays locked. That divergence is the design, not a drift.
    findlay = SITES["findlay"]
    assert "findlay" in STORY_SLUGS
    assert domain_states(findlay, _counts(leads=44))["story"] == "live"
    # And it is genuinely two-signal: drop the leads board and it falls back to seeded.
    assert domain_states(findlay, _counts())["story"] == "seeded"
    # Leads only, no registered story → seeded (Urbana's record/leads case).
    urbana = SITES["urbana"]
    assert "urbana" not in STORY_SLUGS
    assert domain_states(urbana, _counts(leads=2))["story"] == "seeded"
    # Neither → absent.
    assert domain_states(urbana, _counts())["story"] == "absent"


# --- the five canonical tiers ---------------------------------------------------------------
def test_tier_reference_lima() -> None:
    lima = SITES["lima"]
    counts = _counts(
        **{"economics-demand-pressure": 1, "geo/campus": 2},
        records=5,
        documents=2,
        leads=14,
    )
    states = domain_states(lima, counts)
    assert all(states[d] == "live" for d in DOMAINS), states
    assert site_tier(states) == "reference"


def test_tier_case_fort_wayne() -> None:
    # facility + places + record live; story seeded (no leads) → case.
    fw = SITES["fort-wayne"]
    counts = _counts(**{"economics-demand-pressure": 1, "geo/campus": 11}, records=3, documents=1)
    states = domain_states(fw, counts)
    assert states["facility"] == "live"
    assert states["places"] == "live"
    assert states["record"] == "live"
    assert states["story"] == "seeded"
    assert site_tier(states) == "case"


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
    # Story seeded on leads. Places + record live over the floor still ⇒ `case`.
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
    assert states["story"] == "seeded"
    assert site_tier(states) == "case"


def test_tier_backdrop_leads_only() -> None:
    # The floor-plus-a-leads-board-only shape: no facility, no structured corpus, no committed
    # parcels. record/places/facility absent, story seeded (leads) does NOT elevate to case, so the
    # tier is `backdrop`. (Springfield was this shape pre-#1412, before its 5C/Vultr facility was
    # pinned; Xenia carries it now — facility-less, corpus-less.)
    xenia = SITES["xenia"]
    assert xenia.facility is None
    states = domain_states(xenia, _counts(leads=2))
    assert states["record"] == "absent"
    assert states["places"] == "absent"
    assert states["facility"] == "absent"
    assert states["story"] == "seeded"
    assert site_tier(states) == "backdrop"


def test_tier_backdrop_staged() -> None:
    # Floor on disk, nothing above → backdrop. Uses xenia (facility=None, not in STORY_SLUGS) —
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
