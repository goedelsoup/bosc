"""The committed record itself, projected as mirror nodes (#2134, Epic #2124).

The mirror carried entities, relationships, concepts, people, leads and hypotheses — every
one of them a *derivation* over the corpus — and never the corpus. So the evidence standings
the extractions actually assert were invisible to it: 2,145 ``[verified]`` tags sat in
``data/extracted/**`` while the mirror held **none**, and ``verified-unsourced`` returned
early at zero. That zero looked exactly like a clean bill of health and meant "nothing was
projected".

A ``record`` node is one committed extraction, and it exists to answer one question:
**does this record's evidence rest on a registered source?** So it carries the file's claim
profile and a ``rests-on`` link to the catalog entry covering it. A record whose file no
catalog entry registers gets no such link — and, if it asserts anything at ``[verified]``,
that is precisely the finding.

**What it carries, and why it is a profile rather than a transcription.** The tags in this
corpus are inline in dense narrative fields — a single commissioners' ledger entry runs to
several hundred words and mixes ``[verified: agenda]`` with ``[reference]`` and an explicit
*"do NOT upgrade to [verified]"*. Excerpting "the assertion a tag belongs to" out of that is
an editorial act with no correct mechanical answer, and getting it wrong in the flattering
direction is the exact error the check exists to catch. So this projects **no prose**:

* ``claim_standings`` — the distinct standings the file carries, bracketed. This is what
  yidam counts, so a record asserting three verified figures counts as *one* verified claim:
  the question being asked is about the record, not about each figure.
* ``claim_counts`` — the true per-tag totals, so nothing is lost by the line above.

**``[open]`` is carried too, and that is deliberate.** yidam's open-question predicate reads
``[open]`` anywhere in a node's text, so projecting the real profile raises the corpus's open
count. Carrying ``[verified]`` while suppressing ``[open]`` would report only the standings
that flatter, which is the same error in the other direction.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from watermark.config import Settings, get_settings
from watermark.logging import get_logger
from watermark.sites import active_profile, effective_corpus_scope

log = get_logger(__name__)

#: The claim vocabulary a record can assert. `reference` is BOSC's fourth tag and yidam has no
#: counter for it, so it is recorded in `claim_counts` and never emitted as a token — a marker
#: yidam cannot read is noise in a node it can.
_STANDINGS: tuple[str, ...] = ("verified", "inference", "open", "reference")
#: yidam's three — the ones `claims::tally` counts and the only ones written as tokens.
_COUNTED: tuple[str, ...] = ("verified", "inference", "open")

_TAG_RE = {tag: re.compile(re.escape(f"[{tag}]")) for tag in _STANDINGS}

#: Extraction file types that carry reviewed structured claims.
_SUFFIXES = (".yaml", ".yml", ".md")

# A comment that is a horizontal rule rather than a name — dashes, equals, box-drawing, and the
# `--- words ---` form, whose words are a SECTION's name and not the record's.
_RULE_RE = re.compile(r"[-=_*─—]{3,}.*|.*[-=_*─—]{3,}")

#: Documentation that lives *in* the extracted tree without being a record of anything. These
#: carry claim markers while describing the collection rather than asserting about the subject
#: — `grid/README.md` states the tag legend and scores three `[verified]` for it — so
#: projecting them would manufacture six ungrounded verified claims out of prose about
#: filing. Matched by exact filename, because the rule is a naming convention and a
#: substring rule would swallow a real record that happens to be named for a readme.
_NOT_RECORDS = frozenset({"README.md", "ONBOARDING.md", "COMPLETENESS.md"})


@dataclass(frozen=True)
class CorpusRecord:
    """One committed extraction, as the mirror sees it."""

    relpath: str  # relative to `data/extracted/`
    data_relpath: str  # relative to the repo (`data/extracted/…`) — what the catalog registers
    collection: str  # the first path segment: `oepa`, `legal`, `permits`, …
    title: str
    counts: dict[str, int]  # per-standing totals, including `reference`

    @property
    def standings(self) -> list[str]:
        """The bracketed tokens to write — yidam's three only, strongest first."""
        return [f"[{tag}]" for tag in _COUNTED if self.counts.get(tag)]

    @property
    def asserts_anything(self) -> bool:
        return any(self.counts.get(tag) for tag in _STANDINGS)


def _title(path: Path, text: str) -> str:
    """A human name for the record — its own if it states one, else its filename.

    Read with a regex rather than by parsing: these files are large, many are markdown, and a
    mirror projection must never fail because one extraction has a YAML quirk.

    ⚠️ A ``#`` line is only a title where it is the document's OWN opening line. In markdown it is
    a heading anywhere; in YAML it is a comment, and **position is the whole difference between a
    header and a section banner**. Many extractions open with a descriptive comment block — `#
    Tetra Tech "Opinion of Probable Project Cost" — Project BOSC` — which is the best name the
    file has. Many others *also* organise their middles with rules, and matching anywhere in the
    file took whichever came first: seven records published `--- the two certifications ------`
    or a bare row of dashes as their names. So a YAML comment is read only from the leading
    comment block, and a candidate that is nothing but punctuation is refused wherever it sits.
    """
    for pattern in (r"^title:\s*(.+)$", r"^name:\s*(.+)$"):
        if (m := re.search(pattern, text, re.MULTILINE)) is not None:
            found = m.group(1).strip().strip("\"'")
            if found:
                return found[:160]
    for line in _heading_candidates(path, text):
        if (m := re.fullmatch(r"#\s+(.+)", line)) is not None:
            found = m.group(1).strip().strip("\"'")
            if _RULE_RE.fullmatch(found) is None and found:
                return found[:160]
    return path.stem.replace("-", " ").replace(".", " · ")


def _heading_candidates(path: Path, text: str) -> Iterator[str]:
    """The lines a ``#`` title may be read from: any line in markdown, the header block in YAML."""
    for line in text.splitlines():
        stripped = line.strip()
        if path.suffix != ".md" and stripped and not stripped.startswith("#"):
            return  # past the leading comment block; everything below is a section banner
        yield stripped


def load_records(settings: Settings | None = None) -> list[CorpusRecord]:
    """Every committed extraction in the active site's corpus scope, with its claim profile.

    Scope is :func:`~watermark.sites.effective_corpus_scope` — the **same** predicate the
    export, the retrieval and the agent read tools use — so a peer projects its own record and
    never Lima's, and Lima projects the whole tree minus every peer's subtree.
    """
    from watermark.pipeline.corpus import relpath_in_scope

    settings = settings or get_settings()
    extracted = settings.extracted_dir
    if not extracted.exists():
        return []
    scope = effective_corpus_scope(active_profile(settings))

    records: list[CorpusRecord] = []
    for path in sorted(extracted.rglob("*")):
        if not path.is_file() or path.suffix not in _SUFFIXES or path.name in _NOT_RECORDS:
            continue
        rel = path.relative_to(extracted).as_posix()
        if not relpath_in_scope(rel, scope):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        counts = {tag: len(rx.findall(text)) for tag, rx in _TAG_RE.items()}
        records.append(
            CorpusRecord(
                relpath=rel,
                data_relpath=f"data/extracted/{rel}",
                collection=rel.split("/", 1)[0] if "/" in rel else "",
                title=_title(path, text),
                counts={k: v for k, v in counts.items() if v},
            )
        )
    log.info(
        "corpus_records.loaded",
        site=settings.site,
        records=len(records),
        asserting=sum(1 for r in records if r.asserts_anything),
        verified=sum(r.counts.get("verified", 0) for r in records),
    )
    return records
