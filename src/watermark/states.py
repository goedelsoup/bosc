"""Per-state jurisdiction facts shared by the grid + economics stacks (#1645/H2).

The state's readable name and its retail-electric regulator are the same facts wherever
they are needed, but they used to be re-declared per module — ``_STATE_NAME`` in
:mod:`watermark.grid.ferc`, :mod:`watermark.grid.utility` and
:mod:`watermark.economics.connectors.eia`, and two differently-shaped PUC maps
(``_STATE_PUC`` / ``_RETAIL_REGULATOR``) across the first two. Hand-synced copies of a
per-key map are exactly what lost WPAFB/Xenia their FERC filer (A5/#1638), so they live
here once.

Deliberately a **leaf**: stdlib only, no ``watermark`` imports. Both the grid stack and
``watermark.economics.connectors`` read it, and ``grid.utility`` already imports
``economics.energy`` — a home inside either package would close an import cycle.

Registered sites cover OH + IN today. An unlisted state is **not** an error: every lookup
degrades to a generic, state-templated form rather than substituting a neighbour's
regulator, the same refusal discipline as the missing-state-denominator raise in
:mod:`watermark.grid.utility` (A1/#1638).
"""

from __future__ import annotations

from typing import NamedTuple

__all__ = ["STATE_NAME", "STATE_PUC", "StatePuc", "state_name", "state_puc"]


# Full state name for prose/citation labels, keyed by EIA two-letter state code. Keeps the
# readable form in per-site citations (Lima "Ohio", Fort Wayne "Indiana") rather than the bare
# abbreviation; also names the EIA state consumer-energy series (economics/connectors/eia.py).
STATE_NAME: dict[str, str] = {"OH": "Ohio", "IN": "Indiana"}


def state_name(state: str) -> str:
    """The readable name for an EIA state code; the code itself when unlisted."""
    return STATE_NAME.get(state, state)


class StatePuc(NamedTuple):
    """A state's retail-electric regulator, in the three forms the prose needs."""

    short: str  # woven into seam prose, e.g. "PUCO"
    full: str  # the regulator's name, e.g. "Public Utilities Commission of Ohio (PUCO)"
    retail_clause: str  # the citation sentence, e.g. "Ohio retail electric service is ..."


# Retail electric regulator by state. Intrastate retail service is state-PUC-regulated; the
# FERC/PUC seam (grid/ferc.py) and the serving-utility chain (grid/utility.py) both name it.
# NOTE: this is the regulator for an *investor-owned* utility — a municipal system sets its own
# retail rates under home rule and a cooperative's are member/board-set, so the caller resolves
# ownership first (``grid.utility._retail_regulator``); the state only decides the IOU case.
STATE_PUC: dict[str, StatePuc] = {
    "OH": StatePuc(
        short="PUCO",
        full="Public Utilities Commission of Ohio (PUCO)",
        retail_clause="Ohio retail electric service is PUCO-regulated (intrastate)",
    ),
    "IN": StatePuc(
        short="IURC",
        full="Indiana Utility Regulatory Commission (IURC)",
        retail_clause="Indiana retail electric service is IURC-regulated (intrastate)",
    ),
}


def state_puc(state: str) -> StatePuc:
    """The retail regulator for ``state``; a generic state-templated one when unlisted."""
    known = STATE_PUC.get(state)
    if known is not None:
        return known
    return StatePuc(
        short=f"{state} PUC",
        full=f"the {state} state public utilities commission",
        retail_clause=f"{state} retail electric service is state-regulated (intrastate)",
    )
