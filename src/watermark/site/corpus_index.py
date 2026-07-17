"""Build the ``corpus-index`` feed (#1573, epic #1560 workstream C) — the at-a-glance node map.

The wiki's node-index page is the browsable map of the whole corpus: one row per node of the
yidam mirror (:mod:`watermark.site.corpus_mirror`), with its kind, in/out degree, line count, and
freshness. yidam's own ``corpus-index`` report (`render_corpus_index`) is a markdown table the
frontend can't read at build time (the mirror is git-ignored, and the build has no Python), so —
like :mod:`watermark.site.facts` and :mod:`watermark.site.open_questions` — this projects the same
information into a typed bundle feed the Astro build reads offline.

It is a **post-pass over the just-built** :class:`~watermark.site.corpus_mirror.Mirror`, not a new
read of the corpus: ``links_out`` is the node's own edge count, ``links_in`` counts the mirror edges
that point *at* it, ``lines`` replicates ``write_mirror``'s serialization so the count matches
``yidam corpus-index`` exactly, and ``updated`` is the newest git-commit date over the committed
source file(s) the node derives from (:attr:`MirrorNode.source_refs`) — null for an aggregated or
code-derived node with no single backing file. Freshness is baked in at export because the frontend
can run neither git nor Python; git failures (a shallow CI checkout) degrade every ``updated`` to
null rather than aborting.
"""

from __future__ import annotations

import posixpath
import re
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

import yaml

from watermark.config import Settings, get_settings
from watermark.logging import get_logger
from watermark.site.corpus_mirror import Mirror, MirrorNode
from watermark.site.feeds import CorpusNodeItem, CorpusNodeKind

log = get_logger(__name__)

# A committer-date line (`git log --format=%cI`) — matched so it's never mistaken for a file path.
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def _kind(node: MirrorNode) -> CorpusNodeKind:
    """The BOSC display kind — the yidam ``class`` folds several BOSC kinds into ``artifact``.

    ``artifact`` covers the site anchor, resolved entities, and profiled people; ``question`` covers
    both open-leads and open hypothesis cells. The node's meta carries the finer signal.
    """
    cls = node.node_class
    meta = node.meta
    if cls == "concept":
        return "concept"
    if cls == "hypothesis":
        return "hypothesis"
    if cls == "relation":
        return "relation"
    if cls == "question":
        return "lead" if meta.get("lead_kind") else "open-question"
    if cls == "artifact":
        kind = meta.get("kind")
        if kind == "site":
            return "site"
        if kind == "person":
            return "person"
        return "entity"
    return "node"


def _target_id(source_class: str, target: str) -> str:
    """Resolve one link ``target`` (relative to the source node's class dir) to a ``<class>/<name>``.

    A bare ``foo.yml`` is a sibling in the source's own class; ``../<class>/foo.yml`` names another.
    """
    stem = target[:-4] if target.endswith(".yml") else target
    parts = stem.split("/")
    name = parts[-1]
    node_class = parts[-2] if len(parts) >= 2 and parts[-2] != ".." else source_class
    return f"{node_class}/{name}"


def _in_degrees(mirror: Mirror) -> dict[str, int]:
    """``{node id: incoming-edge count}`` — every mirror link resolved back to the node it targets."""
    ids = {node.id for node in mirror.nodes}
    indeg: dict[str, int] = {}
    for node in mirror.nodes:
        for link in node.links:
            tid = _target_id(node.node_class, link.target)
            if tid in ids:
                indeg[tid] = indeg.get(tid, 0) + 1
    return indeg


def _line_count(node: MirrorNode) -> int:
    """The serialized node's line count — the same dump ``write_mirror`` writes to disk."""
    text = yaml.safe_dump(node.to_dict(), sort_keys=False, allow_unicode=True)
    return len(text.splitlines())


def _resolve_ref(ref: str, settings: Settings, repo_root: Path) -> str | None:
    """A source ref → the repo-relative path of the committed file it names, or ``None``.

    Handles the ``concept:<slug>`` sentinel (→ ``concepts_dir/<slug>.md``) and both repo-relative
    (``data/reference/…``) and corpus-relative (``recorder/…``, resolved under the extracted /
    documents trees) source strings. A prose citation that isn't a real file resolves to ``None`` —
    that node simply has no freshness, never a fabricated one.
    """
    ref = (ref or "").strip()
    if not ref:
        return None
    if ref.startswith("concept:"):
        slug = ref[len("concept:") :]
        path = settings.concepts_dir / f"{slug}.md"
        return _rel(path, repo_root) if path.is_file() else None
    candidates = [ref]
    if not ref.startswith("data/"):
        candidates += [f"data/extracted/{ref}", f"data/documents/{ref}", f"data/{ref}"]
    for cand in candidates:
        rel = posixpath.normpath(cand)
        if rel.startswith("..") or rel.startswith("/"):
            continue  # never escape the repo root
        if (repo_root / rel).is_file():
            return rel
    return None


def _rel(path: Path, repo_root: Path) -> str | None:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None


def _resolve_refs(refs: Iterable[str], settings: Settings, repo_root: Path) -> list[str]:
    """Every source ref of a node resolved to a repo-relative path (deduped, order-preserving)."""
    out: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        rel = _resolve_ref(ref, settings, repo_root)
        if rel and rel not in seen:
            seen.add(rel)
            out.append(rel)
    return out


def _git_commit_dates(paths: Sequence[str], repo_root: Path) -> dict[str, str]:
    """``{repo-relative path: newest committer date (ISO-8601)}`` for the given committed paths.

    One ``git log --name-only`` walk over ``data`` (where every corpus source lives): git lists
    commits newest-first, so a path's *first* appearance is its last-commit date. Returns ``{}`` on
    any git failure (missing binary, shallow checkout) — the caller degrades freshness to null.
    """
    if not paths:
        return {}
    wanted = set(paths)
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "log", "--format=%cI", "--name-only", "--", "data"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return {}
    dates: dict[str, str] = {}
    current: str | None = None
    for line in proc.stdout.splitlines():
        if _ISO_RE.match(line):
            current = line
        elif line and current and line in wanted and line not in dates:
            dates[line] = current
        if len(dates) == len(wanted):
            break
    return dates


def build_corpus_index(
    mirror: Mirror,
    *,
    settings: Settings | None = None,
    git_dates: Mapping[str, str] | None = None,
) -> list[CorpusNodeItem]:
    """Project a :class:`Mirror` into the ``corpus-index`` feed rows (sorted by node id).

    ``git_dates`` (``{repo-relative path: ISO datetime}``) is injectable for deterministic tests;
    when omitted, freshness is computed from the repo's git history. Never re-reads the corpus.
    """
    settings = settings or get_settings()
    repo_root = settings.data_dir.parent

    indeg = _in_degrees(mirror)
    node_paths = {
        node.id: _resolve_refs(node.source_refs, settings, repo_root) for node in mirror.nodes
    }
    if git_dates is None:
        all_paths = sorted({p for paths in node_paths.values() for p in paths})
        git_dates = _git_commit_dates(all_paths, repo_root)

    rows: list[CorpusNodeItem] = []
    for node in mirror.nodes:
        node_dates = [git_dates[p] for p in node_paths[node.id] if p in git_dates]
        updated = max(node_dates)[:10] if node_dates else None  # newest, as an ISO date
        rows.append(
            CorpusNodeItem(
                id=node.id,
                node_class=node.node_class,
                kind=_kind(node),
                label=node.label,
                scope=node.meta.get("scope"),
                links_out=len(node.links),
                links_in=indeg.get(node.id, 0),
                lines=_line_count(node),
                updated=updated,
            )
        )
    rows.sort(key=lambda r: r.id)
    log.info("corpus_index.built", site=mirror.site, nodes=len(rows))
    return rows
