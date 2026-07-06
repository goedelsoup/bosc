"""Export Watermark's own compute footprint (the GreenOps report) as a global feed.

Lifts the committed ``data/reference/greenops/footprint.yaml`` — the usage → electricity →
water derivation ``watermark greenops footprint --write`` commits (#1083) — into the
feed-ready :class:`~watermark.greenops.model.GreenopsReport`, so the static export needs no
credentials or network (the same pattern as :mod:`watermark.site.economics` reading
``baseline.yaml``).

**Global** (#1076/#1084): the platform's footprint is a property of the platform, not of any
one watershed point, so this feed is emitted into every site's bundle identically (like
``network``). When the committed artifact is absent it degrades to the fully-modeled
:func:`~watermark.greenops.footprint.placeholder_report` rather than skipping — an honest
placeholder, every figure a stated ``assumption``, so the page never 500s or fakes a figure.
"""

from __future__ import annotations

from watermark.config import Settings
from watermark.greenops.footprint import (
    footprint_reference_path,
    load_footprint,
    placeholder_report,
)
from watermark.greenops.model import GreenopsReport


def export_greenops(settings: Settings) -> GreenopsReport:
    """The compute-footprint report as a feed (already feed-ready, every figure provenanced).

    Reads the committed footprint artifact; falls back to the modeled placeholder when it is
    absent so the global feed is always present. Guards the core discipline before returning —
    no footprint figure may claim to be ``[verified]`` (our own consumption is modeled, not
    metered).
    """
    path = footprint_reference_path(settings)
    report = load_footprint(path) if path.exists() else placeholder_report()
    report.assert_no_verified()
    return report
