"""Per-platform meeting-document fetchers, dispatched on ``Subdivision.platform``.

Each fetcher turns a body's online records into a list of ``MeetingDoc`` (the
inventory of available minutes/agendas with verbatim URLs + parsed dates).
Downloading the binaries into ``data/documents/<slug>/`` under chain-of-custody is
a separate step on top of this inventory.

Implemented:
- ``civicplus`` — CivicPlus / CivicEngage Agenda Center (Lima, LACRPC).
- ``generic`` — records-page link scraper for the WordPress / Wix / Revize / static
  bodies (and any ``unknown`` body that still has a ``records_url`` to scrape).
"""

from __future__ import annotations

from bosc.civic.fetchers import civicplus, generic
from bosc.civic.models import MeetingDoc, Platform, Subdivision
from bosc.config import Settings

__all__ = [
    "FetcherNotImplementedError",
    "civicplus",
    "fetch_meetings",
    "generic",
    "supported_platforms",
]

# Bodies whose records are just document links on a page -> the generic scraper.
_GENERIC_PLATFORMS = {
    Platform.WORDPRESS,
    Platform.WIX,
    Platform.REVIZE,
    Platform.SQUARESPACE,
    Platform.GOVOFFICE,
}


class FetcherNotImplementedError(RuntimeError):
    """No fetcher is wired for a body's publishing platform yet."""


def supported_platforms() -> set[Platform]:
    """Platforms that currently have a fetcher."""
    return {Platform.CIVICPLUS, *_GENERIC_PLATFORMS}


def fetch_meetings(
    subdivision: Subdivision,
    *,
    url: str | None = None,
    settings: Settings | None = None,
) -> list[MeetingDoc]:
    """Dispatch to the fetcher for ``subdivision``'s platform.

    CivicPlus → the Agenda Center fetcher; WordPress/Wix/Revize/Squarespace/GovOffice
    → the generic records-page scraper. An ``unknown`` body is sent to the generic
    scraper too **iff** it has a ``records_url`` (a page was found, its CMS just
    wasn't fingerprinted). Raises :class:`FetcherNotImplementedError` otherwise —
    e.g. ``facebook`` / ``request_only`` bodies, which have no records page.
    """
    platform = subdivision.publishing.platform
    if platform is Platform.CIVICPLUS:
        return civicplus.fetch(subdivision, url=url, settings=settings)
    if platform in _GENERIC_PLATFORMS or (
        platform is Platform.UNKNOWN and (url or subdivision.publishing.records_url)
    ):
        return generic.fetch(subdivision, url=url, settings=settings)
    raise FetcherNotImplementedError(
        f"{subdivision.slug}: no fetcher for platform '{platform.value}' "
        f"(no records page to scrape; supported: civicplus + "
        f"{', '.join(sorted(p.value for p in _GENERIC_PLATFORMS))})"
    )
