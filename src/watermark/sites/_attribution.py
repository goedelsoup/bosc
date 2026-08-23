"""The corpus attribution overlay — which site a committed extraction is ABOUT (#2085).

``data/extracted/**`` mirrors the immutable ``data/documents/**``, so an artifact is shelved
where its *source* was served, and :func:`~watermark.sites.effective_corpus_scope` derives a
site's scope from that shelf (#1405). Usually the shelf is the attribution. When the source's own
filing is wrong it is not: Ohio EPA's eDocument portal served a MANSFIELD WWTP letter and a HENRY
COUNTY spill report on Lima's permit 2PE00000, and both were shelved under ``oepa/lima/`` because
the tree mirrors what was served. **Read the shelf as custody, not attribution.**

This module loads the reviewed, document-cited overlay at ``data/corpus-attribution.yaml`` — the
same repo-relative, import-time idiom as ``data/sites.yaml`` — and turns it into the two
exact-relpath tuples :class:`~watermark.sites.CorpusScope` understands. Nothing here moves a byte,
renames a file, or edits a printed value; the correction lives entirely at the read layer, which
is what the chain-of-custody rule leaves available.

**The overlay is data, and the claim is evidentiary.** A row names an exact committed relpath, the
registered slug the document is actually about (or an explicit ``null``), and the
document-internal ``basis`` for saying so. It is never inferred from a filename, a permit number,
or a warning string — filtering on prose is the loose predicate ``_classify``'s docstring argues
against, and an attribution is a stronger claim than a classification.

``attributed_to: null`` is a real, distinct outcome, not a missing value: Henry County is not a
registered site, so the RAILTECH IPIR has no scope to land in. It leaves Lima's and is claimed by
none. The artifact stays committed and citable — the overlay row is where it stays *visible*, so
"in no site's cross-document layer" can never become the silent drop of #1994.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

_YAML_PATH = Path(__file__).parents[3] / "data" / "corpus-attribution.yaml"


class AttributionOverride(BaseModel):
    """One reviewed re-attribution of a committed extraction (a row of the overlay)."""

    model_config = ConfigDict(extra="forbid")

    #: Exact path relative to ``data/extracted`` — not a prefix. A prefix would re-attribute a
    #: whole subtree on the strength of a claim reviewed against ONE document.
    relpath: str
    #: The site whose scope the shelf would otherwise place it in.
    shelved_under: str
    #: The registered slug the document is about, or ``None`` when no registered site owns it.
    attributed_to: str | None
    #: What the document is about, in the words its own text uses.
    subject: str
    #: The document-internal evidence for the re-attribution.
    basis: str
    reviewed: str
    issue: str | None = None


def _load(path: Path) -> tuple[AttributionOverride, ...]:
    # A MISSING overlay is a failure, not an empty one — checked before the file is read at all.
    # Returning `()` here would silently un-do every re-attribution: the Mansfield letter would
    # slide back onto Lima's chronology and the Henry County IPIR with it, with no error anywhere.
    # That is the exact silent-revert this module exists to prevent, so it fails loudly instead.
    # An overlay with an empty (or absent) `overrides:` list is a different thing entirely — a
    # deliberate statement that nothing is re-attributed — and still loads to `()`.
    if not path.exists():
        raise FileNotFoundError(
            f"attribution overlay missing at {path} — every corpus re-attribution lives there, "
            "so its absence would silently revert them. Restore the committed file (an empty "
            "`overrides:` list is how you say 'nothing is re-attributed')."
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = [AttributionOverride.model_validate(row) for row in data.get("overrides") or ()]
    seen: set[str] = set()
    for row in rows:
        if row.relpath in seen:
            raise ValueError(
                f"{path.name}: duplicate override for {row.relpath!r} — one artifact has one "
                "attribution, and two rows would silently race for it"
            )
        if row.attributed_to == row.shelved_under:
            raise ValueError(
                f"{path.name}: {row.relpath!r} is attributed to the site it is already shelved "
                "under — a row that changes nothing reads as a reviewed finding that there was "
                "something to change"
            )
        seen.add(row.relpath)
    return tuple(rows)


@lru_cache(maxsize=1)
def attribution_overrides() -> tuple[AttributionOverride, ...]:
    """Every committed re-attribution, in file order."""
    return _load(_YAML_PATH)


def reattributed_out(slug: str) -> tuple[str, ...]:
    """Exact relpaths shelved under ``slug`` that are about somewhere else (or nowhere).

    Subtracted from ``slug``'s scope whatever its prefixes say — including the reference build's
    whole-tree inclusion, which is precisely where these two sit.
    """
    return tuple(sorted(r.relpath for r in attribution_overrides() if r.shelved_under == slug))


def reattributed_in(slug: str) -> tuple[str, ...]:
    """Exact relpaths about ``slug`` that are shelved somewhere else.

    Granted to ``slug`` whatever its prefixes say, so a peer's narrow ``(slug, */slug)`` inclusion
    can reach a document filed under another site's collection without widening it.
    """
    return tuple(sorted(r.relpath for r in attribution_overrides() if r.attributed_to == slug))
