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
    DeedExtraction,
    DmrExtraction,
    EpaExtraction,
    Estimate,
    EstimateSection,
    LineItem,
    MarkupLine,
    NpdesExtraction,
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
    """
    hits = {
        *extracted_dir.glob(f"*/meetings/{filename}"),
        *extracted_dir.glob(f"*/*/meetings/{filename}"),
    }
    return sorted(hits)


@dataclass(frozen=True)
class Corpus:
    """All committed extractions, grouped by genre and tagged with their path.

    Each entry is a ``(rel_path, model)`` pair where ``rel_path`` is relative to
    ``data/extracted`` — the citable provenance for any cross-document finding.
    """

    deeds: list[tuple[str, DeedExtraction]] = field(default_factory=list)
    permits: list[tuple[str, NpdesExtraction]] = field(default_factory=list)
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
        )

    def is_empty(self) -> bool:
        return len(self) == 0


def _classify(data: Any) -> str | None:
    """Identify an extraction by its top-level keys (shape, not filename).

    Returns one of ``deed`` / ``npdes`` / ``npdes_dmr`` / ``opc_page`` / ``opc_summary``,
    or ``None`` for anything that isn't a recognized extraction.
    """
    if not isinstance(data, dict):
        return None
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
        return "npdes_dmr" if is_dmr_pull else "npdes"
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
    if "sub_estimates" in data or "meta" in data:
        return "opc_summary"
    return None


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


def load_corpus(settings: Settings | None = None) -> Corpus:
    """Load and validate every extraction under ``data/extracted`` into a Corpus.

    Files that fail to parse or validate are logged and skipped (the corpus is a
    best-effort view; one malformed artifact must not blind the whole layer).
    """
    settings = settings or get_settings()
    extracted = settings.extracted_dir
    # Per-site corpus scope (#762/#780): a non-Lima site reads only its own extracted collections,
    # so the cross-document feeds (timeline/entities/relationships) never inherit Lima's records.
    # The effective scope defaults to the site's own slug when unset (only Lima is whole-tree).
    scope = effective_corpus_scope(active_profile(settings))
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
            elif kind == "npdes":
                corpus.permits.append((rel, NpdesExtraction.model_validate(data)))
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
            else:
                log.warning("corpus.unrecognized", path=rel)
        except Exception as exc:  # validation errors are per-file; keep loading the rest
            log.warning("corpus.invalid", path=rel, kind=kind, error=str(exc).splitlines()[0])

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
    )
    return corpus
