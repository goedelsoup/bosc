"""Discovery connector: probe a body's website and classify how it publishes.

Given a homepage, ``discover`` fetches it (through the shared connector cache, so
tests/CI stay offline) and runs two pure passes over the HTML:

* :func:`classify_platform` — match publishing-platform signatures (CivicPlus,
  Granicus, BoardDocs, ... down to generic WordPress) and return the best guess;
* :func:`find_records_links` — collect every anchor that looks like a minutes /
  agenda / meeting page, resolved to absolute URLs.

The result is **read-only** — it is printed/exported for review, never folded back
into the committed registry automatically (the registry's grounded/discovered split
is hand-curated). Locating the homepage of an as-yet-``unknown`` body is out of
scope here: pass it in (``url=`` / ``--url``) or run a search first.
"""

from __future__ import annotations

import re
from typing import Any, cast
from urllib.parse import urljoin

import httpx

from bosc.civic._http import get_page
from bosc.civic.models import DiscoveryResult, Platform, Subdivision
from bosc.config import Settings, get_settings
from bosc.logging import get_logger

log = get_logger(__name__)

# Platform signatures, checked in this order: meeting-specific portals first
# (strongest signal), then site builders, then generic WordPress (weakest — almost
# any CMS-managed municipal page leaks a "wp-content"). First match wins.
_SIGNATURES: list[tuple[Platform, tuple[str, ...]]] = [
    (Platform.CIVICPLUS, ("civicplus", "civicengage", "/agendacenter", ".civicplus.com")),
    (Platform.GRANICUS, ("granicus", "legistar", ".granicus.com", "govaccess")),
    (Platform.BOARDDOCS, ("boarddocs", "go.boarddocs.com")),
    (Platform.CIVICCLERK, ("civicclerk", ".civicclerk.com")),
    (Platform.REVIZE, ("revize.com", "powered by revize")),
    (Platform.WIX, ("wix.com", "_wix", "static.wixstatic.com")),
    (Platform.SQUARESPACE, ("squarespace", "static1.squarespace.com")),
    (Platform.GOVOFFICE, ("govoffice.com", "govoffice")),
    (Platform.WORDPRESS, ("wp-content", "wp-json", "wp-includes", "wordpress")),
]

# Anchor text / href substrings that mark a minutes/agenda/meeting page.
_RECORDS_KEYWORDS = ("minutes", "agenda", "meeting")

_ANCHOR_RE = re.compile(
    r"<a\b[^>]*\bhref=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL
)
_TAG_RE = re.compile(r"<[^>]+>")


def classify_platform(html: str, *, final_url: str = "") -> tuple[Platform, list[str]]:
    """Best-guess publishing platform for a page, plus the signatures that matched.

    Returns ``(Platform.UNKNOWN, [])`` when nothing matches — never a fabricated
    guess. ``final_url`` is matched too (e.g. a redirect to ``*.civicplus.com``).
    """
    haystack = f"{html}\n{final_url}".lower()
    for platform, needles in _SIGNATURES:
        matched = [n for n in needles if n in haystack]
        if matched:
            return platform, matched
    return Platform.UNKNOWN, []


def find_records_links(html: str, *, base_url: str) -> list[str]:
    """Absolute URLs of anchors whose href or text mentions minutes/agenda/meeting.

    De-duplicated, order-preserving. The fragment/text is *not* returned — only the
    resolved links, which a per-platform fetcher then walks.
    """
    found: list[str] = []
    seen: set[str] = set()
    for href, inner in _ANCHOR_RE.findall(html):
        text = _TAG_RE.sub("", inner).strip().lower()
        if not any(k in href.lower() or k in text for k in _RECORDS_KEYWORDS):
            continue
        absolute = urljoin(base_url, href)
        if absolute not in seen:
            seen.add(absolute)
            found.append(absolute)
    return found


def _pick_records_url(candidates: list[str]) -> str | None:
    """Prefer a 'minutes' link, then 'agenda', then any meeting link; else None."""
    for keyword in _RECORDS_KEYWORDS:
        for url in candidates:
            if keyword in url.lower():
                return url
    return candidates[0] if candidates else None


def _fetch_page(url: str, *, settings: Settings) -> dict[str, Any]:
    """Fetch (or replay) one page through the connector cache; return html+final_url."""
    log.info("civic.discovery.fetch", url=url)
    return get_page(url, connector="subdivision_discovery", settings=settings)


def discover(
    subdivision: Subdivision,
    *,
    url: str | None = None,
    settings: Settings | None = None,
) -> DiscoveryResult:
    """Probe a body's website and classify its publishing platform + records page.

    ``url`` overrides the homepage to fetch; otherwise the registry's
    ``publishing.website`` is used. With no homepage available, returns an
    un-fetched result flagged in ``note`` (discovery of the homepage itself is a
    separate search step).
    """
    settings = settings or get_settings()
    homepage = url or subdivision.publishing.website
    if not homepage:
        return DiscoveryResult(
            slug=subdivision.slug,
            homepage=None,
            platform=Platform.UNKNOWN,
            records_url=None,
            records_url_candidates=[],
            signals=[],
            note="no homepage on record — pass --url or run a search first",
        )

    try:
        page = _fetch_page(homepage, settings=settings)
    except httpx.HTTPStatusError as exc:
        # A WAF/bot-block (commonly 403/406) is a finding, not a crash: report it so
        # a sweep (`--all`) keeps going and the body is flagged for another route.
        return DiscoveryResult(
            slug=subdivision.slug,
            homepage=homepage,
            platform=Platform.UNKNOWN,
            records_url=None,
            records_url_candidates=[],
            signals=[],
            note=f"fetch blocked: HTTP {exc.response.status_code} {exc.response.reason_phrase}",
        )
    except httpx.HTTPError as exc:
        return DiscoveryResult(
            slug=subdivision.slug,
            homepage=homepage,
            platform=Platform.UNKNOWN,
            records_url=None,
            records_url_candidates=[],
            signals=[],
            note=f"fetch failed: {type(exc).__name__}",
        )
    html = cast("str", page.get("html", ""))
    final_url = cast("str", page.get("final_url", homepage))
    platform, signals = classify_platform(html, final_url=final_url)
    candidates = find_records_links(html, base_url=final_url)
    return DiscoveryResult(
        slug=subdivision.slug,
        homepage=final_url,
        platform=platform,
        records_url=_pick_records_url(candidates),
        records_url_candidates=candidates,
        signals=signals,
        note=None if platform is not Platform.UNKNOWN else "no platform signature matched",
    )
