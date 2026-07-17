"""Precompute all-MiniLM-L6-v2 sentence embeddings for the ask-index (#329) and the
page-level passage index (#1589).

Called from :func:`watermark.site.export.export_bundle` (unless ``--no-embeddings``
is passed).  Uses the same model as the Cloudflare Workers AI endpoint
``@cf/sentence-transformers/all-minilm-l6-v2`` that encodes the user's query at
runtime, so document and query vectors share the same 384-dimensional semantic space.

The model is downloaded on first use (~80 MB, cached under
``~/.cache/huggingface/hub`` by the transformers library) and memoised per process
(:func:`_get_model`) so the ask + passage passes don't reload it.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sentence_transformers import SentenceTransformer

from watermark.logging import get_logger

log = get_logger(__name__)

_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_model_cache: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Load (once per process) the shared embedding model — reused by the ask + passage passes."""
    global _model_cache
    if _model_cache is None:
        _model_cache = SentenceTransformer(_MODEL)
    return _model_cache


def _encode_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Encode ``{id, text}`` rows into the shipped ``{id, embedding}`` feed shape.

    Vectors are L2-normalised so cosine similarity equals dot product at query time (cheaper on the
    Worker). An empty input short-circuits without loading the model.
    """
    if not rows:
        return []
    model = _get_model()
    vectors = model.encode(
        [r["text"] for r in rows],
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=64,
    )
    return [{"id": r["id"], "embedding": v.tolist()} for r, v in zip(rows, vectors, strict=True)]


@dataclass
class _TextUnit:
    id: str
    text: str


def _blob(*parts: str | None) -> str:
    return " · ".join(p for p in parts if p)


def _flatten_fields(fields: dict[str, Any], depth: int = 0) -> str:
    if depth > 2:
        return ""
    bits: list[str] = []
    for k, v in fields.items():
        if v is None:
            continue
        if isinstance(v, list):
            scalars = [str(x) for x in v if x is not None and not isinstance(x, dict)]
            if scalars:
                bits.append(f"{k} {' '.join(scalars)}")
        elif isinstance(v, dict):
            inner = _flatten_fields(v, depth + 1)
            if inner:
                bits.append(inner)
        else:
            bits.append(f"{k} {v}")
    return " · ".join(bits)


def _slugify(text: str) -> str:
    """Mirrors the TypeScript ``slugify`` used by ``buildAskIndex``."""
    return re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9]+", "-", text.lower()))


def _read_feed(feeds_dir: str, name: str) -> list[dict[str, Any]]:
    for ext in (".json", ".ndjson"):
        path = os.path.join(feeds_dir, f"{name}{ext}")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            if ext == ".ndjson":
                return [json.loads(line) for line in f if line.strip()]
            data = json.load(f)
            return data if isinstance(data, list) else []
    return []


def build_text_units(bundle_dir: Path | str) -> list[_TextUnit]:
    """Read corpus feeds from a bundle directory and produce one text unit per
    ask-index entry, mirroring ``buildAskIndex()`` in ``web/packages/core/src/askIndex.ts``.

    The ``title + key_fields`` text mirrors the BM25 indexed text so both
    retrieval signals draw from the same content signal.
    """
    feeds = os.path.join(str(bundle_dir), "feeds")
    units: list[_TextUnit] = []

    for r in _read_feed(feeds, "records"):
        if not r.get("rel"):
            continue
        units.append(
            _TextUnit(
                id=f"records:{r['rel']}",
                text=_blob(
                    r.get("title"),
                    r.get("group"),
                    r.get("confidence"),
                    _flatten_fields(r.get("fields", {})),
                ),
            )
        )

    for e in _read_feed(feeds, "timeline"):
        title = e.get("title", "")
        date = e.get("date", "")
        local_id = e.get("ref") or _slugify(f"{date}-{title}")
        units.append(
            _TextUnit(
                id=f"timeline:{local_id}",
                text=_blob(
                    f"{date} — {title}",
                    e.get("category"),
                    e.get("detail"),
                    e.get("source"),
                    *e.get("parties", []),
                    *e.get("also_sources", []),
                ),
            )
        )

    for c in _read_feed(feeds, "documents"):
        if not c.get("slug"):
            continue
        entry_names = " · ".join(x.get("name", "") for x in c.get("entries", []))
        units.append(
            _TextUnit(
                id=f"documents:{c['slug']}",
                text=_blob(c.get("title"), c.get("description"), entry_names),
            )
        )

    for m in _read_feed(feeds, "meetings"):
        if not m.get("slug"):
            continue
        units.append(
            _TextUnit(
                id=f"meetings:{m['slug']}",
                text=_blob(
                    m.get("title") or f"{m.get('date', '')} — {m.get('kind', 'meeting')}",
                    m.get("summary"),
                    m.get("corridor_relevance"),
                    *m.get("decisions", []),
                    *m.get("parties", []),
                    *m.get("dollar_figures", []),
                ),
            )
        )

    for p in _read_feed(feeds, "people"):
        if not p.get("slug"):
            continue
        units.append(
            _TextUnit(
                id=f"people:{p['slug']}",
                text=_blob(
                    p.get("name"),
                    *p.get("aliases", []),
                    *p.get("roles", []),
                    *p.get("affiliations", []),
                    p.get("summary"),
                    p.get("body"),
                ),
            )
        )

    for p in _read_feed(feeds, "places"):
        if not p.get("slug"):
            continue
        units.append(
            _TextUnit(
                id=f"places:{p['slug']}",
                text=_blob(
                    p.get("name"),
                    p.get("kind"),
                    *p.get("aliases", []),
                    *p.get("tags", []),
                    p.get("body"),
                ),
            )
        )

    for e in _read_feed(feeds, "entities"):
        if not e.get("key"):
            continue
        roles: list[str] = list((e.get("roles") or {}).keys())
        units.append(
            _TextUnit(
                id=f"entities:{e['key']}",
                text=_blob(
                    e.get("display"),
                    e.get("kind"),
                    e.get("classification"),
                    *e.get("variants", []),
                    *roles,
                    *e.get("addresses", []),
                ),
            )
        )

    for c in _read_feed(feeds, "concepts"):
        if not c.get("slug"):
            continue
        units.append(
            _TextUnit(
                id=f"concepts:{c['slug']}",
                text=_blob(
                    c.get("title"),
                    c.get("summary"),
                    *c.get("aliases", []),
                    *c.get("tags", []),
                    c.get("body"),
                ),
            )
        )

    return units


def build_ask_embeddings(bundle_dir: Path | str) -> list[dict[str, Any]]:
    """Encode text units from a bundle directory with all-MiniLM-L6-v2.

    Returns a list of ``{"id": ..., "embedding": [...]}`` dicts ready to write
    as the ``ask-embeddings`` feed.  Vectors are L2-normalised so cosine similarity
    equals dot product at query time (cheaper on the Worker).
    """
    units = build_text_units(bundle_dir)
    if not units:
        log.info("embeddings.skip", reason="no text units in bundle")
        return []

    log.info("embeddings.encode", units=len(units), model=_MODEL)
    rows = _encode_rows([{"id": u.id, "text": u.text} for u in units])
    log.info("embeddings.done", units=len(units))
    return rows


def build_passage_embeddings(bundle_dir: Path | str) -> list[dict[str, Any]]:
    """Encode the ``passages`` feed's page excerpts with all-MiniLM-L6-v2 (#1589).

    Reads the just-written ``feeds/passages`` (JSON or NDJSON) and returns ``{"id", "embedding"}``
    rows for the ``passage-embeddings`` feed — the vector companion to the passage text index, in
    the same 384-dim space as ``ask-embeddings`` so ``search_passages`` shares the runtime query
    embedding. Empty when the passages feed is absent/empty (no published PDF text to embed).
    """
    feeds = os.path.join(str(bundle_dir), "feeds")
    rows = _read_feed(feeds, "passages")
    passages = [{"id": r["id"], "text": r.get("text", "")} for r in rows if r.get("id")]
    if not passages:
        log.info("passage_embeddings.skip", reason="no passages in bundle")
        return []

    log.info("passage_embeddings.encode", passages=len(passages), model=_MODEL)
    out = _encode_rows(passages)
    log.info("passage_embeddings.done", passages=len(passages))
    return out
