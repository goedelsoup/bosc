"""Shared page fetch for the civic subsystem (discovery + fetchers).

One browser-like GET through the connector cache, so every civic network call gets
the same offline/fixture discipline, brotli decoding, and WAF-dodging User-Agent.
"""

from __future__ import annotations

from typing import Any, cast

import httpx

from bosc.config import Settings
from bosc.hydrology.connectors._cache import cached_get

# A real browser User-Agent + Accept: several county CMS/WAFs (Sucuri, the Duda CDN,
# Drupal bot rules) reflexively 403/406 an unknown UA, which would otherwise hide a
# body's records. The `brotli` dep lets httpx decode the `br` responses those same
# servers force, so we let httpx negotiate Accept-Encoding itself.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def get_page(url: str, *, connector: str, settings: Settings) -> dict[str, Any]:
    """Fetch (or replay) one page; return ``{html, final_url, status_code}``.

    ``connector`` namespaces the cache/fixture directory (e.g. ``subdivision_discovery``,
    ``civicplus``). Raises ``httpx.HTTPStatusError`` on a 4xx/5xx live response and
    ``HydroOfflineError`` on an offline cache/fixture miss.
    """

    def fetch() -> Any:
        resp = httpx.get(
            url,
            follow_redirects=True,
            timeout=settings.hydro_request_timeout_s,
            headers=BROWSER_HEADERS,
        )
        resp.raise_for_status()
        return {"html": resp.text, "final_url": str(resp.url), "status_code": resp.status_code}

    return cast("dict[str, Any]", cached_get(connector, {"url": url}, fetch, settings=settings))
