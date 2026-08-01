"""Project the international candidates register into the content bundle (#1394, epic #1387).

A thin reader: the committed
``data/extracted/international/data-center-candidates.<scope>.yaml`` is already the feed shape
(:class:`~watermark.international.model.CandidatesRegister`), so this module resolves the path,
loads it, and hands it to the export — no re-derivation, and therefore nothing that can disagree
with the committed artifact.

**Network-global-host gated.** The register belongs to no watershed point, so it rides the
reference build's bundle alongside the other network-global feeds (the hypothesis matrix, the
catalog) rather than being copied into all 26 site bundles. The page that reads it
(``/network/candidates``) is a network-tier route, and a network-tier route resolves to the
reference site's bundle — so this is the same host role, not a special case.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from watermark.international.register import DEFAULT_SCOPE, load_register, register_path
from watermark.sites import is_reference_site

if TYPE_CHECKING:
    from watermark.config import Settings
    from watermark.international.model import CandidatesRegister


def export_data_center_candidates(
    settings: Settings, *, scope: str = DEFAULT_SCOPE
) -> CandidatesRegister | None:
    """The register for the bundle, or ``None`` so the feed self-skips.

    ``None`` in two cases, both of which must degrade rather than fabricate: the active site is
    not the network-global host, or no register has been assembled yet. The frontend then locks
    the section and says the sweep has not run — never renders an empty map as "no data centers
    were found abroad".
    """
    if not is_reference_site(settings.site):
        return None
    return load_register(register_path(settings, scope))
