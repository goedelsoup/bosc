"""The campus annual-consumption assumption — one home for the load factor (#601).

The grid + economics scenarios all size a data-center campus's annual energy the same way:
``draw_mw x 8760 h x load_factor``. The load-factor assumption (0.9, near-flat 24x7) and the
GWh formula used to be redefined in four modules (grid/utility, grid/market, grid/policy,
economics/energy); they live here once so the assumption can't drift between them.

Each consumer keeps its own provenance *citation* prose (the issue references differ, and two
feed committed reference artifacts) — but the citation is **built** from :data:`LOAD_FACTOR` by
:func:`load_factor_cite` rather than re-typed, so the prose can't outlive a change to the number
it describes (H2/#1645: the figure was hand-written into four separate ``_LOAD_FACTOR_CITE``
literals, each free to keep saying "~0.9" after the assumption moved).
"""

from __future__ import annotations

HOURS_PER_YEAR = 8760.0
# Data centers run near-flat (24x7); capacity utilization ~0.9. A stated modeling assumption,
# shared across the grid + economics scenarios (#91/#94/#95).
LOAD_FACTOR = 0.9


def load_factor_cite(*, refs: str = "", subject: str = "") -> str:
    """The load-factor assumption's citation prose, with the number read from :data:`LOAD_FACTOR`.

    ``refs`` is the consumer's own issue trail (rendered ``(cf. …)``) and ``subject`` an optional
    noun for what runs near-flat — the two axes on which the four consumers' wording legitimately
    differs. Everything else, above all the *figure*, comes from here.

    These strings land in committed reference artifacts (``grid-profile.yaml``,
    ``demand-pressure.yaml``, ``federal-energy.yaml``), so a wording change moves data bytes.
    """
    what = f"near-flat 24x7 {subject}" if subject else "near-flat 24x7"
    cf = f" (cf. {refs})" if refs else ""
    return f"data-center capacity utilization ~{LOAD_FACTOR:g} ({what}); assumption{cf}"


def annual_consumption_gwh(draw_mw: float) -> float:
    """Campus annual electricity consumption in GWh: ``draw_mw x 8760 h x load factor`` (MWh→GWh)."""
    return draw_mw * HOURS_PER_YEAR * LOAD_FACTOR / 1000.0
