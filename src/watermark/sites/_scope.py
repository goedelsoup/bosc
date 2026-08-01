"""The corpus scope value — which ``data/extracted`` relpaths a site's cross-document layer reads.

A site's record/timeline/entities/bundle domain is bounded to a subtree of the committed extracted
tree (#762/#780). The reference build (Lima) reads the *whole* tree **except** the subtrees every
registered peer owns, so a Piqua NPDES permit or a Fort Wayne §401 record never renders inside
Lima's Allen-County record (#1505); a non-reference site reads only its own prefixes.

Two shapes of prefix, because the corpus files a site's artifacts two ways: a collection **named**
for the site (``van-wert/…``) and a site subdirectory **inside** a collection named for its source
agency (``oepa/van-wert/…``). Both are derived from the slug — see :data:`_NEST` and
:func:`~watermark.sites.effective_corpus_scope` — so neither has to be enumerated per site (#1405).

This is the single value :func:`~watermark.sites.effective_corpus_scope` returns and the shared
``watermark.pipeline.corpus.relpath_in_scope`` predicate interprets, so export, timeline, entities,
the ``records``/``documents`` feeds, retrieval, and the agent read tools all agree by construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

#: Marker for a **site-attribution nesting** term (#1405). ``"*/van-wert"`` matches a path whose
#: *second* segment is ``van-wert`` under any collection — ``oepa/van-wert/…``, ``idem/van-wert/…``
#: — which is how ``data/documents`` and ``data/extracted`` file a site's artifacts inside a
#: collection that isn't named for it. It is not a general glob: only this one leading form is
#: understood, and only against the second segment.
_NEST = "*/"


def _matches_segment(rel: str, prefixes: tuple[str, ...]) -> bool:
    """Whether ``rel`` equals or is nested under any of ``prefixes`` as a *path segment*.

    ``"fort-wayne"`` matches ``fort-wayne`` and ``fort-wayne/…`` but never ``fort-wayne-foo/…``;
    ``"idem/fort-wayne"`` matches ``idem/fort-wayne/…`` but not a bare ``idem/…``. A ``"*/<slug>"``
    term (:data:`_NEST`) matches any ``<collection>/<slug>`` — the site-attribution nesting.
    """
    norm = rel.replace("\\", "/")
    segments = norm.split("/")
    for p in prefixes:
        if p.startswith(_NEST):
            if len(segments) >= 2 and segments[1] == p[len(_NEST) :]:
                return True
            continue
        if norm == p or norm.startswith(f"{p}/"):
            return True
    return False


@dataclass(frozen=True)
class CorpusScope:
    """A site's extracted-tree scope: an inclusion minus an exclusion (#762/#780/#1505).

    ``include is None`` is the whole tree (the reference build). ``exclude`` is the set of
    path-segment prefixes subtracted from it: Lima subtracts every registered peer's own scope so
    its cross-document domain stops swallowing ``idem/fort-wayne/…`` / ``oepa/troy-piqua/…`` &c.
    A non-reference site names its ``include`` prefixes and excludes nothing.

    Either tuple may carry ``"*/<slug>"`` site-attribution nesting terms (:data:`_NEST`) alongside
    plain prefixes; both sides read them the same way, so a peer's ``oepa/<slug>/`` subtree is
    granted to that peer and subtracted from Lima by the same term.
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
