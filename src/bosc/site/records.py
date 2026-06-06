"""Render the committed extractions into browsable record pages.

Reads every ``data/extracted/**/*.yaml`` generically — by the shape of its
payload block, the same way :mod:`bosc.pipeline.corpus` classifies — and emits
one markdown page per *kind* (deeds, EPA actions, NPDES permits, SoS filings,
plans, OPC estimates), each record rendered as a section with a confidence
badge, a warnings admonition, a field table, and a provenance footer linking the
raw YAML. Rendering off the raw dict (not the Pydantic models) keeps this
contractor-/genre-agnostic and preserves the ``~`` approximate marker verbatim,
per the data discipline in CLAUDE.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from bosc.logging import get_logger

log = get_logger(__name__)

# Group slug -> (human label, page title), in nav order.
_GROUPS: list[tuple[str, str, str]] = [
    ("deeds", "deed", "Deeds"),
    ("permits-epa", "EPA action", "Permits — Ohio EPA / USACE"),
    ("permits-npdes", "NPDES permit", "Permits — NPDES (wastewater discharge)"),
    ("permits-sos", "SoS filing", "Business filings — Secretary of State"),
    ("plans", "site plan", "Engineering plans"),
    ("opc", "cost estimate", "Cost estimates — Opinion of Probable Cost"),
]
# Single-payload-block genres: the block key carries the subject fields.
_BLOCK_TO_GROUP: dict[str, str] = {
    "deed": "deeds",
    "action": "permits-epa",
    "permit": "permits-npdes",
    "filing": "permits-sos",
    "plan": "plans",
}
# OPC estimates are whole-document (summary/detail/page) — no single block key.
_OPC_KEYS = frozenset({"estimate", "sub_estimates", "estimate_template"})
# Envelope keys that are provenance, not subject fields — rendered separately.
_ENVELOPE = frozenset({"doc_id", "source_path", "kind", "pages_read", "dpi", "source_text_excerpt"})


@dataclass
class RecordPage:
    """One generated kind page: ``records/<slug>.md`` with N record sections."""

    slug: str
    title: str
    count: int


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
    return None


def _md_escape(text: str) -> str:
    """Escape the few characters that would break a markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _fmt_scalar(value: Any) -> str:
    """Render a scalar for a table cell, preserving the ``~`` approximate marker."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return _md_escape(str(value))


def _render_value(value: Any, depth: int = 0) -> list[str]:
    """Render an arbitrary YAML value as markdown bullet lines (recursive)."""
    pad = "  " * depth
    lines: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(v, dict | list) and v:
                lines.append(f"{pad}- **{k}:**")
                lines.extend(_render_value(v, depth + 1))
            else:
                lines.append(f"{pad}- **{k}:** {_fmt_scalar(v)}")
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict | list) and item:
                lines.append(f"{pad}-")
                lines.extend(_render_value(item, depth + 1))
            else:
                lines.append(f"{pad}- {_fmt_scalar(item)}")
    else:
        lines.append(f"{pad}- {_fmt_scalar(value)}")
    return lines


def _record_title(rec: _Record) -> str:
    """A legible heading for a record, chosen from the most identifying field."""
    payload = rec.payload
    for key in ("entity_name", "facility_name", "project_name", "instrument_type", "name"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    meta = payload.get("meta")
    if isinstance(meta, dict):
        program = meta.get("program")
        if isinstance(program, str) and program.strip():
            return program.strip()
    return Path(rec.rel).stem


def _confidence_badge(payload: dict[str, Any]) -> str:
    conf = payload.get("confidence")
    return f" · confidence **{conf}**" if isinstance(conf, str) and conf else ""


def _render_record(rec: _Record, raw_link: str) -> list[str]:
    """Render one record as a markdown section (an ``##`` heading + body)."""
    payload = rec.payload
    lines = [f"## {_record_title(rec)}{_confidence_badge(payload)}", ""]

    warnings = payload.get("warnings") or []
    if isinstance(warnings, list) and warnings:
        lines.append('!!! warning "Transcription caveats"')
        for w in warnings:
            lines.append(f"    - {_md_escape(str(w))}")
        lines.append("")

    # Subject fields: everything in the payload except confidence/warnings, as a
    # two-column table for scalars and nested bullets for structured values.
    scalars: list[tuple[str, Any]] = []
    nested: list[tuple[str, Any]] = []
    for k, v in payload.items():
        if k in ("confidence", "warnings"):
            continue
        if isinstance(v, dict | list) and v:
            nested.append((k, v))
        else:
            scalars.append((k, v))
    if scalars:
        lines.append("| field | value |")
        lines.append("|---|---|")
        for k, v in scalars:
            lines.append(f"| {k} | {_fmt_scalar(v)} |")
        lines.append("")
    for k, v in nested:
        lines.append(f"**{k}**")
        lines.append("")
        lines.extend(_render_value(v))
        lines.append("")

    # Provenance footer — cite source file + pages, link the raw YAML artifact.
    src = rec.data.get("source_path")
    src_name = Path(str(src)).name if src else rec.rel
    pages = rec.data.get("pages_read")
    page_note = f", pages {pages}" if pages else ""
    lines.append(f"*Source: `{_md_escape(src_name)}`{page_note} · [raw extraction]({raw_link})*")
    lines.append("")
    lines.append("---")
    lines.append("")
    return lines


def load_records(extracted_dir: Path) -> list[_Record]:
    """Load and classify every recognized record YAML under ``extracted_dir``."""
    records: list[_Record] = []
    for path in sorted(extracted_dir.rglob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            log.warning("site.records.bad_yaml", path=str(path), error=str(exc).splitlines()[0])
            continue
        hit = _classify(data)
        if hit is None:
            continue
        group, payload = hit
        rel = str(path.relative_to(extracted_dir))
        records.append(_Record(rel=rel, group=group, data=data, payload=payload))
    return records


def render_record_pages(extracted_dir: Path, records_dir: Path) -> list[RecordPage]:
    """Write ``records/<slug>.md`` (one per kind) + return their summaries.

    ``records_dir`` is ``<web>/records``; raw YAML is assumed already mirrored at
    ``<web>/data/extracted`` so each record can link its source artifact.
    """
    records = load_records(extracted_dir)
    by_group: dict[str, list[_Record]] = {}
    for rec in records:
        by_group.setdefault(rec.group, []).append(rec)

    records_dir.mkdir(parents=True, exist_ok=True)
    pages: list[RecordPage] = []
    for slug, label, title in _GROUPS:
        group = by_group.get(slug)
        if not group:
            continue
        body = [
            f"# {title}",
            "",
            f"{len(group)} {label} record(s), read from scans into structured data. "
            "Each links its raw extraction; figures marked `~` are approximate "
            "transcriptions.",
            "",
        ]
        for rec in sorted(group, key=lambda r: r.rel):
            # From records/<slug>.md the mirrored YAML is at ../data/extracted/<rel>.
            raw_link = f"../data/extracted/{rec.rel}"
            body.extend(_render_record(rec, raw_link))
        (records_dir / f"{slug}.md").write_text("\n".join(body), encoding="utf-8")
        pages.append(RecordPage(slug=slug, title=title, count=len(group)))

    log.info("site.records.rendered", pages=len(pages), records=len(records))
    return pages
