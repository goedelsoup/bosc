"""Export the committed extractions into typed record feeds.

Reads every ``data/extracted/**/*.yaml`` generically — by the shape of its
payload block, in the same idiom :mod:`watermark.pipeline.corpus` classifies by — and emits one
:class:`~watermark.site.feeds.RecordItem` per record. Reading off the raw dict (not the
Pydantic models) keeps this contractor-/genre-agnostic and preserves the ``~``
approximate marker verbatim, per the data discipline in CLAUDE.md. (The legacy
markdown ``render_record_pages`` peer was removed at the SSG-cutover cleanup, #603.)

The classifier is the site tier's own taxonomy, and it is **wider** than the corpus loader's:
:mod:`watermark.pipeline.corpus` routes a genre only where a Pydantic extraction model backs
it, whereas a record here is published from the raw payload. That gap is what let a site's
worked corpus go unpublished — Urbana's structured read of the Thor v. Urbana complaint and
its recorded land-assembly register were both real, cited extractions that no group claimed,
so the site shipped a zero-length ``records`` feed and a ``record`` domain that read `seeded`
over a corpus that was neither absent nor thin (#1724). A genre earns a group when the corpus
carries the artifact; it does not need an extractor to have produced it.

Classification runs three mechanisms, in this order, and the order is the safety property
(#1993). A **payload block** (``_BLOCK_TO_GROUP``) claims a file whose subject fields live under
one key. A **whole-document block** (``_WHOLE_DOC_BLOCK_TO_GROUP``) claims one whose subject is
spread across the top level, and publishes the document minus its envelope and this repo's own
working notes. Last, a ``meta.kind`` **value allowlist** (``_META_KIND_TO_GROUP``) claims the
genres no payload block can discriminate, because their identity lives in the envelope rather
than in a block name — a grid siting case, a filed tariff sheet. That third mechanism must never
be expressed as a ``meta`` entry in either block map: 77 committed extractions carry a top-level
``meta:`` dict, so such an entry would publish every meetings manifest, corpus index, completeness
audit, standing watch and site footprint in the tree, and steal both Fort Wayne IDEM permits and
the OPC summary out of their correct groups. The allowlist, evaluated last, is what makes the
mechanism safe.

What is deliberately *not* a record: the derived per-site models (``bosc-site-footprint.yaml``
— the profile's ``footprint_relpath`` input), the corpus indexes and manifests (``meta:`` +
``documents:``), the meetings pipeline's own machinery (the ``meetings`` feed already publishes
``meeting-summaries.yaml``, so a record would double-count the same evidence), the standing
watches, and the analysis digests (``kind:``/``subject:``/``provenance:``). Those are compiled
*from* the record or *about* it; publishing them as records would float a site's record domain on
its own scaffolding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import yaml

from watermark.logging import get_logger
from watermark.pipeline.corpus import relpath_in_scope
from watermark.site.feeds import Citation, Confidence, RecordGroup, RecordItem, RenderClass
from watermark.sites import CorpusScopeArg

log = get_logger(__name__)

# The corpus root, as it appears inside an extraction ``source_path``. Committed
# envelopes carry several shapes (see _normalize_source_rel).
_DOC_ANCHOR = "data/documents/"

# Single-payload-block genres: the block key carries the subject fields.
_BLOCK_TO_GROUP: dict[str, str] = {
    "deed": "deeds",
    "action": "permits-epa",
    "order": "enforcement",
    # An agency inspection / compliance-review report (#2077). NOT `enforcement`: an inspection
    # records a visit and imposes nothing, and the letters say so themselves — "The
    # recommendation(s) set out below are not Orders." Filing a recommendation under the
    # enforcement heading would present compliance assistance as an enforceable term, the same
    # misclassification `layoff_notice` and `statutory_notice` exist to prevent.
    "inspection": "inspections",
    "award": "finance",
    "permit": "permits-npdes",
    "filing": "permits-sos",
    "plan": "plans",
    # A WARN Act plant-closing / mass-layoff notice filed with a state workforce agency (#1460).
    # The key is `layoff_notice` and NOT the shorter `notice`, which the corpus already uses for
    # R.C. 1311.04 Notices of Commencement (`recorder/`, `legal/prr-mandamus/`). Those stay
    # unclaimed on purpose: claiming `notice` here would reclassify a mechanic's-lien filing as a
    # workforce instrument, which is precisely the misfiling this taxonomy exists to prevent.
    "layoff_notice": "labor",
    # An act of a LOCAL legislative body, journalled in its own minutes (#1438). Bowling Green's
    # record arrives almost entirely in this form: a county commissioners' resolution authorizing
    # a 75%/15-year tax exemption, a township trustees' roll call on an R.C. 519.12 rezoning, a
    # county planning commission's recommendation on the same application one step upstream. The
    # discriminator is the ACT, not its subject — a rezoning and a tax abatement are the same kind
    # of instrument voted by different boards — and the subject is carried in the payload's own
    # `subject_matter`. No existing group fits: `plans` is a plan document, `finance` (`award:`)
    # is a grant or contract award, and filing a land-use vote under either would present a
    # zoning act as something it is not.
    "resolution": "local-legislation",
    # A USACE Wetland Determination Data Form (Midwest regional supplement) — a dated field
    # delineation at one sampling point, read off the form's own page images: investigator,
    # coordinates, soil map unit, the three regulatory indicators, and the overall finding.
    # `determination:` is already a first-class genre one tier down — `watermark.pipeline.corpus`
    # routes it to `wetland` behind `WetlandExtraction` — and this classifier is supposed to be
    # WIDER than that loader, not narrower; the key was simply never added (#1993).
    # NOT `permits-epa`. That group is an agency ACTION and renders as "Permits — Ohio EPA /
    # USACE". The form is filled by the APPLICANT'S consultant, and this corpus's own copy
    # records a USACE field scientist disagreeing with its negative finding. Publishing it under
    # an agency heading would tell the reader the agency determined there is no wetland; it did
    # not. The corpus loader keeps `wetlands` a separate bucket from `actions` for this reason.
    "determination": "wetland-determinations",
    # A notice a party must SERVE or RECORD under a named R.C. section as a precondition to a
    # private act: an R.C. 1311.04 Notice of Commencement recorded before construction, an
    # R.C. 3735.671 / 5709.83 notice served on a school district before a tax exemption (#1993).
    # The discriminator is the ACT — a statutorily compelled notice — not its subject, which is
    # why a mechanic's-lien precondition and a school-district abatement notice share a group.
    # The key is `statutory_notice` and NOT the bare `notice`, for exactly the reason
    # `layoff_notice` is not `notice`: `notice:` is ALSO the public-notice block on an NPDES
    # permit read (`oepa/findlay/2PD00008.1abaf306.npdes.yaml` carries both `permit:` and
    # `notice:`). Claiming the short key would keep that permit in `permits-npdes` only by
    # accident of dict insertion order — an invariant invisible in this file and destroyed by
    # any future reordering. Two committed files were re-keyed instead; the ordering trick was
    # refused deliberately.
    "statutory_notice": "statutory-notices",
    # Two shapes of one act, both under R.C. 519.12: a zoning commission's own resolution
    # initiating or replacing a section of the township zoning text, and a docketed application
    # by a property owner that the commission takes up by motion and sets for hearing (#1993).
    # Both are `local-legislation` on that group's own discriminator — the ACT, not its subject —
    # and neither needs a group of its own. Each block carries its instrument's own `status`
    # (`proposed` / `pending`), hoisted INTO the block so a record can never read as enacted.
    # `zoning_application` and NOT the bare `application`: the corpus is full of other
    # applications (WPCLF/OWDA loan applications, air-permit applications), and a bare key would
    # sweep a loan application into the legislative group.
    "zoning_amendment": "local-legislation",
    "zoning_application": "local-legislation",
}
# OPC estimates are whole-document (summary/detail/page) — no single block key.
_OPC_KEYS = frozenset({"estimate", "sub_estimates", "estimate_template"})
# Whole-document genres: the subject is spread across the top level, so the payload is the
# document minus its envelope rather than one block (#1724).
#
#   `case`        — a filed court instrument's structured read. The `case:` block carries only
#                   the caption/court/docket; the substance (parties, counts, relief sought, the
#                   ordinance record recited) sits beside it, so keying the payload to the block
#                   would publish a docket stub and drop the filing.
#   `conveyances` — a recorded land-assembly register: one entry per deed (grantor → grantee,
#                   acres, consideration, Official-Record book/page). Deliberately NOT the
#                   `deeds` group, which is instrument-level — a per-deed vision read of a
#                   recorder PDF. A register is a compiled chain sourced to a county CAMA layer,
#                   and filing it under `deeds` would present it as an instrument read.
#   `sellers`     — the produced-instrument peer of `conveyances`: one entry per seller's
#                   option-to-purchase packet with grantor/grantee, acreage, parcel IDs and the
#                   assignment/closing chain, read off page images of a records production rather
#                   than a county CAMA layer. Same register genre, so the same group; keying to
#                   the block alone would drop the mechanism, the blank DTE-100 conveyance-fee
#                   finding, and the CAUV recoupment (#1993).
#   `zoning_code` — an adopted township zoning resolution in CONSOLIDATED form: the in-force text
#                   as re-adopted, with the definitions and district articles that govern a
#                   campus. `local-legislation` because it is still an act of the trustees, but
#                   whole-document on purpose: the substance is spread across `definitions`, the
#                   district articles and the dimensional schedule, and the payload must carry
#                   the file's own `tag: inference` on which re-adoption introduced the
#                   data-center language. The key is `zoning_code` and not the committed
#                   artifact's original `document:`, which is the most generic wrapper word in
#                   this repo and would silently claim the next extraction that used it.
#   `bill`        — a General Assembly bill read section by section against its own printed text.
#                   NOT `local-legislation`: that group is "an act of a LOCAL legislative body,
#                   journalled in its own minutes", and the whole discriminator is the body that
#                   voted. A statewide bill is a different level of government and, as introduced
#                   or as passed by one chamber, is not law at all — the payload keeps
#                   `provenance.version` so the record renders as pending, never enacted.
#                   Whole-document because `bill:` is a pure identity stub (number, title,
#                   sponsors); every provision read sits beside it.
#   `retention_policy`
#                 — an adopted, signed public-records availability + retention policy of a public
#                   body, produced in a records request. It is an instrument (dated, adopted,
#                   signed), not a compilation, but no group fits: `plans` is a plan document,
#                   `local-legislation` is an act journalled in minutes, and the `permits-*`
#                   family is authorizations. Whole-document because the subject is spread across
#                   `availability_policy` / `retention_policy` / `schedule_*`.
#   `development_agreement`
#                 — a per-site REGISTER of the incentive and development instruments for one
#                   campus: the executed agreements plus the legislative chain that authorized
#                   them, one file per site. Deliberately NOT `agreements`, which is
#                   instrument-level — this is the `conveyances`/`deeds` line drawn again, and the
#                   group NAME carries it, because `load_records` yields ONE record per file and a
#                   register cannot honestly be presented as a single executed instrument. It is
#                   keyed on `development_agreement` and not `cra_agreement` because that is the
#                   one block the two committed registers share; their vocabularies otherwise
#                   differ (`cra_agreement`/`legislative_chain`/`land_acquisition` vs `cra`/
#                   `no_cra_agreement`/`disclosed_economics`), and a single-site rule would leave
#                   the other site unpublished. If a SINGLE executed development agreement is ever
#                   extracted on its own, key it `parties:` so it lands in `agreements`, not here.
#   `parties`     — an executed instrument between a public body and a private party: a mutual
#                   NDA, a roadwork development agreement, an intergovernmental wastewater
#                   treatment agreement, a statutory Community Reinvestment Area agreement. No
#                   existing group fits: `finance` (`award:`) is a grant or contract AWARD, and
#                   filing a 75%/15-year R.C. 3735.65 tax exemption there would present an
#                   exemption as a grant — the misfiling #1724 refused. `local-legislation` is the
#                   ACT that authorized the contract, not the contract. Whole-document because
#                   `parties:` names only the counterparties; the terms, execution and authorizing
#                   resolutions sit beside it.
#                   MUST BE LAST. `findlay/governance/litigation-one-energy-v-allen-twp.yaml`
#                   carries both `case:` and `parties:`, and `case` must keep it. (A consent order
#                   carrying `parties:` is already safe — `order:` is a BLOCK key, and the block
#                   map is scanned before this one.)
_WHOLE_DOC_BLOCK_TO_GROUP: dict[str, str] = {
    "case": "litigation",
    "conveyances": "land-assembly",
    "sellers": "land-assembly",
    "zoning_code": "local-legislation",
    "bill": "state-legislation",
    "retention_policy": "agency-policy",
    "development_agreement": "incentive-package",
    "parties": "agreements",  # last — see the note above
}
# Genres a payload block cannot discriminate, because the artifact's identity lives in its
# `meta.kind` rather than in a block name (#1993). This is the SAME rule shape the IDEM permits
# already use, generalized — and it is evaluated LAST, after both block maps and after the OPC
# and IDEM checks, so it can never steal a file that a payload block already claims.
#
# It must never be expressed as a `meta` entry in either block map: 77 committed extractions
# carry a top-level `meta:` dict, the whole-document map is scanned before the IDEM rule, and
# such an entry would publish every meetings manifest, corpus index, completeness audit, standing
# watch and site footprint in the tree while stealing both Fort Wayne IDEM permits and the OPC
# summary out of their correct groups. The value allowlist is the entire safety property.
#
#   siting-cases — a filing in a state utility-siting proceeding for ONE delivery point: an OPSB
#     certificate application or Letter of Notification, a construction notice, a Staff Report of
#     Investigation, or the PJM M-3 need that motivates them. Deliberately NOT in the `permits-*`
#     family: an LON under O.A.C. 4906-6-07 is an APPLICATION with a live intervention docket, and
#     a "Permits —" heading would tell a reader a 29-mile 345 kV line is permitted when the case is
#     pending. The group name is neutral about outcome and about currency, because one member
#     exists precisely to RETIRE a completed 2021 project from a site's data-center load thread.
#   tariffs — a filed retail electric tariff sheet read verbatim at sheet-and-page level (a
#     Schedule DCT, a Rate GT territory definition). NOT keyed on `terms:`, which collides
#     tree-wide with two executed contracts and would misfile a treatment agreement as a tariff.
_META_KIND_TO_GROUP: dict[str, str] = {
    "grid-siting-project": "siting-cases",
    "opsb-siting-case": "siting-cases",
    "transmission-project": "siting-cases",
    "grid-interconnection-need": "siting-cases",
    "tariff-posture": "tariffs",
}
# Envelope keys that are provenance, not subject fields — rendered separately.
_ENVELOPE = frozenset(
    {
        "doc_id",
        "source_path",
        "kind",
        "pages_read",
        "image_pages_read",
        "dpi",
        "source_text_excerpt",
    }
)
# Keys that are the REPO's workflow and the repo's argument, not the document's content. They are
# stripped from whole-document payloads alongside `_ENVELOPE` (#1993). Without this, every
# whole-document record publishes `issue:`/`epic:`/`acceptance:` (an issue's acceptance criteria)
# and `thesis:`/`relevance:`/`bosc_relevance:` (this repo's reading of the document) as if they
# were fields read off the instrument — which is the "floats a site's record domain on its own
# scaffolding" failure this module's docstring names, arriving through the payload instead of
# through the file list.
#
# `subject` is stripped because it is the record's TITLE, not a field — `_record_title` reads it
# off the raw document instead. Deliberately NOT stripped: `limitations`, `open_targets`,
# `open_questions`, `warnings`, `confidence`, `discrepancies`, `provenance`, `source`/`sources`.
# Those are the record's own statement of what it does not establish and where it came from,
# which is exactly what a record must carry.
_WORKING_NOTES = frozenset(
    {
        "as_of",
        "site",
        "issue",
        "epic",
        "strengthens",
        "acceptance",
        "subject",
        "relevance",
        "bosc_relevance",
        "thesis",
        "cross_refs",
        "corrections_to_issue_body",
        "corrections_to_the_register",
    }
)


@dataclass
class _Record:
    rel: str  # path relative to data/extracted
    group: str
    data: dict[str, Any]
    payload: dict[str, Any] = field(default_factory=dict)


def _whole_doc_payload(data: dict[str, Any]) -> dict[str, Any]:
    """The document minus its provenance envelope and the repo's own working notes."""
    return {k: v for k, v in data.items() if k not in _ENVELOPE and k not in _WORKING_NOTES}


def _classify(data: Any) -> tuple[str, dict[str, Any]] | None:
    """Return ``(group_slug, payload)`` for a recognized record, else ``None``."""
    if not isinstance(data, dict):
        return None
    for block, group in _BLOCK_TO_GROUP.items():
        body = data.get(block)
        if isinstance(body, dict):
            return group, body
    for block, group in _WHOLE_DOC_BLOCK_TO_GROUP.items():
        body = data.get(block)
        if isinstance(body, dict | list) and body:
            return group, _whole_doc_payload(data)
    if any(k in data for k in _OPC_KEYS):
        body = data.get("estimate")
        payload = body if isinstance(body, dict) else _whole_doc_payload(data)
        return "opc", payload
    meta = data.get("meta")
    if isinstance(meta, dict):
        # IDEM permit records: a `meta` block with `kind: idem` (Indiana state permits).
        if meta.get("kind") == "idem":
            return "permits-idem", meta
        # The `meta.kind` allowlist — last, so it can never steal a block-claimed file.
        kind = meta.get("kind")
        allowlisted = _META_KIND_TO_GROUP.get(kind) if isinstance(kind, str) else None
        if allowlisted is not None:
            return allowlisted, _whole_doc_payload(data)
    return None


def _record_title(rec: _Record) -> str:
    """A legible heading for a record, chosen from the most identifying field."""
    payload = rec.payload
    for key in (
        "entity_name",
        "facility_name",
        "project_name",
        "instrument_type",
        "instrument",  # enforcement orders / finance awards (#1746)
        "facility",
        "name",
        "subject",
        "permit_number",
        "assembly",  # land-assembly registers (#1724)
        # Last resort before the filename (#1438). A `resolution:` block names itself with the
        # legislative body's own caption — "Authorizing notice to the Elida Local School
        # District…" — and a general permit with its own long-form title does the same; neither
        # carries any of the identifier fields above. It sits at the END on purpose: every record
        # that already resolves to a specific identifier keeps it, so this can only ever replace a
        # filename stem, never a real title.
        "title",
    ):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    # Nested identifiers: the DMR-style `meta.program`, and a filed case's caption, which sits
    # in the `case:` block while the whole-document payload carries the rest of the filing.
    for block, key in (("meta", "program"), ("case", "caption")):
        body = payload.get(block)
        if isinstance(body, dict):
            val = body.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    # Last tier before the filename (#1993): the DOCUMENT's own self-description, read off the raw
    # extraction rather than the payload. Two shapes carry it — the digest envelope's top-level
    # `subject:` (which `_WORKING_NOTES` strips from the payload, because it is the title and not
    # a field) and the connector-read's `meta.subject`/`meta.title`. It sits below every payload
    # probe so a record that resolves to a real identifier keeps it; this can only ever replace a
    # filename stem. Without it, most of the records #1993 publishes rendered as bare stems —
    # `van-wert-haviland-138kv.project`, and two different sites both reading
    # `incentive-instruments`.
    for holder in (rec.data, rec.data.get("meta")):
        if not isinstance(holder, dict):
            continue
        for key in ("subject", "title"):
            val = holder.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return Path(rec.rel).stem


def load_records(extracted_dir: Path, *, scope: CorpusScopeArg = None) -> list[_Record]:
    """Load and classify every recognized record YAML under ``extracted_dir``.

    ``scope`` is the active site's corpus prefixes (#762): when set, only artifacts whose
    rel-path is in scope are loaded, so a non-Lima site's ``records`` feed carries its own
    records. ``None`` reads the whole tree (Lima, the reference build)."""
    records: list[_Record] = []
    for path in sorted(extracted_dir.rglob("*.yaml")):
        rel = str(path.relative_to(extracted_dir))
        if not relpath_in_scope(rel, scope):
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            log.warning("site.records.bad_yaml", path=str(path), error=str(exc).splitlines()[0])
            continue
        hit = _classify(data)
        if hit is None:
            continue
        group, payload = hit
        records.append(_Record(rel=rel, group=group, data=data, payload=payload))
    return records


def _cited_pages(data: dict[str, Any]) -> tuple[int | None, list[int] | None]:
    """The 1-based page locator for a record's citation, from its 0-based ``pages_read``.

    :attr:`~watermark.models.DocExtraction.pages_read` records the **0-based** page indices an
    extraction consulted; a citation locates a claim the way a reader does — by the page number
    a viewer shows — so the indices are lifted to 1-based here (#1584). Until then the builder
    stuffed the raw list into the citation's prose ``note`` (``"pages [16, 17]"``): off by one,
    unparseable, and invisible to `Citation.page`, which stayed null on every record in the
    bundle.

    Returns ``(page, pages)`` — the first page read, and the whole span ascending. ``pages`` is
    ``None`` for a single-page read (``page`` already describes it in full) and the span is kept
    as a list, not a range: a read is often **non-contiguous** (``2PE00000.npdes.yaml`` cites
    pages 1-4, 37, 40, 84-85, 93 of one permit), and collapsing that to "1-93" would claim 88
    pages the extraction never read. A record with no ``pages_read`` — a connector-sourced
    extraction, or an envelope that never recorded one — yields ``(None, None)``: a page cite is
    never invented.
    """
    raw = data.get("pages_read")
    if not isinstance(raw, list):
        return None, None
    # `bool` is an `int` subclass; a stray `true` in a YAML list must not become page 2.
    zero_based = sorted(
        {p for p in raw if isinstance(p, int) and not isinstance(p, bool) and p >= 0}
    )
    if not zero_based:
        return None, None
    pages = [p + 1 for p in zero_based]
    return pages[0], (pages if len(pages) > 1 else None)


def _approx_paths(value: Any, prefix: str = "") -> list[str]:
    """Dotted paths of every scalar that kept the ``~`` approximate transcription marker.

    Works off the raw YAML (where ``~12345`` survives as the string ``"~12345"``), so the
    bundle carries the marker as data (issue #60) without re-shaping each number.
    """
    out: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            out.extend(_approx_paths(v, f"{prefix}{k}."))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            out.extend(_approx_paths(item, f"{prefix}{i}."))
    elif isinstance(value, str) and value.strip().startswith("~"):
        out.append(prefix.rstrip("."))
    return out


def _source_file(value: Any) -> str | None:
    """The corpus path out of one source entry, which may be a bare string or a block."""
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        for key in ("file", "source_path", "source", "path"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return None


def _source_ref(data: dict[str, Any]) -> Any:
    """The extraction's pointer at the source document it was read from.

    A vision extraction carries a top-level ``source_path``. A structured read of a filed
    instrument carries a ``source:`` provenance block instead, whose ``file`` names the same
    corpus path (#1724) — resolving both is what lets such a record link to its instrument in
    the documents catalog rather than standing alone.

    Three further shapes are in the committed corpus and used to resolve to nothing (#1993): the
    analysis envelope's ``provenance.source_path`` / ``provenance.sources`` (the CRA agreement,
    the seller packets, both statewide bills), the connector read's ``meta.sources`` — a dict of
    named LISTS (``primary``, ``self_published_archived``, …), so every list is scanned and not
    just ``primary`` — and a top-level ``sources:`` list of instrument blocks (the per-site
    incentive registers).
    """
    direct = data.get("source_path")
    if direct is not None:
        return direct
    source = data.get("source")
    if isinstance(source, dict) and (hit := _source_file(source)):
        return hit
    provenance = data.get("provenance")
    if isinstance(provenance, dict):
        if hit := _source_file(provenance):
            return hit
        listed = provenance.get("sources")
        if isinstance(listed, list) and listed and (hit := _source_file(listed[0])):
            return hit
    meta = data.get("meta")
    for holder in (meta if isinstance(meta, dict) else {}, data):
        listed = holder.get("sources")
        if isinstance(listed, dict):
            for entries in listed.values():
                if isinstance(entries, list) and entries and (hit := _source_file(entries[0])):
                    return hit
        elif isinstance(listed, list) and listed and (hit := _source_file(listed[0])):
            return hit
    # Last, so it can only ever fill a gap: the connector envelope's own `meta.source_path`.
    # `meta.source`/`meta.sources` are frequently prose ("Ohio EPA eDoc 4091289") rather than a
    # path, which `_normalize_source_rel` then rejects — that is why this runs after the lists
    # above rather than short-circuiting them.
    if isinstance(meta, dict) and (hit := _source_file(meta)):
        return hit
    return None


def _normalize_source_rel(source_path: Any) -> str | None:
    """Normalize an extraction ``source_path`` to a ``data/documents``-relative rel.

    The committed envelopes carry several shapes: repo-relative (``data/documents/...``
    or a bare ``documents/...``) and absolute machine paths with the legacy
    ``/Users/.../shawnee-smart-systems/bosc/data/documents/...`` prefix. Returns the
    corpus-relative remainder, or ``None`` for a directory reference or any path that
    doesn't sit under the corpus root.
    """
    if not isinstance(source_path, str):
        return None
    s = source_path.strip().replace("\\", "/")
    if not s or s.endswith("/"):
        return None  # a directory (e.g. a collection), not a single document
    idx = s.find(_DOC_ANCHOR)
    if idx != -1:
        rel = s[idx + len(_DOC_ANCHOR) :]
    elif s.startswith("documents/"):
        rel = s[len("documents/") :]
    else:
        return None
    return rel.strip("/") or None


def export_records(
    extracted_dir: Path,
    *,
    doc_index: dict[str, tuple[RenderClass, bool]] | None = None,
    scope: CorpusScopeArg = None,
) -> list[RecordItem]:
    """Export every committed extraction as a :class:`RecordItem` feed.

    Generic raw-YAML read (the same classifier the corpus loader uses), emitting
    structured items — the payload verbatim (``~`` markers intact), the dotted paths that
    carried the marker, and a structured :class:`Citation` provenance footer.

    ``doc_index`` (``rel -> (render_class, published)``, from
    :func:`watermark.site.documents.build_doc_index`) joins each record to its **real** source
    document (#274 / #276): a record carries ``source_doc_rel`` + ``render_class`` only
    when its ``source_path`` resolves to a catalogued file — connector-only records, and
    stale/removed sources, carry ``None``.
    """
    records = load_records(extracted_dir, scope=scope)
    items: list[RecordItem] = []
    for rec in sorted(records, key=lambda r: (r.group, r.rel)):
        payload = rec.payload
        conf = payload.get("confidence")
        confidence: Confidence = conf if conf in ("high", "medium", "low") else "medium"
        raw_warnings = payload.get("warnings") or []
        warnings = [str(w) for w in raw_warnings] if isinstance(raw_warnings, list) else []
        fields = {k: v for k, v in payload.items() if k not in ("confidence", "warnings")}
        page, pages = _cited_pages(rec.data)

        # Join to the real source document, but only when it's actually catalogued.
        src_rel = _normalize_source_rel(_source_ref(rec.data))
        joined = doc_index.get(src_rel) if (doc_index is not None and src_rel) else None
        source_doc_rel = src_rel if joined is not None else None
        source_doc_render_class = joined[0] if joined is not None else None
        source_doc_published = joined[1] if joined is not None else False

        items.append(
            RecordItem(
                rel=rec.rel,
                group=cast(RecordGroup, rec.group),
                title=_record_title(rec),
                confidence=conf if isinstance(conf, str) else None,
                warnings=warnings,
                fields=fields,
                approximate_paths=sorted(set(_approx_paths(fields))),
                citation=Citation(
                    source=rec.rel,
                    source_kind="document",
                    page=page,
                    pages=pages,
                    confidence=confidence,
                ),
                source_doc_rel=source_doc_rel,
                source_doc_render_class=source_doc_render_class,
                source_doc_published=source_doc_published,
            )
        )
    return items
