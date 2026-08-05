"""Site readiness by **domain activation** — the SSOT the frontend reads (#1220 / #1221).

The BOSC network is *additive*, not *subtractive*: a site is defined by the **domains that
actually have a story there**, not by its deficits against Lima's full ~10-section taxonomy.
This module classifies a site into five domains, each in one of three states
(``absent | seeded | live``), from ``(SiteProfile, feed counts)`` alone — no hardcoded
Lima/Allen values — and derives a single site **tier** from that vector.

It is the Python peer of ``web/packages/core/src/readiness.ts``. Here it is import-only; #1222 wires it
into ``watermark export`` so the computed block is written into ``manifest.json`` and the
frontend becomes a thin reader (#1223). Because the readiness is recomputed at every export,
it is a **standing** property — it goes up when a source lands and down when one dries up,
without re-running ``onboard``.

The domain model (the two problems #1220 fixes — see the epic):

============  ================================================  =========================
domain        live when                                         signal
============  ================================================  =========================
**backdrop**  every always-pull floor feed present              floor feeds (FIPS/state/grid)
**facility**  ``SiteProfile.facility`` instrument-grounded      profile facility grounding
**places**    committed campus **or** enclave geometry          ``geo/campus``/``geo/enclave``
**record**    extracted corpus over threshold                   records+documents+entities
**inquiry**   the study ANSWERS, over a record that exists      ``impact-study`` verdicts
============  ================================================  =========================

``inquiry`` was called ``story`` until #1971 (epic #1968), and the rename is the point rather than
cosmetic. Its predicate was ``slug in STORY_SLUGS and leads`` — a hand-maintained Python mirror of a
TypeScript overlay of MDX directories. **It was the only domain whose signal was "did a human author
prose."** It measured editorial output, it gated the tier, and so it made a walk the price of a
site's fifth domain: van-wert carried three merged investigations and read ``absent``, while findlay
read ``live`` for a walk that was ``comingSoon`` and could not be opened.

It now measures whether the site's own study **answers**, from the ``impact-study`` verdicts that
same export just computed — data the way every other domain is data. ``STORY_SLUGS`` is deleted;
the leads feed keeps its own facet signal and is no longer ANDed in.

Two conditions, and the second is what makes it about the record:

* a substantive count — chapters reading ``data`` or ``partial``, and
* **record-backed** — at least one of the two corpus-keyed chapters (``assembly`` / ``governance``,
  #1969) is itself substantive.

The second exists because the count alone is not a record signal. Nine of the fifteen chapters
derive from connector pulls, the facility profile and the grid backdrop, so springfield (zero
records) out-scored several worked corpora on count alone before #1969 landed the two chapters that
read the corpus. Requiring one of those to be substantive is what keeps a floor-only pull from
reading as an answered study.

**It no longer gates the tier** (see :func:`site_tier`).

Facility is graded on **documentary depth** (#1630), not on one economics feed: a facility whose
load is grounded in a primary instrument (an air permit, or a filed disclosure) or whose cooling is
document-disclosed is ``live``; a facility on the record only by name / announcement / site-plan
SCREENING ([inference]) is ``seeded``. The old rule keyed ``live`` on the ``economics-demand-pressure``
feed, collapsing permit-grounded (Lima) and screening-only (Urbana) evidence onto one label.

The trigger *is* the evidence: nothing above the floor scaffolds. A partial site **locks**
the domains it lacks and asks for the source, per the repo's spine — never fabricate a value
to make a thin peer look complete.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, get_args

from watermark.sites import SiteProfile

# --- Vocabulary -----------------------------------------------------------------------------
State = Literal["absent", "seeded", "live"]
Domain = Literal["backdrop", "facility", "places", "record", "inquiry"]
Tier = Literal["stub", "backdrop", "case", "reference"]

DOMAINS: tuple[Domain, ...] = get_args(Domain)

# --- Activation signals (named constants so #1223 can mirror them exactly) -------------------
# The always-pull floor: the connectors keyed only by coordinates / county FIPS / state / the
# site's own EIA-861 utility number, so they carry zero curation and no fabrication risk.
# NASA-POWER climatology / Atlas-14 / WBD / SSURGO feed hydrology but emit no distinct floor
# feed of their own (``hydrology-scenarios`` is facility-gated), so RSEI stands as a FIPS-keyed
# floor signal alongside the two economic ones.
#
# ``grid`` joined the floor in #1642 (GP-E E1). The grid backdrop — *whose* utility serves the
# site, within which balancing authority, and how big each is — is a **property of the place**,
# not of any campus proposed on it: ``derive_grid_profile`` emits it with ``load_share=None`` for
# a facility-less site precisely so a thin peer still gets the real electric-service chain. It is
# the same always-pull shape as its neighbours here (state/utility-keyed connectors, no curation),
# and until now it was written only to a CLI reference file and never reached the site at all,
# which is why the frontend hardcoded Lima's denominators.
#
# These are object feeds, which serialize with ``count == 1`` when present — so ``_count(...) > 0``
# tests *presence*, and presence must mean *content*. The exporter drops a genuinely-empty
# inventory (``watermark.site.export``: an RSEI feed with zero facilities, an economic baseline
# with no sectors, a grid profile with zeroed utility/BA denominators) so it is absent, not a
# ``count == 1`` shell that floats backdrop to ``live`` on an empty inventory (#1364).
ECONOMICS_BASELINE_FEED = "economics-baseline"
CONSUMER_ENERGY_FEED = "consumer-energy"
RSEI_FEED = "rsei"
GRID_FEED = "grid"
BACKDROP_FLOOR_FEEDS: tuple[str, ...] = (
    ECONOMICS_BASELINE_FEED,
    CONSUMER_ENERGY_FEED,
    RSEI_FEED,
    GRID_FEED,
)

# The facility demand→price-pressure feed, present only where a facility is disclosed (#1220:
# "demand-pressure missing across 22 sites is not a gap — it's facility-gated"). Since #1630 this
# is the facility domain's **leaf feed** — the facility-facing data the frontend renders — NOT the
# Python live-trigger: ``_facility_state`` now grades on the profile's own facility evidence, and
# the frontend's thin reader gates the demand-pressure section on ``domainPresent(…, "facility")``
# plus ``hasFeed(FACILITY_FEED)`` so an active facility never opens an empty page. Kept in
# ``READINESS_FEED_NAMES`` so the coupling guard still catches a rename that would break that gate.
FACILITY_FEED = "economics-demand-pressure"

# Committed campus/footprint geometry (the exported parcel/footprint layer) vs. place *records*
# without geometry. ``gis_parcel`` is deliberately NOT the seeded signal: the statewide Ohio
# schema is set on nearly every profile (stubs included), so it does not discriminate — only
# actually-committed geometry (which surfaces as ``geo/campus``) or place records do.
PLACES_GEOMETRY_FEED = "geo/campus"
# The **non-CAMA** land path (#1664). ``places`` gated on ``geo/campus`` alone made the domain
# structurally unreachable for a federal enclave: a base is off the county tax rolls, so no
# county parcel layer will ever carry it and no amount of research would ever produce a parcel
# assemblage. That was a gap in the model, not a gap in the evidence — the DoD MIRTA site
# register carries the boundary, and committed register geometry activates the domain on exactly
# the same terms as committed parcel geometry: the trigger is still the evidence, and still
# geometry a map can actually be drawn from.
PLACES_ENCLAVE_FEED = "geo/enclave"
PLACES_GEOMETRY_FEEDS: tuple[str, ...] = (PLACES_GEOMETRY_FEED, PLACES_ENCLAVE_FEED)
PLACES_RECORD_FEED = "places"

# The per-site extracted **document corpus** — the genuinely site-scoped record feeds. Only
# ``records`` (extracted RecordItems) and ``documents`` (per-site DocumentCollectionItems) are
# corpus-scoped and clean. Deliberately EXCLUDED: ``entities`` (the entity feed merges the
# network-global defense-contractor cross-match — e.g. "General Dynamics" surfaces on every site —
# so it does not discriminate a real corpus), ``concepts`` and ``defense-contractors`` (both
# network-global boilerplate present on every bundle). A site with RSEI-derived facility entities
# but no document corpus is correctly a Backdrop site, not a record case.
#
# Only ``records`` (validated ``RecordItem``s — actual extracted content) can float the domain to
# ``live``. ``documents`` counts raw source scans by first-level COLLECTION dir (one row per
# collection, not per file — ``watermark.site.documents``), so it measures containers, not content:
# a thin site with un-extracted scans in ≥2 collection dirs would otherwise sum to ``live`` with
# zero extractions (#1364). Catalogued-but-unworked scans SEED the record domain; they never lift
# it — "let it lock and ask for the source" rather than read present-but-empty as complete.
RECORD_LIVE_FEED = "records"
DOCUMENTS_FEED = "documents"
RECORD_SEED_FEEDS: tuple[str, ...] = (RECORD_LIVE_FEED, DOCUMENTS_FEED)
# ``records`` at/above this is ``live``; any record signal below it is ``seeded``; nothing is
# ``absent``. Two extracted items is the "real worked corpus" bar (a lone stray extraction seeds).
RECORD_LIVE_THRESHOLD = 2

# The leads feed — the open-questions / source-solicitation board for the site. It keeps its own
# facet signal in the frontend and is deliberately NOT part of any domain predicate (#1971): ANDing
# it into the old ``story`` domain is what let a site reach a higher tier by committing a YAML file.
LEADS_FEED = "leads"

# --- The ``inquiry`` signal (#1971) ----------------------------------------------------------
# Study chapter verdicts that count as the study having said something. ``gap`` is content — the
# study renders the absence AS a finding and never locks — but it is not an answer, and ``na`` is
# the watch state for a site with no disclosed project.
SUBSTANTIVE_STATUSES: frozenset[str] = frozenset({"data", "partial"})
# The two corpus-keyed chapters (#1969) — the only ones whose verdict is screened against the
# site's OWN extracted records rather than a connector pull or the facility profile.
RECORD_KEYED_CHAPTERS: tuple[str, ...] = ("assembly", "governance")
# Substantive chapters needed for ``live``. Eight of fifteen is the bar that separates a worked
# corpus from a thin one on the committed cohort (van-wert 9, ottawa 7) — deliberately a plain
# count, because a RATIO would flatter a facility-less site: its project-dependent chapters read
# ``na`` and drop out of the denominator, so the hardest chapters would stop counting against it.
INQUIRY_LIVE_THRESHOLD = 8
# Substantive chapters needed for ``seeded`` without any record-keyed chapter — a floor-only site
# whose study still reports a real labor baseline and grid backdrop has said *something*.
INQUIRY_SEED_THRESHOLD = 5

# Every manifest feed name this module keys a domain on — the single enumerable coupling to the
# exporter's feed spec (``watermark.site.export``). ``export.py`` shares these very constants for
# the feeds it can name directly; the composed geo feed (``geo/campus``) can't, so this set is what
# ``tests/test_site_bundle.py`` asserts the exporter still produces — a rename in ``export.py``
# that skips ``readiness.py`` then drops a feed out of the produced set and fails the guard, rather
# than silently dropping every site's facility/backdrop to ``seeded`` with green tests (#1631).
READINESS_FEED_NAMES: frozenset[str] = frozenset(
    {
        *BACKDROP_FLOOR_FEEDS,
        FACILITY_FEED,
        *PLACES_GEOMETRY_FEEDS,
        PLACES_RECORD_FEED,
        *RECORD_SEED_FEEDS,
        LEADS_FEED,
    }
)


def _count(feed_counts: Mapping[str, int], name: str) -> int:
    """A feed's row count, 0 when absent."""
    return feed_counts.get(name, 0)


def _tri(present: int, total: int) -> State:
    """``live`` when all ``total`` signals present, ``seeded`` when some, ``absent`` when none."""
    if present >= total:
        return "live"
    return "seeded" if present > 0 else "absent"


def _backdrop_state(feed_counts: Mapping[str, int]) -> State:
    present = sum(1 for f in BACKDROP_FLOOR_FEEDS if _count(feed_counts, f) > 0)
    return _tri(present, len(BACKDROP_FLOOR_FEEDS))


def _facility_state(profile: SiteProfile) -> State:
    # No disclosed facility → absent (grid backdrop only, no fabricated campus load share).
    fac = profile.facility
    if fac is None:
        return "absent"
    # Documentary depth grades live vs seeded (#1630): an instrument-grounded facility — an air
    # permit / filed disclosure grounding the load, or a document-disclosed cooling mechanism —
    # reads `live`; a facility on the record only by name / announcement / site-plan SCREENING
    # ([inference]) reads `seeded`. Keyed on the profile's OWN facility evidence, not on the
    # presence of the demand-pressure feed (which the pre-#1630 rule collapsed permit and screening
    # onto — Urbana's floor-area [inference] and Lima's permit-grounded load both read `live`).
    return "live" if fac.is_instrument_grounded else "seeded"


def _places_state(feed_counts: Mapping[str, int]) -> State:
    # Committed campus parcels OR a committed federal-enclave boundary (#1664) — either is
    # drawable geometry for the place the site is about.
    if any(_count(feed_counts, f) > 0 for f in PLACES_GEOMETRY_FEEDS):
        return "live"
    # Place *records* without committed footprint geometry — some spatial signal, not enough
    # to draw the map with.
    return "seeded" if _count(feed_counts, PLACES_RECORD_FEED) > 0 else "absent"


def _record_state(feed_counts: Mapping[str, int]) -> State:
    # Live is gated on extracted content (``records``) alone; catalogued source scans
    # (``documents``, counted by collection dir) only ever seed the domain (#1364).
    if _count(feed_counts, RECORD_LIVE_FEED) >= RECORD_LIVE_THRESHOLD:
        return "live"
    seeded = any(_count(feed_counts, f) > 0 for f in RECORD_SEED_FEEDS)
    return "seeded" if seeded else "absent"


def _inquiry_state(study_statuses: Mapping[str, str] | None) -> State:
    """Whether this site's own study **answers** — ``impact-study`` verdicts, not authored prose.

    ``study_statuses`` maps a chapter id to its verdict. ``None`` means the caller had no study to
    read (a bundle predating the feed, or a synthetic fixture), which degrades to ``absent`` rather
    than guessing — the same "let it lock and ask for the source" rule the rest of this module runs.
    """
    if not study_statuses:
        return "absent"
    substantive = sum(1 for s in study_statuses.values() if s in SUBSTANTIVE_STATUSES)
    # Record-backed: the study says something the site's OWN extracted corpus grounds. Without
    # this, a site with zero records rides connector-derived chapters to a respectable count.
    record_backed = any(
        study_statuses.get(c) in SUBSTANTIVE_STATUSES for c in RECORD_KEYED_CHAPTERS
    )
    if record_backed and substantive >= INQUIRY_LIVE_THRESHOLD:
        return "live"
    if record_backed or substantive >= INQUIRY_SEED_THRESHOLD:
        return "seeded"
    return "absent"


def domain_states(
    profile: SiteProfile,
    feed_counts: Mapping[str, int],
    study_statuses: Mapping[str, str] | None = None,
) -> dict[Domain, State]:
    """Each domain's ``absent|seeded|live`` state for a site, from its profile + feed counts.

    ``feed_counts`` maps a manifest feed name to its row count (as the manifest's ``feeds[]``
    carry). Pure and deterministic per ``(profile, counts, study_statuses)`` — the same inputs the
    frontend reads back out of ``manifest.readiness``.

    ``study_statuses`` is optional **on purpose, and the default is load-bearing.** The exporter
    builds the ``impact-study`` feed by calling back into this function for the FACILITY state (the
    `project` chapter's probe reads it), so a mandatory study argument would close a cycle. It does
    not actually close, because ``inquiry`` is the only domain that reads the study and ``facility``
    reads the profile alone — so the exporter calls this once without a study to build the feed, and
    once with it to write the manifest block.
    """
    return {
        "backdrop": _backdrop_state(feed_counts),
        "facility": _facility_state(profile),
        "places": _places_state(feed_counts),
        "record": _record_state(feed_counts),
        "inquiry": _inquiry_state(study_statuses),
    }


# The domains the TIER is derived from (#1971). ``inquiry`` is reported beside them and never
# gates: the tier measures **the record a site has**, not how much of it has been written up. While
# the old ``story`` domain sat in this vector it was the terminal blocker on every site — so a tier
# moved when someone committed a leads YAML and registered an unreadable walk, and did NOT move for
# three merged investigations. A domain whose signal is derived FROM the other four (inquiry reads
# study verdicts, which read the feeds) would also double-count them if it gated.
TIER_DOMAINS: tuple[Domain, ...] = ("backdrop", "facility", "places", "record")


def site_tier(states: Mapping[Domain, State]) -> Tier:
    """Derive the site tier from its record-bearing domain vector (``TIER_DOMAINS``).

    * ``reference`` — every record-bearing domain live. This is the **readiness** tier and is
      distinct from ``is_reference_site`` (the network-global-host *role* — routed-hydrograph,
      hypothesis matrix, catalog, concepts), which is not a readiness backdoor.
    * ``case`` — the floor is live and at least one above-floor domain is live (Urbana:
      places+record).
    * ``backdrop`` — the floor is live but nothing above it is.
    * ``stub`` — not even the floor is live (profile only, ~zero data).

    ``inquiry`` is deliberately absent from every branch below. Dropping it promotes exactly two
    sites on the committed cohort — fort-wayne and wpafb, both already carrying all four
    record-bearing domains live — and demotes none.
    """
    if all(states[d] == "live" for d in TIER_DOMAINS):
        return "reference"
    if states["backdrop"] != "live":
        return "stub"
    above_floor = [d for d in TIER_DOMAINS if d != "backdrop"]
    if any(states[d] == "live" for d in above_floor):
        return "case"
    return "backdrop"


def compute_readiness(
    profile: SiteProfile,
    feed_counts: Mapping[str, int],
    study_statuses: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """The full readiness block: per-domain states + the derived tier.

    The shape #1222 writes into ``manifest.json`` and #1223 reads: ``{"domains": {...},
    "tier": ...}``.
    """
    states = domain_states(profile, feed_counts, study_statuses)
    return {"domains": dict(states), "tier": site_tier(states)}
