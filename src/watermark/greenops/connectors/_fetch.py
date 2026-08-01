"""The one cached-fetch call shape every GreenOps connector uses.

Each provider pull (AWS Cost Explorer / Sustainability, Anthropic Admin, GitHub billing,
EPA eGRID) resolves through the shared :func:`watermark.connectors.cached_get_traced` with
the *same* GreenOps settings plumbing — cache root, offline flag, fixtures dir, TTL, and the
subsystem's :class:`GreenopsOfflineError`. Threading those five arguments through four
connectors by hand invited them to drift apart; this is the single place they are wired.

It also returns the export's :data:`~watermark.greenops.model.SourceBasis` alongside the
payload (#1643/F3): a committed **fixture** replay is a shaped sample, a **live** pull (or
the cache entry it wrote) is the organization's real usage. Deriving that from the fetch
path — rather than a hand-set flag — is what keeps the published
``/about/sustainability`` figures from quietly reading as measured when they are not.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from watermark.config import Settings
from watermark.connectors import cached_get_traced
from watermark.greenops.model import SourceBasis, basis_for_origin

from . import GreenopsOfflineError


def greenops_cached_get(
    connector: str,
    key_params: dict[str, Any],
    fetch: Callable[[], Any],
    settings: Settings,
) -> tuple[dict[str, Any], SourceBasis]:
    """Resolve one GreenOps pull through the shared cache; return ``(payload, basis)``.

    ``key_params`` must exclude every credential — a secret may neither vary the cache key
    nor land in a committed fixture — and ``fetch`` is invoked only on the live path.
    """
    payload, origin = cached_get_traced(
        connector,
        key_params,
        fetch,
        cache_dir=settings.greenops_cache_dir,
        offline=settings.greenops_offline,
        fixtures_dir=settings.greenops_fixtures_dir,
        ttl_hours=settings.greenops_cache_ttl_hours,
        offline_error=GreenopsOfflineError,
    )
    return cast("dict[str, Any]", payload), basis_for_origin(origin)
