"""Assemble the seeded international candidates register from the discovery priors (#1393 track A).

Track A of the epic's deliverable: the priors-driven half, which — unlike the pilot discovery
sweep — is **not** gated on the #1389 eval harness, because it adjudicates no pixels and
therefore has no precision/recall to measure. It relays what two independent open registers say
and reports where they agree.

The whole method is three steps, and the discipline lives in the middle one:

1. **Pull** both priors per AOI (:mod:`watermark.connectors.priors`) — PeeringDB by country,
   Overpass by bbox — and narrow the country-wide PeeringDB slice to the AOI window.
2. **Cluster** the rows by position: observations within :data:`~watermark.international.model.
   CORROBORATION_RADIUS_M` of a running centroid describe one facility. Independent-source
   agreement is what promotes a cluster from a lead to a *corroborated* candidate; two rows from
   the same register are one source, however many of them there are.
3. **Record everything, including the nothing.** Every AOI gets an :class:`AoiResult` with its
   raw per-source counts even when it yields no corroborated candidate, so a thin result reads as
   a thin result rather than as an unexamined place.

What this cannot do is worth stating plainly, because the register's usefulness depends on the
reader knowing it: two registers agreeing that a building exists is not evidence of its size, its
load, its cooling, its water, or its owner beyond what one of them wrote down. Those are the
questions the later funnel stages and the records ladder exist to answer, and until they run the
fields simply do not exist on the model.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from watermark.connectors.priors import (
    OSM_LICENSE,
    PEERINGDB_LICENSE,
    OsmDataCenter,
    PeeringDbFacility,
    fetch_osm_data_centers,
    fetch_peeringdb_facilities,
)
from watermark.international.aois import AOIS, Aoi
from watermark.international.model import (
    CORROBORATION_RADIUS_M,
    AoiResult,
    Candidate,
    CandidatesRegister,
    Corroboration,
    PriorObservation,
    PriorSource,
    SourceTerms,
    build_candidate,
    haversine_m,
)
from watermark.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from watermark.config import Settings

log = get_logger(__name__)

# The register lives outside every site's collection: it belongs to no watershed point, and
# filing it under one would make an international candidate part of that site's record.
REGISTER_DIR = "international"
DEFAULT_SCOPE = "seeded"

# The licence audit, as data — republished into the register so a consumer of the feed alone
# still has the terms (see `watermark.connectors.priors` for why each is what it is).
SOURCE_TERMS: tuple[SourceTerms, ...] = (
    SourceTerms(
        source=PriorSource.PEERINGDB,
        label="PeeringDB facility register",
        url="https://www.peeringdb.com/",
        license=PEERINGDB_LICENSE,
        attribution="PeeringDB",
        notes=(
            "Operator-maintained interconnection register. Structurally blind to single-tenant "
            "campuses with no carrier presence — an absence here is not evidence of absence."
        ),
    ),
    SourceTerms(
        source=PriorSource.OSM,
        label="OpenStreetMap (telecom=data_center / building=data_center) via Overpass",
        url="https://www.openstreetmap.org/",
        license=OSM_LICENSE,
        attribution="© OpenStreetMap contributors",
        notes=(
            "Crowd-sourced, so coverage is uneven between countries and an `operator=` tag is a "
            "mapper's reading of a sign, not a corporate filing."
        ),
    ),
)


def register_path(settings: Settings, scope: str = DEFAULT_SCOPE, *, suffix: str = "yaml") -> Path:
    """The committed register path for a scope (``…/international/data-center-candidates.<scope>.<ext>``)."""
    return settings.extracted_dir / REGISTER_DIR / f"data-center-candidates.{scope}.{suffix}"


# --- prior rows -> observations ------------------------------------------------------------


def _from_peeringdb(row: PeeringDbFacility, *, retrieved_at: str) -> PriorObservation:
    return PriorObservation(
        source=PriorSource.PEERINGDB,
        source_id=str(row.facility_id),
        url=row.url,
        latitude=row.latitude,
        longitude=row.longitude,
        name=row.name,
        operator=row.organization,
        address=row.address or row.city,
        country=row.country,
        license=PEERINGDB_LICENSE,
        retrieved_at=retrieved_at,
        network_count=row.net_count,
        exchange_count=row.ix_count,
    )


def _from_osm(row: OsmDataCenter, *, country: str, retrieved_at: str) -> PriorObservation:
    return PriorObservation(
        source=PriorSource.OSM,
        source_id=row.element,
        url=row.url,
        latitude=row.latitude,
        longitude=row.longitude,
        name=row.name,
        operator=row.operator,
        address=row.address,
        # `addr:country` is set by a minority of mappers; fall back to the AOI's country, which is
        # a property of the window we queried and so is not an inference about the feature.
        country=row.country or country,
        license=OSM_LICENSE,
        retrieved_at=retrieved_at,
    )


# --- clustering -----------------------------------------------------------------------------


def cluster_observations(
    observations: Iterable[PriorObservation], *, radius_m: float = CORROBORATION_RADIUS_M
) -> list[list[PriorObservation]]:
    """Match observations that describe the same facility, deterministically.

    **At most one row per source per cluster**, matched shortest-distance-first. That structural
    constraint, not the radius, is what makes this correct, and it was learned from the output:
    plain proximity clustering merged a Dublin business park into a single "candidate" carrying
    five different operators (eircom, Hibernia Atlantic, Digital Realty, EXA, AWS) and folded two
    *distinct* PeeringDB facilities into one row. Distance alone cannot separate genuinely
    adjacent data centers, and data centers are built adjacent to each other — that is what a
    cluster market *is*.

    The constraint holds because each register deduplicates itself at the facility level: two
    PeeringDB rows are two facilities, and two separately-drawn OSM features are two things a
    mapper chose to draw separately. Neither register's internal split is ours to overrule, so a
    cluster can only ever be "this register's row for X plus that register's row for X". A campus
    mapped as three OSM buildings therefore stays three candidates rather than becoming one — the
    honest reading, since nothing in the priors says they are one campus.

    Matching is greedy over cross-source pairs sorted by distance (ties broken on the stable
    source/id ordering), so the same rows always yield the same grouping, and the nearest true
    pair claims each other before a more distant near-miss can.
    """
    rows = sorted(observations, key=lambda o: (o.source.value, o.source_id))
    # Union-find over row indices; `sources` tracks each component's occupied sources so a merge
    # that would double up a source is refused.
    parent = list(range(len(rows)))
    sources: list[set[PriorSource]] = [{r.source} for r in rows]

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    pairs: list[tuple[float, int, int]] = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            if rows[i].source is rows[j].source:
                continue  # same register — by construction a different facility
            d = haversine_m(
                rows[i].latitude, rows[i].longitude, rows[j].latitude, rows[j].longitude
            )
            if d <= radius_m:
                pairs.append((d, i, j))
    pairs.sort()

    for _d, i, j in pairs:
        a, b = find(i), find(j)
        if a == b or sources[a] & sources[b]:
            continue
        parent[b] = a
        sources[a] |= sources[b]

    grouped: dict[int, list[PriorObservation]] = {}
    for idx, row in enumerate(rows):
        grouped.setdefault(find(idx), []).append(row)
    return list(grouped.values())


# --- sweep ------------------------------------------------------------------------------------


def sweep_aoi(
    aoi: Aoi,
    *,
    retrieved_at: str,
    radius_m: float = CORROBORATION_RADIUS_M,
    settings: Settings | None = None,
) -> tuple[list[Candidate], AoiResult]:
    """Pull both priors for one AOI and reduce them to candidates plus the AOI's own result row.

    Returns **every** cluster as a candidate, corroborated or not: a single-source row is a real
    lead and dropping it would hide the coverage difference between the registers, which is
    itself one of the more interesting things this sweep shows. The corroboration split rides on
    :attr:`Candidate.corroboration`, so a consumer chooses; the register never pre-filters.
    """
    from watermark.config import get_settings

    settings = settings or get_settings()

    # PeeringDB is queried per country (its own natural unit), then narrowed to the AOI window.
    facilities = [
        f
        for f in fetch_peeringdb_facilities(aoi.country, settings=settings)
        if aoi.contains(f.latitude, f.longitude)
    ]
    features = fetch_osm_data_centers(aoi.overpass_bbox, settings=settings)

    observations = [_from_peeringdb(f, retrieved_at=retrieved_at) for f in facilities]
    observations += [_from_osm(f, country=aoi.country, retrieved_at=retrieved_at) for f in features]

    candidates = [
        build_candidate(
            aoi=aoi.slug,
            country=aoi.country,
            observations=group,
        )
        for group in cluster_observations(observations, radius_m=radius_m)
    ]
    candidates.sort(key=lambda c: c.key)

    corroborated = sum(1 for c in candidates if c.corroboration is Corroboration.CORROBORATED)
    result = AoiResult(
        slug=aoi.slug,
        label=aoi.label,
        country=aoi.country,
        bbox=aoi.bbox,
        selection_basis=aoi.selection_basis,
        observations_by_source={
            PriorSource.PEERINGDB.value: len(facilities),
            PriorSource.OSM.value: len(features),
        },
        candidate_count=len(candidates),
        corroborated_count=corroborated,
    )
    log.info(
        "international.sweep",
        aoi=aoi.slug,
        peeringdb=len(facilities),
        osm=len(features),
        candidates=len(candidates),
        corroborated=corroborated,
    )
    return candidates, result


def build_register(
    *,
    generated_at: str,
    scope: str = DEFAULT_SCOPE,
    aoi_slugs: Sequence[str] | None = None,
    radius_m: float = CORROBORATION_RADIUS_M,
    settings: Settings | None = None,
) -> CandidatesRegister:
    """Sweep every requested AOI and assemble the committed register.

    ``generated_at`` is caller-supplied so a re-run over unchanged priors produces a byte-identical
    artifact — the same determinism rule the rest of the committed tree follows.
    """
    slugs = list(aoi_slugs) if aoi_slugs is not None else list(AOIS)
    candidates: list[Candidate] = []
    results: list[AoiResult] = []
    for slug in slugs:
        found, result = sweep_aoi(
            AOIS[slug], retrieved_at=generated_at, radius_m=radius_m, settings=settings
        )
        candidates.extend(found)
        results.append(result)
    candidates.sort(key=lambda c: (c.aoi, c.key))
    return CandidatesRegister(
        scope=scope,
        generated_at=generated_at,
        corroboration_radius_m=radius_m,
        aois=results,
        sources=list(SOURCE_TERMS),
        candidates=candidates,
    )


# --- IO -----------------------------------------------------------------------------------------


def load_register(path: Path) -> CandidatesRegister | None:
    """Load a committed register, or ``None`` when none has been assembled yet."""
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return CandidatesRegister.model_validate(raw)


def save_register(record: CandidatesRegister, path: Path) -> None:
    """Write the register as clean, deterministic YAML."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = record.model_dump(mode="json", exclude_none=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )


# --- prose ---------------------------------------------------------------------------------------


def _cell(text: str) -> str:
    """A value safe to drop in a markdown table cell.

    A bare ``|`` in a register-supplied name (OSM has "Keppel Data Centres | Keppel DC Dublin 1")
    silently splits the row into extra columns and shifts every later cell one place left, so the
    operator column ends up displaying a position. Escaped, not stripped: the pipe is part of the
    name the register published, and this file quotes registers verbatim.
    """
    return text.replace("|", "\\|")


def _operator_cell(candidate: Candidate) -> str:
    """The attribution as a table cell — a cited name, an explicit ``[open]``, or the competing
    claims spelled out when the sources disagree."""
    attribution = candidate.attribution
    if attribution.operator is None:
        return "`[open]`"
    lead = f"[{_cell(attribution.operator)}]({attribution.citation}) `[reference]`"
    if not attribution.is_contested:
        return lead
    others = "; ".join(
        f"[{_cell(c.operator)}]({c.citation}) ({c.source.value})" for c in attribution.contested
    )
    return f"**contested** — {lead} vs. {others}"


def render_register(record: CandidatesRegister) -> str:
    """Render the register's prose peer.

    Generated from the structured record rather than written beside it, so the two cannot drift —
    the failure the domestic funnel has to manage by hand (a prose register no code reads, next to
    a sidecar no reader reads). Regenerated by ``watermark candidates``; never hand-edit it.
    """
    corroborated = record.corroborated
    lines: list[str] = [
        "# International data-center candidates — seeded register",
        "",
        "<!-- GENERATED by `watermark candidates`. Do not hand-edit: the next run reverts it. -->",
        "",
        f"Assembled {record.generated_at} from open discovery priors "
        f"({len(record.aois)} AOIs, {len(record.candidates)} candidates, "
        f"{len(corroborated)} corroborated).",
        "",
        "## What this is",
        "",
        "The international peer of the domestic data-center sweep, and a **distinct artifact",
        "class** from it. The domestic register starts from an instrument — a permit, a deed, a",
        "council resolution — and imagery only watches what the record already proved. Abroad",
        "that channel mostly does not exist, so this register starts from open registers of the",
        "facilities themselves and reports **where two independent ones agree**.",
        "",
        "Every entry here is `[reference]`: it relays what published third-party registers say.",
        "Nothing in this file is `[verified]`, and nothing can be — no instrument about any of",
        "these facilities is held. No imagery has been adjudicated for this scope, so no entry",
        "carries a detection, a cooling type, or a scene id.",
        "",
        "**Operator attribution is cited or it is `[open]`.** Coordinates are unambiguous;",
        "attribution is the risk. Where neither register names an operator, the cell says so",
        "rather than guessing from a facility name.",
        "",
        "Two registers agreeing that a building exists says nothing about its size, its load, its",
        "cooling, its water draw, or its owner beyond the words one of them wrote down.",
        "",
        "## Method",
        "",
        f"Rows within **{record.corroboration_radius_m:.0f} m** of a cluster's running centroid",
        "are treated as describing one facility. That radius is a *stated screening parameter*,",
        "not a measurement: the two registers geocode differently, so some tolerance is required,",
        "and widening it would manufacture agreement by merging distinct neighbours.",
        "A cluster is **corroborated** when at least two *independent* sources place a facility",
        "there — two rows from the same register are one source, however many there are.",
        "",
        "## Sources",
        "",
        "| Source | Licence | Attribution | Known blind spot |",
        "| --- | --- | --- | --- |",
    ]
    for term in record.sources:
        lines.append(
            f"| [{term.label}]({term.url}) | {term.license} | {term.attribution} "
            f"| {term.notes or '—'} |"
        )

    lines += [
        "",
        "## AOIs swept",
        "",
        "Negative and thin results are listed here as results. An AOI that yielded nothing was",
        "still swept — the row is the evidence of that.",
        "",
        "| AOI | Country | PeeringDB rows | OSM rows | Candidates | Corroborated |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for aoi in record.aois:
        counts = aoi.observations_by_source
        lines.append(
            f"| {aoi.label} | {aoi.country} | {counts.get('peeringdb', 0)} "
            f"| {counts.get('osm', 0)} | {aoi.candidate_count} | {aoi.corroborated_count} |"
        )

    lines += ["", "### Why each AOI is in the sweep", ""]
    for aoi in record.aois:
        lines += [f"**{aoi.label}** — {aoi.selection_basis}", ""]

    negatives = record.negative_aois
    if negatives:
        lines += [
            "### Negative results",
            "",
            "Swept, no corroborated candidate: "
            + ", ".join(f"**{a.label}**" for a in negatives)
            + ". Recorded as a result, per the sweep skill — the priors were queried and the two",
            "registers did not agree anywhere inside the window.",
            "",
        ]

    lines += [
        "## Corroborated candidates",
        "",
        f"{len(corroborated)} of {len(record.candidates)} clusters are placed by both registers.",
        "",
        "| Candidate | AOI | Operator (cited, else `[open]`) | Position | Sources |",
        "| --- | --- | --- | --- | --- |",
    ]
    for candidate in corroborated:
        sources = ", ".join(s.value for s in candidate.sources)
        lines.append(
            f"| {_cell(candidate.name or candidate.key)} | {candidate.aoi} "
            f"| {_operator_cell(candidate)} "
            f"| {candidate.latitude:.5f}, {candidate.longitude:.5f} | {sources} |"
        )
    # Every block here closes with a blank and opens without one, so the next section's heading
    # always gets its required blank line and never two (markdownlint MD022 / MD012).
    lines.append("")

    contested = [c for c in record.candidates if c.attribution.is_contested]
    if contested:
        lines += [
            "### Contested attribution",
            "",
            f"{len(contested)} candidate(s) have sources naming **different** operators for the",
            "same location. The register keeps both claims rather than resolving them: a",
            "disagreement between two registers is usually an acquisition or a rebrand that they",
            "updated at different times, and 'usually' is not a basis for asserting a name.",
            "Read these as contested until a disclosure closes them.",
            "",
        ]
        for candidate in contested:
            attribution = candidate.attribution
            lead_source = attribution.source.value if attribution.source else "?"
            others = "; ".join(
                f"[{claim.operator}]({claim.citation}) ({claim.source.value})"
                for claim in attribution.contested
            )
            lines.append(
                f"- **{_cell(candidate.name or candidate.key)}** ({candidate.aoi}) — "
                f"[{attribution.operator}]({attribution.citation}) ({lead_source}) "
                f"vs. {others}"
            )
        lines.append("")

    single = len(record.candidates) - len(corroborated)
    lines += [
        "## Single-source leads",
        "",
        f"{single} clusters are placed by exactly one register. They are kept in the structured",
        "record (never dropped) because the coverage gap between the two registers is itself a",
        "finding: PeeringDB is blind to single-tenant campuses with no carrier presence, and OSM",
        "coverage varies sharply by country. A lead is not a candidate this register asserts.",
        "",
        "## What would move an entry forward",
        "",
        "- An operator disclosure or national registry entry naming the site — closes `[open]`",
        "  attribution with a citation.",
        "- Geospatial screening (#1391) and vision adjudication (#1392) — would attach a footprint,",
        "  a substation relationship, a construction phase, and a **cooling type**, and would move",
        "  the entry from `[reference]` to `[inference]`, carrying the scene ids it read.",
        "- Neither would make it `[verified]`. Only an instrument about the facility does that,",
        "  and this funnel is not a route to one.",
        "",
    ]
    # Blocks close with a blank, so the last one leaves a trailing empty line that the final
    # newline would double (markdownlint MD012). Strip, then terminate exactly once.
    return "\n".join(lines).rstrip("\n") + "\n"
