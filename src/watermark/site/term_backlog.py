"""Wiki term-backlog harvest (#1565, epic #1560 workstream A1).

Mine the platform's investigative prose — each site's extracted ``.md`` record plus the shared
``docs/`` / ``.claude/skills/`` / investigative-method layer — for **domain terms the wiki
glossary doesn't yet define**, and emit a per-site, density-ranked backlog that drives A2
(#1566, batch-author concepts).

Two passes over each prose blob:

* **lexicon** — high-precision. The curated domain vocabulary in :data:`LEXICON_RELPATH`
  (``data/concepts/lexicon.yaml``) is matched by every surface form (term + aliases); a hit that
  isn't already a concept lands in the backlog's ``terms``. This is the authoritative list A2
  authors from.
* **discovery** — high-recall. A mechanical acronym/initialism sweep surfaces every
  uppercase-and-undefined token (minus the lexicon's ``stopwords`` and anything already covered),
  landing in ``candidates`` for human triage — promote the good ones into the lexicon, drop the
  noise into ``stopwords``.

Membership of the extracted tree is the site's own :func:`watermark.sites.effective_corpus_scope`
(the same predicate the export/retrieval path uses), so a peer whose record lives under a
collection prefix is harvested correctly and Lima (the reference build) reads its own tree minus
every registered peer's. The ``network`` scope has no corpus scope — it is the shared repo-global
prose that belongs to no single site.

Everything here is pure and deterministic (sorted output) so the committed backlog under
``data/concepts/backlog/`` is stable and diffable, and the tests are hermetic.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel, ConfigDict, Field

from watermark.config import Settings, get_settings
from watermark.logging import get_logger
from watermark.site.feeds import ConceptItem

if TYPE_CHECKING:
    from watermark.sites import CorpusScope

log = get_logger(__name__)

# The curated lexicon, relative to ``settings.concepts_dir``.
LEXICON_RELPATH = "lexicon.yaml"
# Where `watermark term-backlog` writes the per-scope backlog, relative to ``concepts_dir``.
BACKLOG_DIRNAME = "backlog"
# The synthetic scope name for the shared, repo-global prose (docs/skills/method layer).
NETWORK_SCOPE = "network"

# Prose file stems that are repo scaffolding, not investigative record — never harvested.
_SKIP_STEMS = frozenset({"README", "ONBOARDING", "CLAUDE"})

# An acronym/initialism candidate: an uppercase-dominant token, optionally digit-flanked
# (so ``7Q10`` is reachable), captured with non-alphanumeric boundaries so it survives adjacent
# punctuation. Post-filtered in :func:`_accept_acronym`.
_ACRONYM_RE = re.compile(r"(?<![A-Za-z0-9])([0-9]{0,2}[A-Z][A-Z0-9]*[A-Z0-9])(?![A-Za-z0-9])")
# Longest acronym we treat as a glossary candidate; longer ALL-CAPS tokens are almost always
# transcript headings ("HYDROLOGY", "ECONOMICS", "ADJOURNMENT"), not initialisms.
_MAX_ACRONYM_LEN = 6
# A run of >= this many consecutive digits marks a permit/identifier (OHD000001, 1PE00007), not
# a glossary term.
_ID_DIGIT_RUN = re.compile(r"\d{3,}")
# Context window (characters) captured around a term's first occurrence, for the authoring hint.
_EXAMPLE_RADIUS = 90


def _normalize(text: str) -> str:
    """A surface form reduced to its comparison key: lowercase, alphanumerics only.

    ``"7Q10 low flow"`` and ``"7q10-low-flow"`` both key to ``"7q10lowflow"``; ``"NPDES"`` to
    ``"npdes"``. Used to match a candidate against the glossary and the lexicon regardless of
    case, spacing, or punctuation.
    """
    return re.sub(r"[^a-z0-9]+", "", text.lower())


# --- lexicon ------------------------------------------------------------------------------------
class LexiconEntry(BaseModel):
    """One curated domain term the harvest looks for.

    ``extra="forbid"`` so a typo'd key in ``lexicon.yaml`` is a loud error, not a dropped field.
    """

    model_config = ConfigDict(extra="forbid")

    term: str
    aliases: list[str] = Field(default_factory=list)
    kind: str = "term"  # concept | term | method (mirrors the concept frontmatter)
    tags: list[str] = Field(default_factory=list)
    note: str = ""
    # Homonym phrases that disqualify a match when the match falls inside them — the escape hatch
    # for a surface form that collides with an unrelated term (``variance`` in "mercury variance",
    # ``dilution`` in "isotope-dilution", ``TIF`` in a ``.tif`` file path). Whitespace matches
    # whitespace or a hyphen; no other anchoring — containment is what disqualifies.
    exclude: list[str] = Field(default_factory=list)

    @property
    def surface_forms(self) -> list[str]:
        """The canonical term plus every alias — all the strings that count as a hit."""
        return [self.term, *self.aliases]


class Lexicon(BaseModel):
    """The parsed ``lexicon.yaml``: the curated vocabulary plus the discovery stoplist."""

    model_config = ConfigDict(extra="forbid")

    terms: list[LexiconEntry] = Field(default_factory=list)
    stopwords: list[str] = Field(default_factory=list)

    @property
    def stopword_keys(self) -> frozenset[str]:
        """Normalized stopword tokens, for case/spacing-insensitive discovery filtering."""
        return frozenset(_normalize(w) for w in self.stopwords)


def load_lexicon(concepts_dir: Path) -> Lexicon:
    """Load ``<concepts_dir>/lexicon.yaml``; an absent file yields an empty lexicon."""
    path = concepts_dir / LEXICON_RELPATH
    if not path.is_file():
        log.warning("term_backlog.lexicon_missing", path=str(path))
        return Lexicon()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Lexicon.model_validate(data)


# --- glossary index -----------------------------------------------------------------------------
def build_glossary_index(concepts: Sequence[ConceptItem]) -> frozenset[str]:
    """Every already-defined term as a normalized key: each concept's slug, title, and aliases.

    A candidate whose normalized form is in this set is already in the glossary and is dropped
    from the backlog — so an entry stays out of the backlog the moment its concept lands.
    """
    keys: set[str] = set()
    for c in concepts:
        for form in (c.slug, c.title, *c.aliases):
            key = _normalize(form)
            if key:
                keys.add(key)
    return frozenset(keys)


# --- prose sources ------------------------------------------------------------------------------
def iter_prose_files(root: Path, *, scope: CorpusScope | None = None) -> Iterator[Path]:
    """Yield investigative-prose ``.md`` files under ``root``, README/ONBOARDING/CLAUDE excluded.

    When ``scope`` is a :class:`watermark.sites.CorpusScope`, a file is kept only if its path
    relative to ``root`` is in scope — the same ``relpath_in_scope`` predicate the export and
    retrieval paths use, so a site is harvested over exactly its own corpus region. ``scope=None``
    keeps every file (used for the shared ``network`` roots).
    """
    if not root.is_dir():
        return
    from watermark.pipeline.corpus import relpath_in_scope

    for path in sorted(root.rglob("*.md")):
        if path.stem.upper() in _SKIP_STEMS:
            continue
        if scope is not None and not relpath_in_scope(str(path.relative_to(root)), scope):
            continue
        yield path


def _flatten(text: str) -> str:
    """Collapse all whitespace to single spaces so wrapped phrases (``constructive\\ndenial``)
    match and context snippets read as one line."""
    return re.sub(r"\s+", " ", text).strip()


# --- matching -----------------------------------------------------------------------------------
def _compile_surface_pattern(forms: Iterable[str]) -> re.Pattern[str]:
    """A case-insensitive alternation over ``forms``, longest-first, with non-word boundaries.

    Internal whitespace in a multi-word form is matched flexibly (``\\s+``) so it still matches
    after :func:`_flatten` (single spaces) and would match raw multi-space text too.
    """
    # Longest-first, ties broken lexically — a fully deterministic alternation order (so the
    # compiled pattern is stable regardless of set-iteration / hash-seed order).
    parts = sorted({f.strip() for f in forms if f.strip()}, key=lambda f: (-len(f), f))
    alt = "|".join(re.escape(f).replace(r"\ ", r"\s+") for f in parts)
    # The non-capturing group is load-bearing: without it the boundary anchors would bind only to
    # the first/last alternative (``|`` has lowest precedence), matching middle forms as substrings.
    return re.compile(rf"(?<![A-Za-z0-9])(?:{alt})(?![A-Za-z0-9])", re.IGNORECASE)


def _compile_exclude(phrase: str) -> re.Pattern[str]:
    """A case-insensitive pattern for a homonym-disqualifying phrase, unanchored.

    No boundary anchors: containment of the term match inside the phrase's span is what
    disqualifies (so ``.tif`` disqualifies the ``TIF`` inside a ``…date.tif`` path). Internal
    whitespace matches whitespace *or* a hyphen, so ``isotope dilution`` catches ``isotope-dilution``.
    """
    return re.compile(re.escape(phrase.strip()).replace(r"\ ", r"[\s\-]+"), re.IGNORECASE)


def _accept_acronym(token: str, *, exclude: frozenset[str], stopwords: frozenset[str]) -> bool:
    """Whether a discovered token is a plausible glossary candidate.

    Rejects the long tail of noise: over-length ALL-CAPS headings, identifier/permit numbers,
    single-capital tokens, and anything already covered (glossary + lexicon) or stoplisted.
    """
    if not (2 <= len(token) <= _MAX_ACRONYM_LEN):
        return False
    if sum(ch.isupper() for ch in token) < 2:  # needs >= 2 caps (kills "7Q10"-style single-cap)
        return False
    if _ID_DIGIT_RUN.search(token):  # OHD000001, 1PE00007 — identifiers, not terms
        return False
    key = _normalize(token)
    return key not in exclude and key not in stopwords


def _example(flat_text: str, match: re.Match[str]) -> str:
    """A one-line context snippet around ``match`` in already-flattened ``flat_text``."""
    start = max(0, match.start() - _EXAMPLE_RADIUS)
    end = min(len(flat_text), match.end() + _EXAMPLE_RADIUS)
    snippet = flat_text[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(flat_text):
        snippet = snippet + "…"
    return snippet


# --- accumulation -------------------------------------------------------------------------------
class BacklogTerm(BaseModel):
    """One undefined term in a backlog: what it is, how much it's used, and where."""

    model_config = ConfigDict(extra="forbid")

    term: str
    kind: str = "term"
    tags: list[str] = Field(default_factory=list)
    provenance: str  # "lexicon" | "discovery"
    count: int = 0
    sources: dict[str, int] = Field(default_factory=dict)  # relpath -> occurrences
    example: str = ""
    note: str = ""


class _Accumulator:
    """Running per-term tallies as prose files are scanned; frozen into :class:`BacklogTerm`s."""

    def __init__(self, term: str, *, kind: str, tags: list[str], provenance: str, note: str):
        self.term = term
        self.kind = kind
        self.tags = tags
        self.provenance = provenance
        self.note = note
        self.count = 0
        self.sources: Counter[str] = Counter()
        self.example = ""

    def add(self, relpath: str, hits: int, example: str) -> None:
        if hits <= 0:
            return
        self.count += hits
        self.sources[relpath] += hits
        if not self.example and example:
            self.example = example

    def freeze(self) -> BacklogTerm:
        return BacklogTerm(
            term=self.term,
            kind=self.kind,
            tags=self.tags,
            provenance=self.provenance,
            count=self.count,
            sources=dict(sorted(self.sources.items())),
            example=self.example,
            note=self.note,
        )


# Default cap on discovery candidates written per scope; the long tail is noise, and the
# committed backlog should stay signal-only. Surfaced as ``candidates_found`` when it bites.
DEFAULT_MAX_CANDIDATES = 40


class ScopeBacklog(BaseModel):
    """The harvest for one scope (a site slug or ``network``): its undefined-term backlog."""

    model_config = ConfigDict(extra="forbid")

    scope: str
    sources_scanned: int = 0
    glossary_defined: int = 0
    candidates_found: int = 0  # total discovered before the top-N cap (== len(candidates) if none)
    terms: list[BacklogTerm] = Field(default_factory=list)  # lexicon-backed, ready to author
    candidates: list[BacklogTerm] = Field(default_factory=list)  # discovered, needs triage (capped)


def _rank(accumulators: Iterable[_Accumulator], *, min_count: int) -> list[BacklogTerm]:
    """Freeze and sort accumulators by descending count then term (deterministic)."""
    frozen = [a.freeze() for a in accumulators if a.count >= min_count]
    frozen.sort(key=lambda t: (-t.count, t.term.lower()))
    return frozen


def harvest_scope(
    scope_name: str,
    files: Sequence[tuple[str, str]],
    *,
    lexicon: Lexicon,
    glossary_index: frozenset[str],
    defined_count: int = 0,
    min_count: int = 1,
    discover: bool = True,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
) -> ScopeBacklog:
    """Harvest one scope from ``files`` — a sequence of ``(relpath, text)`` prose blobs.

    ``relpath`` is the path recorded in the backlog's ``sources`` (repo-relative by convention).
    ``defined_count`` is the number of concepts already in the glossary (reported for context).
    ``max_candidates`` caps the discovery bucket (0 = uncapped); the pre-cap total is reported as
    ``candidates_found``. Pure: no filesystem access, so tests pass literal blobs.
    """
    if min_count < 1:
        raise ValueError(f"min_count must be >= 1, got {min_count}")
    if max_candidates < 0:
        raise ValueError(f"max_candidates must be >= 0, got {max_candidates}")

    # Lexicon entries not already defined in the glossary, each with a compiled surface pattern
    # and (optionally) homonym-exclusion patterns.
    lex_accs: dict[str, _Accumulator] = {}
    lex_patterns: dict[str, re.Pattern[str]] = {}
    lex_excludes: dict[str, list[re.Pattern[str]]] = {}
    lex_surface_keys: set[str] = set()
    for entry in lexicon.terms:
        keys = {_normalize(f) for f in entry.surface_forms if _normalize(f)}
        lex_surface_keys |= keys
        if keys & glossary_index:  # already a concept — skip, but still exclude from discovery
            continue
        lex_accs[entry.term] = _Accumulator(
            entry.term,
            kind=entry.kind,
            tags=list(entry.tags),
            provenance="lexicon",
            note=entry.note,
        )
        lex_patterns[entry.term] = _compile_surface_pattern(entry.surface_forms)
        if entry.exclude:
            lex_excludes[entry.term] = [_compile_exclude(p) for p in entry.exclude]

    # Tokens discovery must never surface: already-defined + every lexicon surface form.
    discovery_exclude = glossary_index | frozenset(lex_surface_keys)
    disc_accs: dict[str, _Accumulator] = {}

    for relpath, raw in files:
        flat = _flatten(raw)
        if not flat:
            continue
        _harvest_lexicon(flat, relpath, lex_accs, lex_patterns, lex_excludes)
        if discover:
            _harvest_discovery(flat, relpath, disc_accs, discovery_exclude, lexicon.stopword_keys)

    ranked_candidates = _rank(disc_accs.values(), min_count=max(min_count, 2))
    capped = ranked_candidates[:max_candidates] if max_candidates > 0 else ranked_candidates
    return ScopeBacklog(
        scope=scope_name,
        sources_scanned=len(files),
        glossary_defined=defined_count,
        candidates_found=len(ranked_candidates),
        terms=_rank(lex_accs.values(), min_count=min_count),
        candidates=capped,
    )


def _harvest_lexicon(
    flat: str,
    relpath: str,
    accs: dict[str, _Accumulator],
    patterns: dict[str, re.Pattern[str]],
    excludes: dict[str, list[re.Pattern[str]]],
) -> None:
    """Fold one file's lexicon hits into ``accs``, overlap-aware.

    All surface matches across every term are collected, then resolved so **the longest matching
    surface form wins any overlap** — so ``OEPA``'s "Ohio EPA" claims the span and the generic
    ``EPA`` doesn't also count it. A match contained in one of its term's exclude spans (a homonym
    like "mercury variance") is dropped. Non-overlapping matches are all retained.
    """
    # (start, end, term, match) for every surface hit of every term.
    spans: list[tuple[int, int, str, re.Match[str]]] = []
    for term, pattern in patterns.items():
        spans.extend((m.start(), m.end(), term, m) for m in pattern.finditer(flat))
    if not spans:
        return
    # Per-term exclude spans (a match inside one of these, for the same term, is a homonym).
    blocked: dict[str, list[tuple[int, int]]] = {}
    for term, pats in excludes.items():
        ex_spans = [(m.start(), m.end()) for pat in pats for m in pat.finditer(flat)]
        if ex_spans:
            blocked[term] = ex_spans

    # Longest-span-first at each position (ties broken lexically → deterministic); greedily accept
    # a span only if it neither is excluded nor overlaps an already-accepted (longer/earlier) span.
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0]), s[2]))
    occupied: list[tuple[int, int]] = []
    kept: list[tuple[str, re.Match[str]]] = []
    for start, end, term, m in spans:
        if any(bs <= start and end <= be for bs, be in blocked.get(term, ())):
            continue
        if any(start < e and s < end for s, e in occupied):
            continue
        occupied.append((start, end))
        kept.append((term, m))

    per_term: Counter[str] = Counter(term for term, _ in kept)
    first: dict[str, re.Match[str]] = {}
    for term, m in kept:
        first.setdefault(term, m)
    for term, hits in per_term.items():
        accs[term].add(relpath, hits, _example(flat, first[term]))


def _harvest_discovery(
    flat: str,
    relpath: str,
    accs: dict[str, _Accumulator],
    exclude: frozenset[str],
    stopwords: frozenset[str],
) -> None:
    """Fold one file's acronym-discovery hits into ``accs`` (keyed by the exact token)."""
    per_file: Counter[str] = Counter()
    first: dict[str, re.Match[str]] = {}
    for m in _ACRONYM_RE.finditer(flat):
        token = m.group(1)
        if not _accept_acronym(token, exclude=exclude, stopwords=stopwords):
            continue
        per_file[token] += 1
        first.setdefault(token, m)
    for token, hits in per_file.items():
        acc = accs.get(token)
        if acc is None:
            acc = accs[token] = _Accumulator(
                token, kind="term", tags=[], provenance="discovery", note=""
            )
        acc.add(relpath, hits, _example(flat, first[token]))


# --- orchestration (filesystem-backed) ----------------------------------------------------------
# The shared, repo-global prose roots that belong to no single site — harvested as ``network``.
NETWORK_ROOTS: tuple[str, ...] = ("docs", ".claude/skills")


def load_glossary(concepts_dir: Path) -> tuple[frozenset[str], int]:
    """Load every concept (site-tag filter *not* applied) → ``(normalized index, count)``.

    Unlike :func:`watermark.site.concepts.load_concepts`, this includes site-scoped concepts, so a
    Lima-only term already defined never re-surfaces in another site's backlog.
    """
    from watermark.site.concepts import parse_concept

    items: list[ConceptItem] = []
    for path in sorted(concepts_dir.glob("*.md")):
        if path.name.upper() == "README.MD":
            continue
        try:
            items.append(parse_concept(path))
        except Exception as exc:  # a malformed concept must not abort the harvest
            log.warning("term_backlog.concept_parse_failed", path=str(path), error=str(exc))
    return build_glossary_index(items), len(items)


def _read_prose(
    root: Path, repo_root: Path, *, scope: CorpusScope | None = None
) -> list[tuple[str, str]]:
    """Read prose files under ``root`` into ``(repo-relative path, text)`` blobs."""
    blobs: list[tuple[str, str]] = []
    for path in iter_prose_files(root, scope=scope):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            rel = str(path.relative_to(repo_root))
        except ValueError:
            rel = str(path)
        blobs.append((rel, text))
    return blobs


def harvest_backlog(
    settings: Settings | None = None,
    *,
    sites: Sequence[str] | None = None,
    include_network: bool = True,
    min_count: int = 1,
    discover: bool = True,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
) -> dict[str, ScopeBacklog]:
    """Harvest the term backlog for every requested scope, keyed by scope name.

    ``sites=None`` harvests every registered site; ``include_network`` adds the shared
    ``docs`` / ``.claude/skills`` prose as the ``network`` scope. The lexicon and glossary are
    loaded once and shared across scopes.
    """
    from watermark.sites import SITES, effective_corpus_scope

    settings = settings or get_settings()
    repo_root = settings.data_dir.parent
    lexicon = load_lexicon(settings.concepts_dir)
    glossary_index, defined_count = load_glossary(settings.concepts_dir)

    slugs = list(sites) if sites is not None else list(SITES)
    out: dict[str, ScopeBacklog] = {}
    for slug in slugs:
        profile = SITES.get(slug)
        if profile is None:
            log.warning("term_backlog.unknown_site", site=slug)
            continue
        scope = effective_corpus_scope(profile)
        blobs = _read_prose(settings.extracted_dir, repo_root, scope=scope)
        out[slug] = harvest_scope(
            slug,
            blobs,
            lexicon=lexicon,
            glossary_index=glossary_index,
            defined_count=defined_count,
            min_count=min_count,
            discover=discover,
            max_candidates=max_candidates,
        )
    if include_network:
        net_blobs: list[tuple[str, str]] = []
        for rel in NETWORK_ROOTS:
            net_blobs += _read_prose(repo_root / rel, repo_root)
        out[NETWORK_SCOPE] = harvest_scope(
            NETWORK_SCOPE,
            net_blobs,
            lexicon=lexicon,
            glossary_index=glossary_index,
            defined_count=defined_count,
            min_count=min_count,
            discover=discover,
            max_candidates=max_candidates,
        )
    return out


# --- rendering ----------------------------------------------------------------------------------
_BACKLOG_HEADER = (
    "# Generated by `watermark term-backlog` — do not edit by hand; regenerate.\n"
    "# Undefined domain terms harvested from this scope's prose (#1565, epic #1560 A1).\n"
    "#   terms       — curated-lexicon hits not yet in data/concepts/; author these (A2, #1566).\n"
    "#   candidates  — mechanically discovered acronyms needing triage (promote or stoplist).\n"
    "# `count` is total occurrences; `sources` maps each file to its hit count.\n"
)


def _term_to_dict(t: BacklogTerm) -> dict[str, object]:
    """A backlog term as an ordered plain dict for stable YAML (empty fields omitted)."""
    d: dict[str, object] = {"term": t.term, "kind": t.kind}
    if t.tags:
        d["tags"] = t.tags
    d["provenance"] = t.provenance
    d["count"] = t.count
    if t.note:
        d["note"] = t.note
    if t.example:
        d["example"] = t.example
    d["sources"] = t.sources
    return d


def render_backlog(backlog: ScopeBacklog) -> str:
    """Render one scope's backlog as commented, deterministic YAML."""
    body: dict[str, object] = {
        "scope": backlog.scope,
        "sources_scanned": backlog.sources_scanned,
        "glossary_defined": backlog.glossary_defined,
        "term_count": len(backlog.terms),
        "candidate_count": len(backlog.candidates),
        "candidates_found": backlog.candidates_found,
        "terms": [_term_to_dict(t) for t in backlog.terms],
        "candidates": [_term_to_dict(t) for t in backlog.candidates],
    }
    dumped = yaml.safe_dump(body, sort_keys=False, allow_unicode=True, width=100)
    return _BACKLOG_HEADER + dumped


def write_backlog(backlog: ScopeBacklog, out_dir: Path) -> Path | None:
    """Write ``<out_dir>/<scope>.yaml`` when the scope has any harvested term; else skip.

    Returns the written path, or ``None`` when nothing was harvested. An empty scope writes no
    file *and* removes a stale ``<scope>.yaml`` from a prior run (e.g. once its last term is
    authored), so a regeneration never leaves a signal-free artifact behind.
    """
    path = out_dir / f"{backlog.scope}.yaml"
    if not backlog.terms and not backlog.candidates:
        path.unlink(missing_ok=True)
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(render_backlog(backlog), encoding="utf-8")
    return path
