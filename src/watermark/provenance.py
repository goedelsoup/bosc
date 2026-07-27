"""Shared provenance primitives for the evidence vocabulary (#60, #605).

The lightweight core the three provenance-tagged models speak —
:class:`watermark.site.feeds.Citation`, :class:`watermark.hypotheses.Citation`, and
:class:`watermark.hydrology.model.ProvenancedValue`. Each used to hand-mirror the same
``SourceKind``/``Confidence`` literals and the same ``verified`` predicate; those live here
once so the discipline can't drift. Kept dependency-free (no ``watermark.site`` / ``watermark.hydrology``
import) so any of them can import it without a cycle.
"""

from __future__ import annotations

from typing import Literal

# Where a value came from. document/connector are records or live gauges ([verified]);
# reference is a vendored published spec; assumption is a stated modeling input; derived
# is computed from other provenanced values.
SourceKind = Literal["document", "connector", "reference", "assumption", "derived"]
Confidence = Literal["high", "medium", "low"]


def as_confidence(value: object) -> Confidence:
    """Narrow an arbitrary (e.g. YAML-loaded) value to a :data:`Confidence` literal.

    Accepts ``high`` / ``medium`` / ``low`` case-insensitively. A present-but-unrecognized
    value is a real provenance error in the source table, so it raises rather than being
    silently masked by a ``# type: ignore`` on the ``str(...)`` — pass a known default
    (``entry.get("confidence", "high")``) for the absent case.
    """
    text = str(value).strip().lower()
    if text == "high":
        return "high"
    if text == "medium":
        return "medium"
    if text == "low":
        return "low"
    raise ValueError(f"invalid confidence {value!r}; expected one of high|medium|low")


def source_is_verified(source_kind: SourceKind) -> bool:
    """True for a value grounded in a record or a live gauge (the ``[verified]`` tag).

    ``reference`` (a vendored published spec) is authoritative but is *not* a record about
    the subject; ``assumption``/``derived`` are stated/computed — so none are "verified" in
    the evidence-discipline sense.
    """
    return source_kind in ("document", "connector")


# The evidence-discipline tag vocabulary the prose + dossier speak (``[verified]`` /
# ``[inference]`` / ``[reference]`` / ``[open]``). ``open`` is not derivable from a
# ``SourceKind`` — it marks an asserted-but-*unquantified* fact (a known predicate with no
# value yet), so it lives on the caller, not here.
EvidenceTag = Literal["verified", "inference", "reference"]
# The **full** four-tag register, including ``open`` — the vocabulary a model carries when it
# tags a claim rather than deriving the tag from a ``SourceKind`` (a defense parcel's
# attribution, a normalized fact's status). Lives here, next to its three-tag
# ``SourceKind``-derivable subset, so the four modules that speak it —
# :data:`watermark.site.feeds.FactStatus`, :class:`watermark.connectors.gis_schema.GisDefenseMeta`,
# ``watermark.site.corpus_nodes``, and the frontend's ``FactStatus`` — can't drift (#1663, ME-D).
EvidenceRegister = Literal["verified", "inference", "reference", "open"]


def evidence_tag(source_kind: SourceKind) -> EvidenceTag:
    """Map a value's ``source_kind`` to its evidence-discipline tag (#1587 facts feed).

    ``document``/``connector`` → ``verified``; ``reference`` → ``reference``;
    ``assumption``/``derived`` → ``inference``. The complement of
    :func:`source_is_verified`, but keeping the three non-``open`` tags distinct so a
    normalized fact can render ``[reference]`` vs ``[inference]`` rather than a bare boolean.
    """
    if source_is_verified(source_kind):
        return "verified"
    if source_kind == "reference":
        return "reference"
    return "inference"
