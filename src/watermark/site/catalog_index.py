"""Build the hydrated catalog index (epic #1090 / #1093) — the addressable atom index.

The catalog is the **dependency gate** for user-authored Stories: an addressable index of every
"grabbable" atom across a site, with handle grammar ``<kind>:<site>:<local_id>`` where ``local_id``
reuses each source feed's **existing** stable key (no new ids minted). It is a *pointer* index —
each atom names the live feed row it resolves against, never a copy, so a Story cites the record
without forking it (chain of custody).

This module emits the **feed-backed** kinds (record, timeline, entity, person, place, meeting,
exhibit, concept, lead, dataset) by normalising over feeds the bundle already ships. The web-only
kinds (``teardown``/``doc``/``chapter``/``figure``) are overlaid by the Astro build at render time
(`web/src/lib/catalog.ts`), since they are web artifacts the Python tier can't see. The two tiers
union into one catalog the resolver consumes.

The builder takes already-assembled feed rows (parsed dicts, ``by_alias`` serialisation) so it does
no corpus re-load — a cheap normalisation pass over data already in memory.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from watermark.logging import get_logger
from watermark.site.feeds import CatalogAtom, CatalogIndex

log = get_logger(__name__)

# A row of a collection feed, already serialised to JSON-compatible dicts (``by_alias``).
Row = Mapping[str, Any]


@dataclass(frozen=True)
class _KindSpec:
    """How one feed-backed kind maps its rows onto catalog atoms.

    ``local_id`` returns the row's stable local id, or ``None`` to skip an **ungrabbable** row
    (e.g. a timeline event with no ``ref``). ``title`` yields the human-readable grab-UI label.
    """

    kind: str
    feed: str
    local_id: Callable[[Row], str | None]
    title: Callable[[Row], str]


def _get(row: Row, key: str) -> str:
    value = row.get(key)
    return "" if value is None else str(value)


def _meeting_local_id(row: Row) -> str | None:
    """``MeetingItem.slug`` is the subdivision *body* ("lima", "lacrpc"), not unique per meeting,
    so key on the composite ``slug/{date}`` when dated (slash-delimited — no clash with the ``:``
    handle separator). Undated meetings fall back to the bare slug; a residual collision (two
    undated same-body meetings) leaves the later one ungrabbable in v1 (#1093 rough edge)."""
    slug = _get(row, "slug")
    if not slug:
        return None
    date = _get(row, "date")
    return f"{slug}/{date}" if date else slug


def _meeting_title(row: Row) -> str:
    slug = _get(row, "slug")
    date = _get(row, "date")
    return f"{slug} meeting ({date})" if date else f"{slug} meeting"


# The closed feed-backed kind set (#1093). One render component + one resolver branch each; the
# web-only kinds (teardown/doc/chapter/figure) are added by the Astro overlay, not here.
_SPECS: tuple[_KindSpec, ...] = (
    _KindSpec("record", "records", lambda r: _get(r, "rel") or None, lambda r: _get(r, "title")),
    # Timeline atoms are grabbable only when the event carries a `ref` (locked rough edge); the
    # ref-less majority is deferred to synthetic-hash addressing.
    _KindSpec("timeline", "timeline", lambda r: _get(r, "ref") or None, lambda r: _get(r, "title")),
    _KindSpec("entity", "entities", lambda r: _get(r, "key") or None, lambda r: _get(r, "display")),
    _KindSpec("person", "people", lambda r: _get(r, "slug") or None, lambda r: _get(r, "name")),
    _KindSpec("place", "places", lambda r: _get(r, "slug") or None, lambda r: _get(r, "name")),
    _KindSpec("meeting", "meetings", _meeting_local_id, _meeting_title),
    _KindSpec("exhibit", "exhibits", lambda r: _get(r, "slug") or None, lambda r: _get(r, "title")),
    _KindSpec("concept", "concepts", lambda r: _get(r, "slug") or None, lambda r: _get(r, "title")),
    _KindSpec("lead", "leads", lambda r: _get(r, "id") or None, lambda r: _get(r, "title")),
    _KindSpec("dataset", "catalog", lambda r: _get(r, "id") or None, lambda r: _get(r, "title")),
)

# The full closed kind set, feed-backed + web-only — the resolver's `unknown_kind` guard reads it
# (kept here as the single source of truth so the two tiers can't drift). The web overlay adds
# atoms for the web-only kinds; they are still valid handle kinds everywhere.
FEED_BACKED_KINDS: tuple[str, ...] = tuple(spec.kind for spec in _SPECS)
WEB_ONLY_KINDS: tuple[str, ...] = ("teardown", "doc", "chapter", "figure")
CATALOG_KINDS: tuple[str, ...] = FEED_BACKED_KINDS + WEB_ONLY_KINDS


def catalog_version(atoms: Sequence[CatalogAtom]) -> str:
    """A content hash over the atom set — stable across identical corpora, so #1099 can detect
    when a user Story's cited handles may have drifted. Hashes the sorted handle list (the atoms'
    identity), not their volatile display titles."""
    joined = "\n".join(sorted(atom.handle for atom in atoms))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def build_catalog_index(
    rows_by_feed: Mapping[str, Sequence[Row]],
    *,
    site: str,
    contract_version: str,
) -> CatalogIndex:
    """Normalise the feed-backed rows into the hydrated catalog index (#1093).

    ``rows_by_feed`` maps a bundle feed name to its parsed collection rows (absent/empty feeds are
    simply skipped — a thin site indexes only what it ships). Every ``local_id`` is a source feed
    key **verbatim** — no new ids are minted (#1093). A genuine collision (two rows sharing a key,
    e.g. two timeline events on one instrument ``ref``, or two undated same-body meetings) keeps
    the first — the atom is a *pointer* to "the row with this key" — and the ambiguous remainder is
    left ungrabbable in v1 (synthetic-hash addressing deferred), counted and logged, never minted
    into a fake id that wouldn't resolve.
    """
    atoms: list[CatalogAtom] = []
    seen: set[str] = set()
    dropped = 0
    for spec in _SPECS:
        rows = rows_by_feed.get(spec.feed)
        if not rows:
            continue
        for row in rows:
            local_id = spec.local_id(row)
            if not local_id:
                continue  # ungrabbable row (e.g. ref-less timeline event)
            handle = f"{spec.kind}:{site}:{local_id}"
            if handle in seen:
                dropped += 1  # ambiguous duplicate key — keep the first, drop the rest (v1)
                continue
            seen.add(handle)
            atoms.append(
                CatalogAtom(
                    handle=handle,
                    kind=spec.kind,
                    site=site,
                    local_id=local_id,
                    title=spec.title(row) or local_id,
                    feed=spec.feed,
                )
            )

    atoms.sort(key=lambda a: a.handle)
    index = CatalogIndex(
        site=site,
        catalog_version=catalog_version(atoms),
        contract_version=contract_version,
        atoms=atoms,
    )
    log.info(
        "catalog.indexed",
        site=site,
        atoms=len(atoms),
        dropped=dropped,
        version=index.catalog_version[:12],
    )
    return index
