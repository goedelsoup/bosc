"""Hydrologic soil group vocabulary + the dual-group drainage switch (WS-20 / #1620).

USDA NRCS gives some soils a **dual** hydrologic soil group — ``A/D``, ``B/D``, ``C/D``.
A dual class is assigned *only* to a soil that is group ``D`` in its natural condition and
that can be drained: the **first** letter is the group the soil behaves as where artificial
drainage is installed **and maintained**, the **second** is that natural, undrained
condition. Which letter a scenario runs on is therefore a modeling decision about
*drainage*, not a string operation.

That distinction is load-bearing here. Collapsing ``B/D`` with an implicit ``[:1]`` picks
the drained — lower curve number, lower runoff — class **everywhere**, including for
post-development scenarios where construction severs or reroutes the field tile that earned
the drained rating in the first place. Across a Black-Swamp lake-plain corridor of ``B/D``
and ``C/D`` clays that is a systematic, one-directional understatement of post-development
runoff. So the choice is made explicitly, per scenario, and carries its provenance:
:func:`resolve_hsg` never guesses, and the consumers that take a single letter
(:func:`watermark.hydrology.solver.curve_number.cn_for`, the SWMM deck's Horton
infiltration) **refuse** an unresolved dual group rather than slicing one.

Deliberately a **leaf**: stdlib + ``typing`` only, no ``watermark`` imports. Both
:mod:`watermark.sites` (which carries the per-site switch on ``SiteProfile``) and
:mod:`watermark.hydrology` read it, and a home inside either would close the
``config → sites → hydrology → config`` loop — the same reason
:mod:`watermark.connectors.gis_schema` sits outside ``watermark.hydrology.connectors``.
"""

from __future__ import annotations

from typing import Literal

__all__ = [
    "DEFAULT_DRAINAGE_BASIS",
    "DUAL_HSG_RULE",
    "HSG_LETTERS",
    "DrainageCondition",
    "hsg_code",
    "is_dual_hsg",
    "normalize_hsg",
    "resolve_hsg",
]

#: The four single hydrologic soil groups, in increasing-runoff order (A infiltrates most).
HSG_LETTERS: tuple[str, ...] = ("A", "B", "C", "D")

#: Which condition of a dual group a scenario is modeled under. ``drained`` = artificial
#: drainage installed and maintained (the first letter); ``undrained`` = the soil's natural
#: condition (the second letter, always ``D``).
DrainageCondition = Literal["drained", "undrained"]

_DUAL: dict[str, tuple[str, str]] = {
    # group -> (drained letter, undrained letter)
    "A/D": ("A", "D"),
    "B/D": ("B", "D"),
    "C/D": ("C", "D"),
}

#: The published rule the resolution implements — cited wherever a resolved letter is tagged.
DUAL_HSG_RULE = (
    "USDA NRCS, National Engineering Handbook Part 630 Ch. 7 'Hydrologic Soil Groups' / TR-55 "
    "Ch. 2: a dual group (A/D, B/D, C/D) is assigned only to a soil that is group D in its "
    "natural condition and that can be drained. The first letter is the group where artificial "
    "drainage is installed and maintained; the second is the natural, undrained condition."
)

#: Why the default pre/post switch is set the way it is — the stated modeling basis a site
#: inherits unless its own record says otherwise (``SiteProfile.drainage_condition_citation``).
DEFAULT_DRAINAGE_BASIS = (
    "Stated Tier-0 modeling basis (WS-20). Pre-development runs the DRAINED letter: the prior "
    "cover is tile-drained cropland, which is the installed-and-maintained condition TR-55 "
    "requires for the drained class. Post-development runs the UNDRAINED letter: site work "
    "severs or reroutes field tile it does not then maintain, so the soil's natural group is "
    "the conservative design basis. Neither is a fact about a particular field's tile — a site "
    "whose record shows otherwise overrides both on its SiteProfile with its own citation."
)


def normalize_hsg(group: str) -> str:
    """A verbatim SSURGO ``hydgrp`` value in canonical form (``" b/d "`` -> ``"B/D"``)."""
    return group.strip().upper().replace(" ", "")


def is_dual_hsg(group: str) -> bool:
    """True when ``group`` is a dual class carrying both a drained and an undrained letter."""
    return normalize_hsg(group) in _DUAL


def resolve_hsg(group: str, condition: DrainageCondition) -> str:
    """The single A-D letter ``group`` behaves as under ``condition``.

    A dual group resolves to its drained (first) or undrained (second) letter; a single group
    is the same under either condition — only naturally-``D`` soils are ever dual-classed, so
    an ``A``/``B``/``C`` rating already *is* the soil's undrained behaviour and a ``D`` cannot
    be drained into a lower group without a re-rating.

    Raises ``ValueError`` on anything that is not a recognised group. There is deliberately no
    fallback: an unparseable soil rating that quietly became "C" would be a fabricated
    infiltration class, and the ``[:1]`` this replaces was exactly that failure in miniature.
    """
    canonical = normalize_hsg(group)
    dual = _DUAL.get(canonical)
    if dual is not None:
        return dual[0] if condition == "drained" else dual[1]
    if canonical in HSG_LETTERS:
        return canonical
    raise ValueError(
        f"unrecognised hydrologic soil group {group!r} — expected one of "
        f"{', '.join((*HSG_LETTERS, *sorted(_DUAL)))}"
    )


def hsg_code(letter: str) -> float:
    """The 1-4 index of a single group (``A`` -> 1.0 … ``D`` -> 4.0) for a coded value.

    Raises ``ValueError`` for a dual or unknown group: a code is a single-group ordinal, so
    the drainage condition has to be resolved with :func:`resolve_hsg` first.
    """
    canonical = normalize_hsg(letter)
    if canonical not in HSG_LETTERS:
        raise ValueError(
            f"hydrologic soil group code needs a single group A-D, got {letter!r}"
            + (
                " — resolve the drainage condition first (resolve_hsg)"
                if is_dual_hsg(letter)
                else ""
            )
        )
    return float(HSG_LETTERS.index(canonical) + 1)
