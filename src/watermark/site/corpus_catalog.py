"""Project BOSC's dataset catalog into yidam catalog entries (#2134, Epic #2124).

``.yidam/catalog/<slug>.md`` is where yidam records **where knowledge came from, not the
knowledge itself**. Four of its lint checks read that tree, and — more importantly —
``verified-unsourced`` resolves each node's links against it: a node asserting a
``[verified]`` claim while linking to no registered source has claimed a standing it cannot
demonstrate. BOSC projected no catalog at all, so all five reported zero, and the zero meant
"no registry", not "nothing unsourced". That is the same false green #2132 was filed to end.

**The source of truth is BOSC's own catalog** (``data/catalog/<scope>/<id>.yaml``,
:mod:`watermark.catalog`) — 199 reviewed :class:`~watermark.catalog.CatalogEntry` records
naming what each dataset is, how it regenerates, and which files it covers. This module
renders a subset of them into yidam's much smaller schema. It invents nothing: every field
here is carried over from an entry a reviewer already wrote.

**A citation is a link that resolves to the catalog file** (``checks.rs::linked_paths``) —
not a mention, not a slug appearing in the node's bytes. So a mirror node cites a source by
carrying a ``links:`` entry whose target is ``../../catalog/<slug>.md``, which is what
:func:`catalog_link_target` writes and what makes the resolution work.

**What is deliberately omitted, and why each omission is safe.** yidam's ``Source`` carries
``used_by``, ``ttl_days``/``retrieved`` and ``artifacts`` beyond the fields written here, and
each gates a check that stays silent while the field is absent:

* ``used-by`` — declaring it asserts the list is current, and ``catalog-used-by-drift``
  (Warn) then reports every disagreement with the real citations. The citations *are*
  authoritative, so the list would be a second copy of a derived fact whose only possible
  contribution is to be wrong.
* ``ttl_days``/``retrieved`` — ``catalog-expired`` (Warn) is a staleness gate, and BOSC
  already has one: ``watermark catalog check`` reads the same ``refresh.ttl_days`` from the
  same entries. Projecting it would report each stale dataset twice, in two vocabularies.
* ``artifacts`` — RFC-0023 content addressing. Upstream writes those checks so that an empty
  list is silent, explicitly so a corpus adopts them deliberately rather than by upgrading.
* ``obtained`` — absent means *yes*. Every entry projected here is committed data on disk, so
  ``false`` would be a lie, and it is ``false`` that arms ``catalog-unobtained-but-cited``,
  the one Error-severity check of the four.

Which leaves ``catalog-uncited`` (Info) as the only check this projection newly activates,
plus the resolution target ``verified-unsourced`` was missing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from watermark.catalog import CatalogEntry, load_entries
from watermark.catalog.resolve import resolved_for_site
from watermark.config import Settings, get_settings
from watermark.logging import get_logger

log = get_logger(__name__)

#: Where the projected catalog lands, relative to the repo root.
CATALOG_DIRNAME = "catalog"

#: The relationship a corpus node uses to cite a catalog entry.
#:
#: **Not a class edge, and deliberately undeclared in any `<class>.ont.yml`.** yidam's
#: `unlicensed-edge` and `edge-target-class` both walk `instance_links`, which pairs a link
#: with the *node* it resolves to — and a catalog entry is a file, not a node, so both checks
#: skip these by construction. `linked_paths`, which is what `verified-unsourced` and the
#: citation counter read, parses `links:` targets straight out of the YAML and does see them.
#: So the citation is invisible to the class contract and fully visible to the evidence
#: checks, which is exactly the split that makes an `exhaustive` edge policy compatible with
#: citing sources at all.
CITES = "rests-on"

#: yidam's `type` vocabulary (`catalog-entry.json`). BOSC's `ProducerKind` is a different
#: question — *how the dataset comes into being* rather than *what kind of source it is* — so
#: the map is stated rather than assumed, and anything unmapped lands on `other` rather than
#: inventing a category.
_TYPE_BY_PRODUCER: dict[str, str] = {
    "connector": "api",
    "vendored": "dataset",
    "derived": "dataset",
    "extracted": "other",
    "manual": "other",
}


@dataclass(frozen=True)
class CatalogLocation:
    """One `location:` entry — where the source is reachable."""

    kind: str  # `url` | `url_template` | `address` | `file`
    value: str
    description: str = ""


@dataclass(frozen=True)
class CatalogSource:
    """One projected `.yidam/catalog/<slug>.md`."""

    slug: str
    name: str
    description: str
    type: str
    locations: tuple[CatalogLocation, ...] = ()
    body: str = ""
    #: The `data/`-relative paths this entry registers — what a citation of it means. Not
    #: written into the file; it is how :func:`entry_for_path` resolves a node's source to a
    #: slug, and it is the reason a projected catalog can be *cited* rather than merely listed.
    covers: tuple[str, ...] = ()


def _oneline(text: str) -> str:
    """Collapse prose to a single line — a `description:` is one sentence, not a document."""
    return re.sub(r"\s+", " ", (text or "").strip())


def _describe(entry: CatalogEntry) -> str:
    """The one-sentence `description:`, from what the reviewer already wrote."""
    said = _oneline(entry.producer.source or "")
    if said:
        # The producer's `source` is the human sentence naming the upstream — exactly what
        # this field is for. Truncated on a word boundary so a paragraph-length one stays a
        # description; the whole of it is kept in the body below, never lost.
        if len(said) > 300:
            said = said[:300].rsplit(" ", 1)[0] + "…"
        return said
    return _oneline(entry.title)


def _body(entry: CatalogEntry) -> str:
    """The prose half of the entry — what this source is, and what it does not answer."""
    lines = [f"# {entry.title}", ""]
    if entry.producer.source:
        lines += ["## What it is", "", _oneline(entry.producer.source), ""]
    facts = [
        ("Scope", entry.scope),
        ("Provenance", entry.provenance),
        ("License", entry.license or "not stated"),
        ("Access", entry.access_tier),
        ("Site scope", entry.site_scope),
        ("Review status", entry.status),
        ("Regenerated by", entry.producer.command or f"{entry.producer.kind} (no command)"),
    ]
    lines += ["## Record", ""]
    lines += [f"- **{k}:** {v}" for k, v in facts if v]
    lines += [""]
    if entry.notes:
        lines += ["## Notes", "", _oneline(entry.notes), ""]
    lines += [
        "---",
        "",
        "Projected from `data/catalog/"
        f"{entry.scope}/{entry.id}.yaml` by `watermark corpus-mirror`"
        " (`watermark.site.corpus_catalog`). Edit the catalog entry, never this file.",
        "",
    ]
    return "\n".join(lines)


def _covered_relpaths(entry: CatalogEntry, slug: str) -> list[str]:
    """Every `data/`-relative path this entry registers **for the active site**.

    ⚠️ **`{site}` templates must be expanded, or the citation silently does not resolve.**
    A `slug-scoped` dataset stores a different file per site and declares it once as
    `extracted/{site}/bosc-site-footprint.yaml`; 27 of the catalog's storage relpaths are
    written that way. Comparing that literal against a real path never matches, so the record
    got no `rests-on` link and `verified-unsourced` reported it as a claim resting on nothing
    — a FALSE positive, in the one check this projection exists to make trustworthy. Findlay
    produced two of them.

    :func:`~watermark.catalog.resolve.resolved_for_site` is the repo's one expansion rule,
    shared with `reconcile` and `sites`, so a citation resolves the same way an observation
    does. A second copy of that rule is where the next divergence goes.
    """
    concrete = {s.relpath for s in entry.storage if "{site}" not in s.relpath}
    return sorted(concrete | set(resolved_for_site(entry, slug)))


def _locations(entry: CatalogEntry, slug: str) -> tuple[CatalogLocation, ...]:
    """Where the source lives — its committed files, `{site}` already expanded."""
    by_rel = {s.relpath: s for s in entry.storage}
    out: list[CatalogLocation] = []
    for rel in _covered_relpaths(entry, slug):
        # The templated member's media type lives on the un-expanded declaration.
        item = by_rel.get(rel) or next(
            (
                s
                for s in entry.storage
                if "{site}" in s.relpath and rel.endswith(s.relpath.rsplit("{site}", 1)[-1])
            ),
            None,
        )
        out.append(
            CatalogLocation(
                kind="file",
                value=f"data/{rel}",
                description=(item.media_type if item else "") or "",
            )
        )
    return tuple(out)


def project_entry(entry: CatalogEntry, slug: str) -> CatalogSource:
    """One :class:`~watermark.catalog.CatalogEntry` as a yidam catalog source, for one site."""
    covered = _covered_relpaths(entry, slug)
    return CatalogSource(
        slug=entry.id,
        name=entry.title,
        description=_describe(entry),
        type=_TYPE_BY_PRODUCER.get(entry.producer.kind, "other"),
        locations=_locations(entry, slug),
        body=_body(entry),
        covers=tuple(f"data/{rel}" for rel in covered),
    )


def build_catalog(settings: Settings | None = None) -> list[CatalogSource]:
    """Every reviewed catalog entry, projected — network-wide, not per-site.

    **The catalog is a registry of sources, and a registry is not a site's record.** Scoping
    it to the active site would make a citation resolvable in one mirror and dangling in
    another, for the same committed file. `catalog-uncited` is Info and reports the entries a
    given site does not draw on, which is the honest way to say that, and costs nothing.
    """
    settings = settings or get_settings()
    entries = load_entries(settings=settings)
    sources = [project_entry(e, settings.site) for e in entries]
    log.info(
        "corpus_catalog.built", sources=len(sources), covered=sum(len(s.covers) for s in sources)
    )
    return sources


def entry_for_path(sources: list[CatalogSource], data_relpath: str) -> str | None:
    """The slug registering ``data/<…>``, or ``None`` — how a node's source becomes a citation."""
    want = data_relpath.strip().lstrip("./")
    if not want.startswith("data/"):
        want = f"data/{want}"
    for source in sources:
        if want in source.covers:
            return source.slug
    return None


def catalog_link_target(slug: str) -> str:
    """The link a corpus node writes to cite ``slug``.

    Resolved from the node's own directory (`.yidam/corpus/<class>/`), which is what
    `linked_paths` does — so the two `..` segments are load-bearing, not decoration.
    """
    return f"../../{CATALOG_DIRNAME}/{slug}.md"


def _front_matter(source: CatalogSource) -> str:
    body: dict[str, object] = {
        "name": source.name,
        "description": source.description,
        "type": source.type,
    }
    if source.locations:
        body["location"] = [
            {"kind": loc.kind, "value": loc.value}
            | ({"description": loc.description} if loc.description else {})
            for loc in source.locations
        ]
    return yaml.safe_dump(body, sort_keys=False, allow_unicode=True, width=100)


def render_source(source: CatalogSource) -> str:
    """One catalog entry as its `.md` file — YAML front matter, then the prose."""
    return f"---\n{_front_matter(source)}---\n\n{source.body}"


def write_catalog(sources: list[CatalogSource], root: Path) -> Path:
    """Write `<root>/catalog/<slug>.md` for each source, clearing what a prior run wrote."""
    out = root / CATALOG_DIRNAME
    if out.is_dir():
        for stale in out.glob("*.md"):
            stale.unlink()
    out.mkdir(parents=True, exist_ok=True)
    for source in sources:
        (out / f"{source.slug}.md").write_text(render_source(source), encoding="utf-8")
    return out
