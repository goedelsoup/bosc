"""Export the committed extractions into typed record feeds.

Reads every ``data/extracted/**/*.yaml`` generically — by the shape of its
payload block, the same way :mod:`watermark.pipeline.corpus` classifies — and emits one
:class:`~watermark.site.feeds.RecordItem` per record. Reading off the raw dict (not the
Pydantic models) keeps this contractor-/genre-agnostic and preserves the ``~``
approximate marker verbatim, per the data discipline in CLAUDE.md. (The legacy
markdown ``render_record_pages`` peer was removed at the SSG-cutover cleanup, #603.)
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
    "award": "finance",
    "permit": "permits-npdes",
    "filing": "permits-sos",
    "plan": "plans",
}
# OPC estimates are whole-document (summary/detail/page) — no single block key.
_OPC_KEYS = frozenset({"estimate", "sub_estimates", "estimate_template"})
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


@dataclass
class _Record:
    rel: str  # path relative to data/extracted
    group: str
    data: dict[str, Any]
    payload: dict[str, Any] = field(default_factory=dict)


def _classify(data: Any) -> tuple[str, dict[str, Any]] | None:
    """Return ``(group_slug, payload)`` for a recognized record, else ``None``."""
    if not isinstance(data, dict):
        return None
    for block, group in _BLOCK_TO_GROUP.items():
        body = data.get(block)
        if isinstance(body, dict):
            return group, body
    if any(k in data for k in _OPC_KEYS):
        body = data.get("estimate")
        payload = (
            body
            if isinstance(body, dict)
            else {k: v for k, v in data.items() if k not in _ENVELOPE}
        )
        return "opc", payload
    # IDEM permit records: a `meta` block with `kind: idem` (Indiana state permits).
    meta = data.get("meta")
    if isinstance(meta, dict) and meta.get("kind") == "idem":
        return "permits-idem", meta
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
    ):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    meta = payload.get("meta")
    if isinstance(meta, dict):
        program = meta.get("program")
        if isinstance(program, str) and program.strip():
            return program.strip()
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
        pages = rec.data.get("pages_read") or None

        # Join to the real source document, but only when it's actually catalogued.
        src_rel = _normalize_source_rel(rec.data.get("source_path"))
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
                    confidence=confidence,
                    note=(f"pages {pages}" if pages else None),
                ),
                source_doc_rel=source_doc_rel,
                source_doc_render_class=source_doc_render_class,
                source_doc_published=source_doc_published,
            )
        )
    return items
