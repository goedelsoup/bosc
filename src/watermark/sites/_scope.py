"""The corpus scope value — which ``data/extracted`` relpaths a site's cross-document layer reads.

A site's record/timeline/entities/bundle domain is bounded to a subtree of the committed extracted
tree (#762/#780). The reference build (Lima) reads the *whole* tree **except** the subtrees every
registered peer owns, so a Piqua NPDES permit or a Fort Wayne §401 record never renders inside
Lima's Allen-County record (#1505); a non-reference site reads only its own prefixes.

This is the single value :func:`~watermark.sites.effective_corpus_scope` returns and the shared
``watermark.pipeline.corpus.relpath_in_scope`` predicate interprets, so export, timeline, entities,
the ``records``/``documents`` feeds, retrieval, and the agent read tools all agree by construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


def _matches_segment(rel: str, prefixes: tuple[str, ...]) -> bool:
    """Whether ``rel`` equals or is nested under any of ``prefixes`` as a *path segment*.

    ``"fort-wayne"`` matches ``fort-wayne`` and ``fort-wayne/…`` but never ``fort-wayne-foo/…``;
    ``"idem/fort-wayne"`` matches ``idem/fort-wayne/…`` but not a bare ``idem/…``.
    """
    norm = rel.replace("\\", "/")
    return any(norm == p or norm.startswith(f"{p}/") for p in prefixes)


@dataclass(frozen=True)
class CorpusScope:
    """A site's extracted-tree scope: an inclusion minus an exclusion (#762/#780/#1505).

    ``include is None`` is the whole tree (the reference build). ``exclude`` is the set of
    path-segment prefixes subtracted from it: Lima subtracts every registered peer's own scope so
    its cross-document domain stops swallowing ``idem/fort-wayne/…`` / ``oepa/troy-piqua/…`` &c.
    A non-reference site names its ``include`` prefixes and excludes nothing.
    """

    include: tuple[str, ...] | None
    exclude: tuple[str, ...] = ()

    def contains(self, rel: str) -> bool:
        """Whether an extracted artifact's ``rel`` (relative to ``data/extracted``) is in scope."""
        if self.exclude and _matches_segment(rel, self.exclude):
            return False
        if self.include is None:
            return True
        return _matches_segment(rel, self.include)


# The whole extracted tree, unqualified — the legacy ``None`` scope as a value. A safe default for
# helpers that read the tree directly; production Lima gets its peer-exclusion from
# :func:`~watermark.sites.effective_corpus_scope`, not from this.
WHOLE_TREE = CorpusScope(include=None)

# What the shared ``relpath_in_scope`` predicate and the scope-forwarding feed builders accept: the
# canonical :class:`CorpusScope`, or a legacy raw inclusion tuple / ``None`` (tests, ad-hoc callers).
CorpusScopeArg: TypeAlias = "CorpusScope | tuple[str, ...] | None"
