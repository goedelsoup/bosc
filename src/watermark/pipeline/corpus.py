"""The cross-document layer — load every committed extraction into one corpus.

Stages 1-2 produce per-document artifacts under ``data/extracted/**`` (one YAML
per deed, NPDES permit, or OPC page). Phase C reasons *across* them — a timeline,
an entity graph — so it first needs them all in memory as typed models. This
module is that loader: walk the extracted tree, classify each file by its content
shape (not just its name), and validate it back into the model that produced it.

Each loaded item is tagged with its ``rel_path`` (relative to ``data/extracted``)
so downstream analysis can cite the artifact it came from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from watermark.config import Settings, get_settings
from watermark.logging import get_logger
from watermark.models import (
    RENDER_ENVELOPE_KEYS,
    DeedExtraction,
    DmrExtraction,
    EpaExtraction,
    Estimate,
    EstimateSection,
    GeneralPermitExtraction,
    LineItem,
    MarkupLine,
    NpdesExtraction,
    NpdesTranscription,
    OPCSummary,
    PageExtraction,
    PlanExtraction,
    SosExtraction,
    WetlandExtraction,
)
from watermark.sites import (
    CorpusScope,
    CorpusScopeArg,
    active_profile,
    effective_corpus_scope,
)

log = get_logger(__name__)


def relpath_in_scope(rel: str, scope: CorpusScopeArg) -> bool:
    """Whether an extracted artifact's ``rel`` (relative to ``data/extracted``) is in ``scope``
    (#762/#780/#1505) — the shared predicate every read surface funnels through.

    ``scope`` is normally the :class:`~watermark.sites.CorpusScope` from
    :func:`~watermark.sites.effective_corpus_scope`; Lima's carries the peer-exclusion that keeps a
    sibling's slug-scoped records (``idem/fort-wayne/…``, ``oepa/troy-piqua/…``) out of the
    reference record. A legacy raw inclusion tuple — or ``None`` meaning the whole tree with no
    exclusion — is also accepted for tests and ad-hoc callers. Prefixes match as path *segments*:
    ``"fort-wayne"`` matches ``fort-wayne/…`` (but never ``fort-wayne-foo/…``).
    """
    if isinstance(scope, CorpusScope):
        return scope.contains(rel)
    return CorpusScope(include=scope).contains(rel)


def iter_meeting_artifacts(extracted_dir: Path, filename: str) -> list[Path]:
    """Every committed meeting artifact named ``filename``, across both site layouts (#1522).

    Meeting-holding bodies live in a body-slug namespace: Lima's six bodies stay flat at
    ``<body>/meetings/<filename>``; a peer's bodies nest one level deeper under the site slug at
    ``<site>/<body>/meetings/<filename>`` (:func:`watermark.civic.layout.meetings_dir`), which the
    peer's default corpus scope ``(slug,)`` owns for free. Two bounded globs cover exactly those
    one- and two-segment depths — cheaper and more precise than a ``**`` walk of the whole
    extracted tree, and independent of body count: the meeting read surfaces (timeline, committed
    summaries, entity fold-in) run this once, then gate each path through :func:`relpath_in_scope`,
    so a nested tree lands in **exactly one** site's scope. Returns a sorted, de-duplicated list.

    **The bounded globs are an assumption, and it is load-bearing** (#1839). They cover a prefix
    of exactly ONE or TWO segments before ``meetings/`` — which is precisely what
    :func:`watermark.civic.layout.meetings_dir` writes, for every site, today. A tree filed any
    deeper would be **silently invisible** here: no error, no warning, just a body that never
    reaches the timeline or the bundle. The concrete way that happens is a peer whose meetings are
    filed under a jurisdiction-prefixed collection rather than its site slug —
    ``idem/fort-wayne/<body>/meetings/`` is three segments — so if a future layout ever nests
    that way, widening the write path is not enough: this read path must widen with it, and
    :func:`assert_meeting_layout_depth` is the tripwire that says so.
    """
    hits = {
        *extracted_dir.glob(f"*/meetings/{filename}"),
        *extracted_dir.glob(f"*/*/meetings/{filename}"),
    }
    return sorted(hits)


# The prefix depths (segments before ``meetings/``) :func:`iter_meeting_artifacts` can see.
MEETING_LAYOUT_DEPTHS = (1, 2)


def assert_meeting_layout_depth(rel: str) -> None:
    """Raise unless ``rel`` (a ``…/meetings/<file>`` path relative to ``data/extracted``) sits at
    a depth :func:`iter_meeting_artifacts` actually globs (#1839).

    The two bounded globs there are an unstated contract with
    :func:`watermark.civic.layout.meetings_dir`; this makes it stated, and failing, rather than
    letting a mis-filed tree read as an empty one.
    """
    parts = rel.replace("\\", "/").strip("/").split("/")
    if "meetings" not in parts:
        raise ValueError(f"{rel!r} is not a meeting artifact path (no 'meetings' segment)")
    depth = parts.index("meetings")
    if depth not in MEETING_LAYOUT_DEPTHS:
        raise ValueError(
            f"meeting artifact {rel!r} has {depth} segment(s) before 'meetings/', but "
            f"iter_meeting_artifacts only globs {MEETING_LAYOUT_DEPTHS} — it would be silently "
            "invisible to the timeline, committed summaries and the bundle. Widen the globs in "
            "iter_meeting_artifacts together with watermark.civic.layout.meetings_dir."
        )
    # Both globs end `meetings/<filename>` — the artifact is a direct child. A sub-directory
    # (`meetings/archive/meeting-index.yaml`) is just as invisible as a too-deep prefix, and for
    # the same reason, so it fails the same way.
    if len(parts) - depth != 2:
        raise ValueError(
            f"meeting artifact {rel!r} is not a direct child of its 'meetings/' directory — "
            "iter_meeting_artifacts globs 'meetings/<filename>' exactly, so anything nested "
            "below it would be silently invisible."
        )


@dataclass(frozen=True)
class CorpusReject:
    """A file the classifier CLAIMED and the model then REJECTED — a defect, not noise."""

    rel: str
    kind: str
    error: str


class CorpusValidationError(RuntimeError):
    """Raised by ``load_corpus(strict=True)`` when any claimed artifact failed its model."""

    def __init__(self, rejects: list[CorpusReject]) -> None:
        self.rejects = rejects
        super().__init__(
            f"{len(rejects)} committed extraction(s) were claimed by the corpus classifier "
            "and then rejected by their model:\n"
            + "\n".join(f"  {r.kind:>18}  {r.rel}\n{' ' * 22}{r.error}" for r in rejects)
        )


@dataclass(frozen=True)
class Corpus:
    """All committed extractions, grouped by genre and tagged with their path.

    Each entry is a ``(rel_path, model)`` pair where ``rel_path`` is relative to
    ``data/extracted`` — the citable provenance for any cross-document finding.
    """

    deeds: list[tuple[str, DeedExtraction]] = field(default_factory=list)
    # Both envelopes declare `.permit`, which is all either consumer (`timeline._npdes_events`,
    # `entities._graph`) touches — the union costs them nothing.
    permits: list[tuple[str, NpdesExtraction | NpdesTranscription]] = field(default_factory=list)
    general_permits: list[tuple[str, GeneralPermitExtraction]] = field(default_factory=list)
    # Files the classifier CLAIMED and the model then REJECTED. They are still dropped from the
    # typed buckets — deliberately; one malformed artifact must not blind the whole layer — but
    # #1994 showed a WARNING log is not a report: a permit can sit in the `records` feed looking
    # present while it is absent from every model-driven feed. Recording them lets a test assert
    # the drop set is empty instead of grepping logs.
    rejected: list[CorpusReject] = field(default_factory=list)
    # Files no arm of `_classify` claimed. Expected and numerous (~81); kept only for counting.
    declined: list[str] = field(default_factory=list)
    dmr_records: list[tuple[str, DmrExtraction]] = field(default_factory=list)
    filings: list[tuple[str, SosExtraction]] = field(default_factory=list)
    actions: list[tuple[str, EpaExtraction]] = field(default_factory=list)
    wetlands: list[tuple[str, WetlandExtraction]] = field(default_factory=list)
    plans: list[tuple[str, PlanExtraction]] = field(default_factory=list)
    estimates: list[tuple[str, PageExtraction]] = field(default_factory=list)
    summaries: list[tuple[str, OPCSummary]] = field(default_factory=list)

    def __len__(self) -> int:
        return (
            len(self.deeds)
            + len(self.permits)
            + len(self.dmr_records)
            + len(self.filings)
            + len(self.actions)
            + len(self.wetlands)
            + len(self.plans)
            + len(self.estimates)
            + len(self.summaries)
            + len(self.general_permits)
        )
        # `rejected`/`declined` are deliberately NOT counted — they hold no models.

    def is_empty(self) -> bool:
        return len(self) == 0

    def rel_paths(self) -> list[str]:
        """Every loaded artifact's path, across all genres.

        Exists so a caller never has to iterate ``vars(corpus).values()`` and unpack each field
        as a ``(rel, model)`` pair — an idiom that broke the moment #1994 added ``rejected``
        (dataclasses) and ``declined`` (bare strings) beside the typed buckets. Loaded artifacts
        only: a rejected or declined file is deliberately absent, because this answers "what did
        the corpus take in", which is exactly the question a scope assertion is asking.
        """
        return [
            rel
            for group in (
                self.deeds,
                self.permits,
                self.general_permits,
                self.dmr_records,
                self.filings,
                self.actions,
                self.wetlands,
                self.plans,
                self.estimates,
                self.summaries,
            )
            for rel, _ in group
        ]


# The sentinel `_classify` returns for a file the corpus layer does not model. It is NOT
# `None`: "the loader never reached a decision" and "the loader decided this is not an
# extraction" must not be the same observation (#1994).
DECLINED = "_declined"


def _has_render_envelope(data: dict[str, Any]) -> bool:
    """Whether ``data`` was written by an extractor rather than transcribed by a person.

    Every render extraction is constructed as a ``DocExtraction`` subclass in Python and
    serialized by ``DocExtraction.to_yaml`` (``model_dump``), so all four required fields are
    present by construction — verified across every committed render extraction, including the
    older ones that predate ``image_pages_read`` (#613) and omit that key entirely. That is why
    this tests only the REQUIRED four: they are precisely the fields whose absence would fail
    ``NpdesExtraction`` anyway.
    """
    return RENDER_ENVELOPE_KEYS.issubset(data)


def _has_transcription_provenance(data: dict[str, Any]) -> bool:
    """Whether ``data`` carries a hand transcription's own provenance block.

    Two committed conventions, both accepted: ``meta.sources`` (a mapping of named sources, each
    with path + sha256 + url) and ``provenance.sources`` (a list of paths). This is a POSITIVE
    signal, deliberately — routing on "no render envelope" alone would let a genuinely malformed
    extractor output be silently reclassified as a transcription and loosely validated, trading a
    silent drop for a silent mislabel, which is the failure the DMR discriminator exists to
    prevent. A ``provenance:`` block WITHOUT ``sources`` is not this: ``oepa/ottawa/
    2PD00028.npdes.yaml`` has one (extractor/tags/summary) and is a full render extraction.
    """
    return any(
        isinstance(body := data.get(block), dict) and body.get("sources")
        for block in ("meta", "provenance")
    )


def _classify(data: Any) -> str:
    """Identify an extraction by its top-level keys (shape, not filename).

    Returns ``deed`` / ``npdes`` / ``npdes_transcribed`` / ``npdes_dmr`` / ``general_permit`` /
    ``sos`` / ``epa`` / ``wetland`` / ``plan`` / ``opc_page`` / ``opc_detail_legacy`` /
    ``opc_summary``, or :data:`DECLINED`.

    **Every arm is a positive shape test, and that is the point.** This used to end
    ``if "sub_estimates" in data or "meta" in data: return "opc_summary"``. Because
    :class:`~watermark.models.OPCSummary` defaults every field, *any* mapping with a ``meta:``
    block validated — so **71 of the 72** files that reached that arm (meeting indexes,
    ``commissioners/minutes/filename-map.yaml``, ``van-wert/water-watch.yaml``, grid project
    files, PRR response indexes) loaded into ``corpus.summaries`` as construction cost estimates.
    Nothing broke only because ``timeline._opc_events`` skips a summary with no ``meta.date`` and
    exactly one file in the tree has one — the real estimate. The first rename of an
    ``extracted_at`` / ``checked_on`` / ``generated_at`` key to ``date`` would put a fabricated
    "OPC estimate: …" event on a water-watch report's timeline (#1994). An OPC summary is now
    identified by ``sub_estimates:``, which is what an OPC summary is.
    """
    if not isinstance(data, dict):
        return DECLINED
    if "deed" in data:
        return "deed"
    if "permit" in data:
        # Both a document extraction (NpdesExtraction, read from a scanned PDF) and an
        # ECHO DMR effluent-record pull (`watermark dmr`, a derived API summary) key a
        # top-level `permit:` block. Require the full DMR shape (a top-level `meta:`, a
        # `permit:` mapping carrying `npdes_id`/`window`, and a `discharge_summary:`
        # mapping) before routing to the DMR kind — a looser check (e.g. bare
        # `"discharge_summary" in data`) could misroute a document extraction that
        # happens to carry an extra `discharge_summary` key, which would then fail
        # DmrExtraction validation and land right back in the silently-dropped bug this
        # discriminator exists to fix (#1492).
        permit_block = data.get("permit")
        is_dmr_pull = (
            "meta" in data
            and isinstance(permit_block, dict)
            and "npdes_id" in permit_block
            and "window" in permit_block
            and isinstance(data.get("discharge_summary"), dict)
        )
        # The DMR test runs FIRST and stays first: a DMR pull carries a top-level `meta:` and
        # would otherwise reach the transcription test below. (It has no `meta.sources`, so it
        # would fail that test too — but the ordering is the guarantee, not the accident.)
        if is_dmr_pull:
            return "npdes_dmr"
        # A permit read three ways, discriminated in the same idiom as the DMR split above
        # (#1994). The render envelope is checked first because it is the only one of the three
        # that is satisfied BY CONSTRUCTION for anything the extractor writes.
        if _has_render_envelope(data):
            return "npdes"
        # A STATEWIDE general permit is a framework instrument, not a facility discharge record:
        # no facility, no receiving water, no public-notice date, and its provenance is a
        # `provenance:` block over SEVERAL source PDFs. Routed to `npdes` it was rejected for a
        # `doc_id`/`dpi`/`source_path` describing a vision render that never happened — and the
        # rejection was a WARNING nobody read. Name the genre instead of mis-routing it.
        if data.get("kind") == "general_permit" and isinstance(data.get("provenance"), dict):
            return "general_permit"
        if _has_transcription_provenance(data):
            return "npdes_transcribed"
        # Neither: an incomplete render envelope with no transcription provenance is MALFORMED,
        # not a third genre. It routes to `npdes` and fails validation loudly, where
        # `Corpus.rejected` and its gate report it by name.
        return "npdes"
    if "filing" in data:
        return "sos"
    if "action" in data:
        return "epa"
    if "determination" in data:
        return "wetland"
    if "plan" in data:
        return "plan"
    if "estimate" in data:
        return "opc_page"
    if "estimate_template" in data:
        return "opc_detail_legacy"
    if "sub_estimates" in data:
        return "opc_summary"
    return DECLINED


def _estimate_from_legacy_page(
    name: str, page: dict[str, Any], template: dict[str, Any]
) -> Estimate:
    """Convert one ``page_*`` block of the hand-authored detail YAML to an Estimate.

    The detail file keeps its ``~approximate`` markers on disk (data discipline);
    the ``Number`` coercion turns them into ints here for computation. Nothing is
    rewritten — this is an in-memory view onto the generic shape.
    """
    sections = []
    for sec_name, body in (page.get("line_items") or {}).items():
        if not isinstance(body, dict):
            continue
        items = [LineItem.model_validate(it) for it in (body.get("items") or [])]
        sections.append(
            EstimateSection(
                name=sec_name,
                line_items=items,
                subtotal=body.get("subtotal"),
                note=body.get("note"),
            )
        )
    markups = []
    amount = page.get("contingency_and_inflation_25pct")
    if amount is not None:
        markups.append(
            MarkupLine(
                label="Contingency and inflation",
                rate=template.get("contingency_rate"),
                amount=amount,
            )
        )
    return Estimate(
        name=page.get("title") or name,
        profile="tetratech",
        sections=sections,
        construction_subtotal=page.get("construction_subtotal"),
        markups=markups,
        total=page.get("total"),
    )


def _load_legacy_opc_detail(rel: str, data: dict[str, Any], corpus: Corpus) -> None:
    """Load the bespoke hand-authored OPC detail YAML as PageExtractions."""
    template = data.get("estimate_template") or {}
    for key, page in data.items():
        if not key.startswith("page_") or not isinstance(page, dict) or "line_items" not in page:
            continue
        estimate = _estimate_from_legacy_page(key, page, template)
        pdf_page = int(page.get("pdf_page") or 1)
        corpus.estimates.append(
            (
                rel,
                PageExtraction(
                    doc_id=rel,
                    source_path=rel,
                    page_index=pdf_page - 1,
                    pdf_page=pdf_page,
                    dpi=300,
                    estimate=estimate,
                ),
            )
        )


def validate_npdes(kind: str, data: Any) -> NpdesExtraction | NpdesTranscription:
    """Validate a ``permit:``-keyed payload against the envelope ``kind`` names.

    The single place that decides render-vs-transcription, so no second reader of a
    ``*.npdes.yaml`` off disk can ever disagree with the corpus loader about what a permit is —
    which is how ``agent.tools._load_all_permits`` came to swallow a valid permit whole (#1994).

    ``kind`` is the caller's already-computed :func:`_classify` result rather than a second
    call on the same data: re-classifying was not just redundant, it opened a seam where this
    function could reach a different verdict than the branch that dispatched to it. Raises on
    any other ``kind`` — a mismatch is a programming error and belongs in ``Corpus.rejected``
    with everything else the loader could not take in, never silently skipped.
    """
    if kind == "npdes":
        return NpdesExtraction.model_validate(data)
    if kind == "npdes_transcribed":
        return NpdesTranscription.model_validate(data)
    raise ValueError(f"validate_npdes called with kind={kind!r}, not a permit kind")


def load_corpus(
    settings: Settings | None = None,
    *,
    scope: CorpusScopeArg | None = None,
    strict: bool = False,
) -> Corpus:
    """Load and validate every extraction under ``data/extracted`` into a Corpus.

    ``scope`` overrides the active site's corpus scope — pass :data:`watermark.sites.WHOLE_TREE`
    to audit every committed artifact in one pass, which the #1994 gate does because *validity is
    a property of the file*: a per-site sweep is blind to any path no registered site's scope
    claims.

    Files that fail to parse or validate are recorded and skipped (the corpus is a best-effort
    view; one malformed artifact must not blind the whole layer). ``strict=True`` turns a
    rejection into :class:`CorpusValidationError` instead.
    """
    settings = settings or get_settings()
    extracted = settings.extracted_dir
    # Per-site corpus scope (#762/#780): a non-Lima site reads only its own extracted collections,
    # so the cross-document feeds (timeline/entities/relationships) never inherit Lima's records.
    # The effective scope defaults to the site's own slug when unset (only Lima is whole-tree).
    scope = scope if scope is not None else effective_corpus_scope(active_profile(settings))
    corpus = Corpus()
    if not extracted.exists():
        log.warning("corpus.no_extracted_dir", path=str(extracted))
        return corpus

    for path in sorted(extracted.rglob("*.yaml")):
        rel = str(path.relative_to(extracted))
        if not relpath_in_scope(rel, scope):
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            log.warning("corpus.bad_yaml", path=rel, error=str(exc).splitlines()[0])
            continue
        kind = _classify(data)
        try:
            if kind == "deed":
                corpus.deeds.append((rel, DeedExtraction.model_validate(data)))
            elif kind in ("npdes", "npdes_transcribed"):
                corpus.permits.append((rel, validate_npdes(kind, data)))
            elif kind == "general_permit":
                corpus.general_permits.append((rel, GeneralPermitExtraction.model_validate(data)))
            elif kind == "npdes_dmr":
                corpus.dmr_records.append((rel, DmrExtraction.model_validate(data)))
            elif kind == "sos":
                corpus.filings.append((rel, SosExtraction.model_validate(data)))
            elif kind == "epa":
                corpus.actions.append((rel, EpaExtraction.model_validate(data)))
            elif kind == "wetland":
                corpus.wetlands.append((rel, WetlandExtraction.model_validate(data)))
            elif kind == "plan":
                corpus.plans.append((rel, PlanExtraction.model_validate(data)))
            elif kind == "opc_page":
                corpus.estimates.append((rel, PageExtraction.model_validate(data)))
            elif kind == "opc_detail_legacy":
                _load_legacy_opc_detail(rel, data, corpus)
            elif kind == "opc_summary":
                corpus.summaries.append((rel, OPCSummary.model_validate(data)))
            else:  # kind is DECLINED
                corpus.declined.append(rel)
                # DEBUG, not WARNING. ~81 files land here on every single load, and two ERRORs
                # buried in eighty-one WARNINGs is indistinguishable from zero ERRORs — which is
                # exactly how #1994 survived long enough to be found by a hand sweep.
                log.debug("corpus.declined", path=rel)
        except Exception as exc:
            # A file the classifier CLAIMED and the model then REJECTED is a defect, not noise.
            # The artifact is real, reviewed and committed; the drop makes it invisible to the
            # timeline, the entity graph and the yidam mirror while `watermark.site.records`
            # (which reads raw dicts) keeps publishing it into the `records` feed — so it LOOKS
            # PRESENT AND IS NOT (#1994).
            detail = str(exc).splitlines()[0]
            corpus.rejected.append(CorpusReject(rel=rel, kind=kind, error=detail))
            log.error(
                "corpus.invalid",
                path=rel,
                kind=kind,
                error=detail,
                hint="the classifier claimed this file; either fix the artifact or teach "
                "_classify to route it to a model that fits — do NOT invent envelope fields",
            )

    log.info(
        "corpus.loaded",
        deeds=len(corpus.deeds),
        permits=len(corpus.permits),
        dmr_records=len(corpus.dmr_records),
        filings=len(corpus.filings),
        actions=len(corpus.actions),
        wetlands=len(corpus.wetlands),
        plans=len(corpus.plans),
        estimates=len(corpus.estimates),
        summaries=len(corpus.summaries),
        general_permits=len(corpus.general_permits),
        declined=len(corpus.declined),
        rejected=len(corpus.rejected),
    )
    if corpus.rejected:
        log.error(
            "corpus.rejected",
            count=len(corpus.rejected),
            paths=[r.rel for r in corpus.rejected],
        )
        if strict:
            raise CorpusValidationError(corpus.rejected)
    return corpus
